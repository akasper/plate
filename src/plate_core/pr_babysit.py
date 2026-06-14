"""Local PR feedback babysitting helpers.

The pr-babysit skill/MCP surface (`gh plate pr babysit` or `plate_pr_babysit`) is the dedicated tool for PR feedback and health work. Agents must default to it (rather than hand-rolling git/gh commands) for "babysit", "get CI passing", "address feedback", or "make PR green" instructions (addresses #524 and related).

**Mandatory first step in any verification/babysit/repro flow (addresses #527):** "CI diagnosis first" — *always* fetch `gh pr checks <N>` + identify the exact failing job/run + `gh run view <run> --job <job> --log-failed` (or equivalent structured) *before* any broad/expensive local command (e.g. full pytest in worktree). Only after seeing the real current error (labels? threads? specific test failure?) decide minimal scope or if local repro is even needed. Use cheap GitHub inspection before investing CPU/time.

During babysit or green-loop work, own the *full* "current failing gates" model and "make mergeable" loop (per agent_guidance "Full PR Green / Make Mergeable Loop" + new "CI Diagnosis First Protocol" and AGENTS.md babysit section):
- Start (and re-start after pushes) by comprehensively inspecting *all* gates, *beginning with* the CI diagnosis one-liners above (threads via the tool, base sync, labels, etc.).
- Address everything agent-actionable in the worktree (rebase, apply safe suggestions, resolve addressed threads via plate_resolve_review_thread, fix local tests with targeted scope only, etc.).
- Push to the *existing* PR branch only.
- Re-inspect (starting again with CI diagnosis).
- Repeat until only human-judgment items remain (e.g. owner CHANGES_REQUESTED, credentials, high-risk decisions). Only then report the one-sentence summary of what is left for the human.
- Use quiet terse bullets for looped turns. Escalate with need:human-review for judgment items.

The skill supports (via --act, --branch-update-strategy, and the returned BabysitReport) the inspect-fix-push-reinspect cycle. Prefer or expose "until-green" / comprehensive make-mergeable behavior in future enhancements. Follow long-running command protocol for any backgrounded verification during the loop (record task_id, poll, cheap fallback on kill; see #529). Always start verification with CI diagnosis first (see #527).

See quiet_operations guidance (including new CI Diagnosis First and Full PR Green sections), plate.agent.md, and AGENTS.md for the full procedure (addresses #528, #527, #526, #519, #510, etc.).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
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
    local_rebase_performed: bool = False
    local_rebase_success: bool | None = None
    local_rebase_conflict: bool = False
    local_rebase_error: str | None = None

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
            "owner": owner,
            "repo": name,
            "number": pr_number,
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


def _perform_local_rebase(base_ref: str, head_ref: str, repo_dir: str | None = None) -> dict:
    """Perform a local rebase of head_ref onto base_ref using an isolated git worktree.

    Returns a dict with:
        success: bool
        conflict: bool
        error: str | None
        output: str | None
    Safe: does not modify current working tree; cleans up worktree on exit.
    """
    if not base_ref or not head_ref:
        return {"success": False, "conflict": False, "error": "missing base or head ref", "output": None}

    if repo_dir is None:
        # detect from cwd
        try:
            repo_dir = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True, cwd="."
            ).strip()
        except Exception as e:
            return {"success": False, "conflict": False, "error": f"not in git repo: {e}", "output": None}

    worktree_path = None
    try:
        # fresh fetch
        subprocess.check_call(["git", "-C", repo_dir, "fetch", "origin", base_ref, head_ref], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        worktree_path = tempfile.mkdtemp(prefix="plate-babysit-rebase-")
        # add worktree at the head_ref tip
        subprocess.check_call(
            ["git", "-C", repo_dir, "worktree", "add", "--detach", worktree_path, f"origin/{head_ref}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # rebase in the worktree
        rebase_res = subprocess.run(
            ["git", "-C", worktree_path, "rebase", f"origin/{base_ref}"],
            capture_output=True, text=True
        )
        if rebase_res.returncode != 0:
            # abort to clean
            subprocess.run(["git", "-C", worktree_path, "rebase", "--abort"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "success": False,
                "conflict": True,
                "error": "rebase conflict or failure",
                "output": (rebase_res.stdout or "") + (rebase_res.stderr or ""),
            }

        # push back (force-with-lease for safety)
        push_res = subprocess.run(
            ["git", "-C", worktree_path, "push", "origin", f"HEAD:{head_ref}", "--force-with-lease"],
            capture_output=True, text=True
        )
        if push_res.returncode != 0:
            return {
                "success": False,
                "conflict": False,
                "error": "push after rebase failed",
                "output": (push_res.stdout or "") + (push_res.stderr or ""),
            }

        return {"success": True, "conflict": False, "error": None, "output": None}

    except Exception as e:
        return {"success": False, "conflict": False, "error": str(e), "output": None}
    finally:
        if worktree_path:
            try:
                subprocess.run(
                    ["git", "-C", repo_dir, "worktree", "remove", "--force", worktree_path],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
            shutil.rmtree(worktree_path, ignore_errors=True)


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
    local_rebase_performed = False
    local_rebase_success = None
    local_rebase_conflict = False
    local_rebase_error = None
    if act and sync_info["out_of_sync"] and strategy == "copilot-request":
        if not _has_existing_merge_trigger_comment(gh, target, pr_number):
            merge_trigger_url = _post_merge_trigger(gh, target, pr_number, sync_info)
            merge_trigger_posted = True
    elif act and sync_info["out_of_sync"] and strategy == "local-rebase":
        rebase_res = _perform_local_rebase(sync_info.get("base_ref"), sync_info.get("head_ref"))
        local_rebase_performed = True
        local_rebase_success = rebase_res.get("success", False)
        local_rebase_conflict = rebase_res.get("conflict", False)
        local_rebase_error = rebase_res.get("error")
        # Note: we do not post copilot trigger when local-rebase is chosen

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
        local_rebase_performed=local_rebase_performed,
        local_rebase_success=local_rebase_success,
        local_rebase_conflict=local_rebase_conflict,
        local_rebase_error=local_rebase_error,
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
        fields={"query": query, "threadId": thread_id},
    )
    thread = (
        ((payload or {}).get("data") or {})
        .get("resolveReviewThread", {})
        .get("thread", {})
    )
    return {"repo": target, "thread_id": thread.get("id", thread_id), "resolved": bool(thread.get("isResolved"))}
