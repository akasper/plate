"""Local PR feedback babysitting helpers."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .github_client import GhClient
from .health import resolve_repo


_DEFAULT_AGENT_PATTERNS = [
    re.compile(r"^devin", re.IGNORECASE),
    re.compile(r"^openhands", re.IGNORECASE),
    re.compile(r"^codegen", re.IGNORECASE),
    re.compile(r"^swe-agent", re.IGNORECASE),
    re.compile(r"^aide-agent", re.IGNORECASE),
    re.compile(r"^mentat-bot", re.IGNORECASE),
]

_BABYSIT_MARKER = "<!-- plate-pr-babysit -->"
_MERGE_TRIGGER_MARKER = "<!-- plate-pr-merge-trigger -->"

# Valid branch update strategies
_VALID_STRATEGIES = ["copilot-request", "local-rebase", "none"]
_DEFAULT_STRATEGY = "copilot-request"


@dataclass
class BabysitReport:
    repo: str
    pr_number: int
    detected_threads: int
    actionable_threads: int
    trigger_comment_posted: bool
    trigger_comment_url: str | None = None
    out_of_sync: bool = False
    merge_state: str | None = None
    merge_trigger_posted: bool = False
    merge_trigger_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _default_agent_match(login: str) -> bool:
    return any(pattern.search(login or "") for pattern in _DEFAULT_AGENT_PATTERNS)


def _detect_base_branch_out_of_sync(pr_data: dict) -> dict:
    """Detect if PR branch is out of sync with base branch.

    Args:
        pr_data: PR data containing mergeStateStatus and branch refs

    Returns:
        dict with keys:
            - out_of_sync (bool): Whether PR is out of sync
            - state (str): The mergeStateStatus value
            - base_ref (str): Base branch name
            - head_ref (str): Head branch name
    """
    merge_state = pr_data.get("mergeStateStatus", "")
    out_of_sync_states = ["BEHIND", "CONFLICTING", "DIRTY"]

    return {
        "out_of_sync": merge_state in out_of_sync_states,
        "state": merge_state,
        "base_ref": pr_data.get("baseRefName", ""),
        "head_ref": pr_data.get("headRefName", ""),
    }


def _parse_agent_logins(agent_logins: str | None) -> set[str]:
    if not agent_logins:
        return set()
    return {item.strip().lower() for item in agent_logins.split(",") if item.strip()}


def _extract_actionable_threads(threads: list[dict], agent_logins: str | None) -> list[dict]:
    configured = _parse_agent_logins(agent_logins)
    actionable: list[dict] = []
    for thread in threads:
        if thread.get("isResolved") or thread.get("isOutdated"):
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue
        last = comments[-1]
        author = ((last.get("author") or {}).get("login") or "").strip()
        lower = author.lower()
        is_target = lower in configured if configured else _default_agent_match(author)
        if not is_target:
            continue
        actionable.append(
            {
                "thread_id": thread.get("id"),
                "comment_id": last.get("databaseId"),
                "author": author,
                "url": last.get("url"),
                "body": (last.get("body") or "").strip(),
            }
        )
    return actionable


def _load_review_threads(client: GhClient, repo: str, pr_number: int) -> list[dict]:
    """Load review threads only. For backward compatibility."""
    pr_data = _load_pr_data(client, repo, pr_number)
    return pr_data.get("reviewThreads", [])


def _load_pr_data(client: GhClient, repo: str, pr_number: int) -> dict:
    """Load PR data including review threads and merge state.

    Returns:
        dict with keys:
            - reviewThreads (list): List of review thread nodes
            - mergeStateStatus (str): Merge state (CLEAN, BEHIND, CONFLICTING, DIRTY, etc)
            - baseRefName (str): Base branch name
            - headRefName (str): Head branch name
    """
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      mergeStateStatus
      baseRefName
      headRefName
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(last: 5) {
            nodes {
              databaseId
              body
              url
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}
""".strip()
    payload = client.api(
        "graphql",
        method="POST",
        fields={
            "query": query,
            "variables[owner]": owner,
            "variables[repo]": name,
            "variables[number]": pr_number,
        },
    )
    pr = (
        ((payload or {}).get("data") or {})
        .get("repository", {})
        .get("pullRequest", {})
    )
    return {
        "reviewThreads": (pr.get("reviewThreads", {}) or {}).get("nodes", []),
        "mergeStateStatus": pr.get("mergeStateStatus", "UNKNOWN"),
        "baseRefName": pr.get("baseRefName", ""),
        "headRefName": pr.get("headRefName", ""),
    }


def _has_existing_babysit_comment(client: GhClient, repo: str, pr_number: int) -> bool:
    comments = client.api(f"repos/{repo}/issues/{pr_number}/comments?per_page=100&sort=created&direction=desc")
    return any(_BABYSIT_MARKER in ((c or {}).get("body") or "") for c in comments or [])


def _has_existing_merge_trigger_comment(client: GhClient, repo: str, pr_number: int) -> bool:
    """Check if merge trigger comment already exists to avoid duplicates."""
    comments = client.api(f"repos/{repo}/issues/{pr_number}/comments?per_page=100&sort=created&direction=desc")
    return any(_MERGE_TRIGGER_MARKER in ((c or {}).get("body") or "") for c in comments or [])


