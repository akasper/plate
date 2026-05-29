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


@dataclass
class BabysitReport:
    repo: str
    pr_number: int
    detected_threads: int
    actionable_threads: int
    trigger_comment_posted: bool
    trigger_comment_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _default_agent_match(login: str) -> bool:
    return any(pattern.search(login or "") for pattern in _DEFAULT_AGENT_PATTERNS)


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
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
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
    return (
        ((payload or {}).get("data") or {})
        .get("repository", {})
        .get("pullRequest", {})
        .get("reviewThreads", {})
        .get("nodes", [])
    )


def _has_existing_babysit_comment(client: GhClient, repo: str, pr_number: int) -> bool:
    comments = client.api(f"repos/{repo}/issues/{pr_number}/comments?per_page=100&sort=created&direction=desc")
    return any(_BABYSIT_MARKER in ((c or {}).get("body") or "") for c in comments or [])


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


def babysit_pr(
    pr_number: int,
    repo: str | None = None,
    *,
    agent_logins: str | None = None,
    act: bool = False,
    client: GhClient | None = None,
) -> BabysitReport:
    target = resolve_repo(repo)
    gh = client or GhClient()
    threads = _load_review_threads(gh, target, pr_number)
    actionable = _extract_actionable_threads(threads, agent_logins)

    posted = False
    trigger_url = None
    if act and actionable and not _has_existing_babysit_comment(gh, target, pr_number):
        trigger_url = _post_babysit_trigger(gh, target, pr_number, actionable)
        posted = True

    return BabysitReport(
        repo=target,
        pr_number=pr_number,
        detected_threads=len(threads),
        actionable_threads=len(actionable),
        trigger_comment_posted=posted,
        trigger_comment_url=trigger_url,
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
