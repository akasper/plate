"""Typed issue-context resolution for branch policy (#1449).

PR bodies and sidebar metadata are untrusted input; results distinguish
verified absence from API/network failures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .pr_gates_checks import normalize_label_list, requires_strict_closing_keyword
from .pr_gates_closing import CLOSING_KEYWORD_STRICT_RE, strip_closing_scan_text

INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LOOSE_HASH_RE = re.compile(r"(?<!#)#(\d+)\b")

_SIDEBAR_GRAPHQL = """
query($owner: String!, $repo: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      timelineItems(first: 100, after: $after, itemTypes: [CONNECTED_EVENT, DISCONNECTED_EVENT]) {
        pageInfo { hasNextPage endCursor }
        nodes {
          __typename
          ... on ConnectedEvent {
            createdAt
            subject {
              __typename
              ... on Issue {
                id
                number
                repository { nameWithOwner }
              }
            }
          }
          ... on DisconnectedEvent {
            createdAt
            subject {
              __typename
              ... on Issue {
                id
                number
                repository { nameWithOwner }
              }
            }
          }
        }
      }
    }
  }
}
"""


class IssueContextStatus(str, Enum):
    OK = "ok"
    ABSENT = "absent"
    UNAVAILABLE = "unavailable"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True)
class IssueRef:
    owner: str
    repo: str
    number: int
    source: str  # "closing_body" | "sidebar"

    @property
    def repo_full(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass
class IssueContextResult:
    status: IssueContextStatus
    refs: list[IssueRef] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in (IssueContextStatus.OK, IssueContextStatus.ABSENT, IssueContextStatus.NOT_REQUIRED)


def strip_inline_code_for_scan(text: str | None) -> str:
    if not text:
        return ""
    return INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)


def strip_blockquotes_for_scan(text: str | None) -> str:
    """Drop markdown blockquote lines from closing-keyword scan input."""
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _scan_body_for_closing(body: str | None) -> str:
    return strip_closing_scan_text(
        strip_inline_code_for_scan(strip_blockquotes_for_scan(body))
    )


def parse_closing_issue_refs(
    body: str | None,
    *,
    default_repo: str,
) -> list[IssueRef]:
    """Parse closing keywords from fence-stripped, inline-code-stripped body."""
    owner, name = default_repo.split("/", 1)
    cleaned = _scan_body_for_closing(body)
    seen: set[tuple[str, str, int]] = set()
    out: list[IssueRef] = []
    for match in CLOSING_KEYWORD_STRICT_RE.finditer(cleaned):
        url_owner = match.group("url_owner")
        url_repo = match.group("url_repo")
        num_s = match.group("url_num") or match.group("hash_num")
        if not num_s:
            continue
        ref_owner = (url_owner or owner).strip()
        ref_repo = (url_repo or name).strip()
        num = int(num_s)
        key = (ref_owner.lower(), ref_repo.lower(), num)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            IssueRef(owner=ref_owner, repo=ref_repo, number=num, source="closing_body")
        )
    return out


def detect_unparsed_closing_candidates(body: str | None) -> bool:
    """True when #N or closing-like text appears outside scannable prose."""
    if not body:
        return False
    raw_clean = strip_closing_scan_text(strip_blockquotes_for_scan(body))
    raw_loose = {int(m) for m in _LOOSE_HASH_RE.findall(raw_clean)}
    stripped = _scan_body_for_closing(body)
    strict_nums = {ref.number for ref in parse_closing_issue_refs(stripped, default_repo="x/y")}
    strict_from_stripped = set()
    owner_l = "x"
    repo_l = "y"
    for match in CLOSING_KEYWORD_STRICT_RE.finditer(stripped):
        num_s = match.group("url_num") or match.group("hash_num")
        if num_s:
            strict_from_stripped.add(int(num_s))
    if raw_loose - strict_from_stripped:
        return True
    # Closing keywords only inside original fences (invisible after strip)
    if re.search(r"\b(closes?|fixe?s?|fixed|resolve[sd]?)\s+#\d+", body or "", re.I):
        if not re.search(r"\b(closes?|fixe?s?|fixed|resolve[sd]?)\s+#\d+", stripped, re.I):
            return True
    return False


def _issue_ref_from_graphql_subject(subject: dict[str, Any], *, fallback_repo: str) -> IssueRef | None:
    if subject.get("__typename") != "Issue":
        return None
    issue_id = subject.get("id")
    num = subject.get("number")
    if issue_id is None or num is None:
        return None
    repo_full = ((subject.get("repository") or {}).get("nameWithOwner") or "").strip()
    if repo_full and "/" in repo_full:
        ref_owner, ref_repo = repo_full.split("/", 1)
    else:
        ref_owner, ref_repo = fallback_repo.split("/", 1)
    return IssueRef(owner=ref_owner, repo=ref_repo, number=int(num), source="sidebar")