def _post_babysit_trigger(client: GhClient, repo: str, pr_number: int, actionable_threads: list[dict]) -> str | None:
    thread_lines = [f"- {item['url']} (thread `{item['thread_id']}` by @{item['author']})" for item in actionable_threads]
    body = "\n".join(
        [
            _BABYSIT_MARKER,
            "@copilot Start PR feedback babysitting for this pull request.",
            "",
            "Actionable third-party agent threads detected:",
            *thread_lines,
            "",
            "Workflow requirements:",
            "1. Address each actionable thread with code changes or a rationale reply.",
            "2. Push changes to this same PR branch (do not open a new PR).",
            "3. Resolve each addressed thread via GraphQL `resolveReviewThread`.",
            "4. If human judgment is needed, add `need:human-review` and explain the block.",
        ]
    )
    response = client.api(
        f"repos/{repo}/issues/{pr_number}/comments",
        method="POST",
        fields={"body": body},
    )
    return (response or {}).get("html_url")


def _post_merge_trigger(client: GhClient, repo: str, pr_number: int, sync_info: dict) -> str | None:
    """Post a Copilot merge-request trigger comment.

    Args:
        client: GitHub client
        repo: Repository identifier (owner/name)
        pr_number: Pull request number
        sync_info: Dict with base_ref, head_ref, and state

    Returns:
        URL of posted comment or None
    """
    base_ref = sync_info.get("base_ref", "base")
    head_ref = sync_info.get("head_ref", "head")
    state = sync_info.get("state", "out-of-sync")

    body = "\n".join(
        [
            _MERGE_TRIGGER_MARKER,
            f"@copilot This PR branch (`{head_ref}`) is out of sync with the base branch (`{base_ref}`).",
            f"Merge state: `{state}`",
            "",
            "Please update this branch to resolve the merge conflict or bring it up to date with the base branch.",
        ]
    )
    response = client.api(
        f"repos/{repo}/issues/{pr_number}/comments",
        method="POST",
        fields={"body": body},
    )
    return (response or {}).get("html_url")


def babysit_pr(
    pr_number: int,
    repo: str | None = None,
    *,
    agent_logins: str | None = None,
    act: bool = False,
    branch_update_strategy: str | None = None,
    client: GhClient | None = None,
) -> BabysitReport:
    """Babysit a pull request for actionable third-party agent feedback and base branch sync.

    Args:
        pr_number: Pull request number
        repo: Repository identifier (owner/name), defaults to git remote
        agent_logins: Comma-separated GitHub logins to treat as agents
        act: If True, post trigger comments when issues detected
        branch_update_strategy: How to handle out-of-sync base branch.
            Options: "copilot-request" (default), "local-rebase", "none"
        client: Optional GitHub client

    Returns:
        BabysitReport with detection and action results
    """
    target = resolve_repo(repo)
    gh = client or GhClient()
    strategy = branch_update_strategy or _DEFAULT_STRATEGY

    # Validate strategy
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(f"Invalid branch_update_strategy: {strategy}. Must be one of {_VALID_STRATEGIES}")

    # Load PR data including threads and merge state
    pr_data = _load_pr_data(gh, target, pr_number)
    threads = pr_data.get("reviewThreads", [])
    actionable = _extract_actionable_threads(threads, agent_logins)

    # Detect base branch sync state
    sync_info = _detect_base_branch_out_of_sync(pr_data)

    # Handle review thread feedback
    posted = False
    trigger_url = None
    if act and actionable and not _has_existing_babysit_comment(gh, target, pr_number):
        trigger_url = _post_babysit_trigger(gh, target, pr_number, actionable)
        posted = True

    # Handle base branch sync
    merge_trigger_posted = False
    merge_trigger_url = None
    if act and sync_info["out_of_sync"] and strategy == "copilot-request":
        if not _has_existing_merge_trigger_comment(gh, target, pr_number):
            merge_trigger_url = _post_merge_trigger(gh, target, pr_number, sync_info)
            merge_trigger_posted = True
    elif act and sync_info["out_of_sync"] and strategy == "local-rebase":
        # Stub for future implementation
        raise NotImplementedError("local-rebase strategy is not yet implemented")

    return BabysitReport(
        repo=target,
        pr_number=pr_number,
        detected_threads=len(threads),
        actionable_threads=len(actionable),
        trigger_comment_posted=posted,
        trigger_comment_url=trigger_url,
        out_of_sync=sync_info["out_of_sync"],
        merge_state=sync_info["state"],
        merge_trigger_posted=merge_trigger_posted,
        merge_trigger_url=merge_trigger_url,
    )


def resolve_review_thread(
    thread_id: str,
    repo: str | None = None,
    *,
    client: GhClient | None = None,
) -> dict:
    target = resolve_repo(repo)
    gh = client or GhClient()
    query = """
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}
""".strip()
    payload = gh.api(
        "graphql",
        method="POST",
        fields={"query": query, "variables[threadId]": thread_id},
    )
    thread = (
        ((payload or {}).get("data") or {})
        .get("resolveReviewThread", {})
        .get("thread", {})
    )
    return {"repo": target, "thread_id": thread.get("id", thread_id), "resolved": bool(thread.get("isResolved"))}