def sidebar_linked_issue_refs(
    pr_repo: str,
    pr_number: int,
    *,
    client: GhClient,
) -> tuple[list[IssueRef] | None, str | None]:
    """Replay Development sidebar links; None refs means API failure."""
    owner, name = pr_repo.split("/", 1)
    linked_by_id: dict[str, IssueRef] = {}
    after: str | None = None
    seen_cursors: set[str] = set()
    try:
        while True:
            payload = client.api(
                "graphql",
                method="POST",
                fields={
                    "query": _SIDEBAR_GRAPHQL,
                    "owner": owner,
                    "repo": name,
                    "number": pr_number,
                    "after": after,
                },
            )
            gql_errors = (payload or {}).get("errors") or []
            if gql_errors:
                msgs = "; ".join(
                    str(item.get("message") or item) for item in gql_errors if item
                )
                return None, f"Development sidebar GraphQL errors: {msgs}"
            repo_data = ((payload or {}).get("data") or {}).get("repository")
            if not repo_data:
                return None, "Could not load repository for Development sidebar links."
            pr = repo_data.get("pullRequest")
            if not pr:
                return None, "Could not load PR timeline for Development sidebar links."
            if "timelineItems" not in pr:
                return None, "PR timeline metadata unavailable for Development sidebar links."
            items = pr["timelineItems"]
            if not isinstance(items, dict):
                return None, "Invalid PR timeline payload for Development sidebar links."
            events = items.get("nodes")
            if events is None:
                return None, "PR timeline nodes missing for Development sidebar links."
            page = items.get("pageInfo")
            if not isinstance(page, dict):
                return None, "PR timeline pageInfo missing for Development sidebar links."
            for node in events:
                subject = node.get("subject") or {}
                ref = _issue_ref_from_graphql_subject(subject, fallback_repo=pr_repo)
                if ref is None:
                    continue
                if node.get("__typename") == "ConnectedEvent":
                    linked_by_id[str(subject.get("id"))] = ref
                elif node.get("__typename") == "DisconnectedEvent":
                    linked_by_id.pop(str(subject.get("id")), None)
            if not page.get("hasNextPage"):
                break
            end_cursor = page.get("endCursor")
            if not end_cursor:
                return None, "Sidebar timeline pagination incomplete (missing endCursor)."
            if end_cursor in seen_cursors:
                return None, "Sidebar timeline pagination stalled (repeated endCursor)."
            seen_cursors.add(str(end_cursor))
            if after is not None and end_cursor == after:
                return None, "Sidebar timeline pagination did not advance."
            after = end_cursor
        return sorted(linked_by_id.values(), key=lambda r: (r.repo_full.lower(), r.number)), None
    except GhApiError as exc:
        return None, f"Development sidebar link verification failed: {exc}"


def _merge_labels_from_issue_payload(payload: dict[str, Any] | None) -> tuple[list[str], str | None]:
    if not isinstance(payload, dict):
        return [], "Issue payload missing or not an object."
    raw = payload.get("labels")
    if raw is None:
        return [], "Issue response missing labels field."
    if not isinstance(raw, list):
        return [], "Issue labels field is not a list."
    names = [str(item.get("name") or "").strip() for item in raw if isinstance(item, dict)]
    return [n for n in names if n], None


def fetch_issue_labels_for_ref(
    ref: IssueRef,
    *,
    client: GhClient,
) -> tuple[list[str], str | None]:
    endpoint = f"repos/{ref.repo_full}/issues/{ref.number}"
    try:
        payload = client.api(endpoint)
    except GhApiError as exc:
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg:
            return [], f"Issue {ref.repo_full}#{ref.number} not found."
        return [], f"Could not load issue {ref.repo_full}#{ref.number}: {exc}"
    return _merge_labels_from_issue_payload(payload)


def resolve_issue_context(
    *,
    pr_repo: str | None,
    pr_labels: list[str],
    body: str | None,
    pr_number: int | None = None,
    client: GhClient | None = None,
) -> IssueContextResult:
    labs = normalize_label_list(pr_labels)
    if not requires_strict_closing_keyword(labs):
        return IssueContextResult(status=IssueContextStatus.NOT_REQUIRED)

    gh = client or GhClient()
    target = resolve_repo(pr_repo)
    owner, name = target.split("/", 1)

    refs = parse_closing_issue_refs(body, default_repo=target)
    if pr_number is not None:
        sidebar_refs, err = sidebar_linked_issue_refs(target, pr_number, client=gh)
        if err:
            return IssueContextResult(
                status=IssueContextStatus.UNAVAILABLE,
                message=err,
            )
        if sidebar_refs:
            seen = {(r.owner.lower(), r.repo.lower(), r.number) for r in refs}
            for sr in sidebar_refs:
                key = (sr.owner.lower(), sr.repo.lower(), sr.number)
                if key not in seen:
                    refs.append(sr)
                    seen.add(key)

    if not refs and detect_unparsed_closing_candidates(body):
        return IssueContextResult(
            status=IssueContextStatus.UNAVAILABLE,
            message=(
                "Closing references appear inside inline code, comments, or fences where "
                "branch policy cannot read them. Move Closes #N into normal PR body prose, "
                "or use a Development sidebar link when the PR number is available."
            ),
        )

    if not refs:
        return IssueContextResult(status=IssueContextStatus.ABSENT, refs=[], labels=[])

    merged: list[str] = []
    for ref in refs:
        labels, err = fetch_issue_labels_for_ref(ref, client=gh)
        if err:
            return IssueContextResult(
                status=IssueContextStatus.UNAVAILABLE,
                refs=refs,
                message=err,
            )
        for lab in labels:
            if lab not in merged:
                merged.append(lab)

    return IssueContextResult(
        status=IssueContextStatus.OK,
        refs=refs,
        labels=merged,
    )
