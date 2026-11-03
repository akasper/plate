"""Compact PR evidence packets for agent handoffs (#1364).

Builds a size-capped JSON bundle (review threads, failing check excerpts, PR facts)
so downstream agents can act on feedback without re-reading raw bot comments or full
CI logs. Reuses babysit watch probe helpers (ETag / conditional GET) and REST ``since``
deltas from ``pr_watch_probe`` (#1077–#1081) with a **separate** persisted checkpoint
from ``gh plate pr babysit --watch``. Optional spend-ledger rows record
``handoff_packet_size`` and ``turns`` (#1352 / #1358).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .integration_close import parse_closing_issue_numbers
from .pr_watch_backoff import Backoff
from .pr_watch_probe import (
    GhApiHttp,
    HttpClient,
    ProbeState,
    _split_repo,
    fetch_delta,
    load_probe_state,
    probe_pr,
    save_probe_state,
)
from .procutil import run_hidden

DEFAULT_MAX_BYTES = 6144
COMMENT_SNIPPET_LEN = 400
_FAIL_LOG_MAX_LINES = 16
_QUOTED_CODE_MAX_LINES = 12
_DELTA_EPOCH = "1970-01-01T00:00:00Z"
_REVIEW_THREADS_PAGE = 100
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class PrPacketResult:
    packet: dict[str, Any]
    json_text: str
    byte_size: int
    probe_changed: bool
    not_modified: bool
    ledger_entry: dict[str, Any] | None = None


class PacketClient(Protocol):
    """Minimal GitHub client surface for tests and live ``GhClient``."""

    def api(self, endpoint: str, method: str = "GET", fields: Mapping[str, Any] | None = None) -> Any:
        ...


def packet_probe_state_path(repo: str, pr: int, root: Path | str | None = None) -> Path:
    """Persisted probe checkpoint for pr-packet only (not babysit watch)."""
    owner, name = _split_repo(repo)
    base = Path(root) if root is not None else Path.cwd()
    return base / ".agentic" / "babysit" / f"{len(owner)}-{owner}-{len(name)}-{name}-{pr}.packet-probe.json"


def serialize_pr_packet(packet: dict[str, Any]) -> str:
    """Canonical JSON text for CLI, MCP, size fitting, and ledger measurement."""
    return json.dumps(packet, indent=2, ensure_ascii=False) + "\n"


def _stamp_byte_size(packet: dict[str, Any]) -> dict[str, Any]:
    """Set ``byte_size`` to the UTF-8 length of the canonical serialized packet."""
    working = dict(packet)
    working.pop("byte_size", None)
    for _ in range(24):
        working["byte_size"] = len(serialize_pr_packet(working).encode("utf-8"))
        text = serialize_pr_packet(working)
        size = len(text.encode("utf-8"))
        if working["byte_size"] == size:
            working["byte_size"] = size
            break
        working["byte_size"] = size
    return working


def _comment_snippet(body: str | None) -> str:
    text = (body or "").strip()
    if len(text) <= COMMENT_SNIPPET_LEN:
        return text
    return text[:COMMENT_SNIPPET_LEN] + "…"


def _quoted_code_lines(diff_hunk: str | None, *, line: int | None = None) -> list[str]:
    if not diff_hunk:
        return []
    parsed: list[tuple[int | None, str]] = []
    new_line: int | None = None
    for raw in diff_hunk.splitlines():
        header = _HUNK_HEADER_RE.match(raw)
        if header:
            new_line = int(header.group(2))
            continue
        if raw.startswith(("+++", "---")):
            continue
        if not raw.startswith(("+", "-", " ")):
            continue
        if raw.startswith("-"):
            parsed.append((None, raw))
            continue
        parsed.append((new_line, raw))
        if new_line is not None:
            new_line += 1

    if not parsed:
        return []

    visible = [(idx, nl, text) for idx, (nl, text) in enumerate(parsed) if nl is not None]
    if not visible:
        return [text for _, text in parsed[:_QUOTED_CODE_MAX_LINES]]

    if line is None:
        return [text for _, _, text in visible[:_QUOTED_CODE_MAX_LINES]]

    anchor_idx = min(visible, key=lambda item: abs((item[1] or 0) - line))[0]
    half = _QUOTED_CODE_MAX_LINES // 2
    start = max(0, anchor_idx - half)
    end = min(len(parsed), start + _QUOTED_CODE_MAX_LINES)
    start = max(0, end - _QUOTED_CODE_MAX_LINES)
    return [parsed[i][1] for i in range(start, end)]


def _thread_state(*, is_outdated: bool, is_resolved: bool, comment_count: int) -> str:
    if is_outdated:
        return "outdated"
    if comment_count > 1 or is_resolved:
        return "addressed"
    return "unresolved"


def _format_thread_nodes(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for thread in threads or []:
        if not isinstance(thread, dict):
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        first = comments[0] if comments else {}
        last = comments[-1] if comments else {}
        body = (last.get("body") or first.get("body") or "").strip()
        diff_hunk = first.get("diffHunk") or last.get("diffHunk")
        thread_line = thread.get("line") or first.get("line") or last.get("line")
        try:
            line_num = int(thread_line) if thread_line is not None else None
        except (TypeError, ValueError):
            line_num = None
        comment_count = int((thread.get("comments") or {}).get("totalCount") or len(comments) or 0)
        formatted.append(
            {
                "id": thread.get("id"),
                "file": thread.get("path") or first.get("path") or "",
                "line": thread_line,
                "quoted_code_lines": _quoted_code_lines(diff_hunk, line=line_num),
                "reviewer": ((first.get("author") or {}).get("login") or "").strip(),
                "resolved": bool(thread.get("isResolved")),
                "outdated": bool(thread.get("isOutdated")),
                "comment_snippet": _comment_snippet(body),
                "state": _thread_state(
                    is_outdated=bool(thread.get("isOutdated")),
                    is_resolved=bool(thread.get("isResolved")),
                    comment_count=comment_count,
                ),
            }
        )
    return formatted


def _fail_log_excerpt(output: dict[str, Any] | None) -> list[str]:
    if not isinstance(output, dict):
        return []
    chunks: list[str] = []
    for key in ("text", "summary", "title"):
        val = output.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val.strip())
    if not chunks:
        return []
    lines: list[str] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            lines.append(stripped)
            if len(lines) >= _FAIL_LOG_MAX_LINES:
                return lines
    return lines


def _extract_fail_lines_from_log(log_text: str) -> list[str]:
    if not log_text.strip():
        return []
    lines = [ln.rstrip() for ln in log_text.splitlines() if ln.strip()]
    if not lines:
        return []
    markers = ("##[error]", "Error:", "FAILED", "AssertionError", "Traceback")
    hit_indices = [i for i, ln in enumerate(lines) if any(m in ln for m in markers)]
    if hit_indices:
        center = hit_indices[0]
        start = max(0, center - 3)
        return lines[start : start + _FAIL_LOG_MAX_LINES]
    return lines[-_FAIL_LOG_MAX_LINES:]


def _fetch_actions_job_log(repo: str, job_id: str) -> str | None:
    owner, name = _split_repo(repo)
    endpoint = f"repos/{owner}/{name}/actions/jobs/{job_id}/logs"
    proc = run_hidden(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    return text or None


def _summarize_check_runs(
    runs: list[dict[str, Any]],
    *,
    repo: str | None = None,
    job_log_fetcher: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    fetcher = job_log_fetcher
    if fetcher is None and repo:

        def fetcher(job_id: str) -> str | None:  # type: ignore[misc]
            return _fetch_actions_job_log(repo, job_id)

    for run in runs or []:
        if not isinstance(run, dict):
            continue
        name = run.get("name") or run.get("app", {}).get("name") or "check"
        conclusion = (run.get("conclusion") or run.get("status") or "").lower()
        entry: dict[str, Any] = {"name": name, "conclusion": conclusion or None}
        if conclusion in ("failure", "timed_out", "cancelled", "action_required", "startup_failure"):
            excerpt = _fail_log_excerpt(run.get("output"))
            if not excerpt and fetcher:
                external_id = run.get("external_id")
                app_slug = ((run.get("app") or {}).get("slug") or "").lower()
                if external_id and app_slug == "github-actions":
                    log_text = fetcher(str(external_id))
                    if log_text:
                        excerpt = _extract_fail_lines_from_log(log_text)
            if excerpt:
                entry["log_excerpt"] = excerpt
        summaries.append(entry)
    return summaries


def _parse_closes_links(body: str | None) -> list[int]:
    return parse_closing_issue_numbers(body)


def _load_pr_graphql(client: PacketClient, repo: str, pr_number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $repo: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      body
      mergeStateStatus
      baseRefName
      headRefOid
      reviewDecision
      labels(first: 50) { nodes { name } }
      milestone { title }
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 10) {
            totalCount
            nodes {
              body
              path
              line
              diffHunk
              author { login }
            }
          }
        }
      }
    }
  }
}
""".strip()
    all_threads: list[dict[str, Any]] = []
    cursor: str | None = None
    has_next = True
    pr: dict[str, Any] = {}
    while has_next:
        payload = client.api(
            "graphql",
            method="POST",
            fields={
                "query": query,
                "owner": owner,
                "repo": name,
                "number": pr_number,
                "after": cursor,
            },
        )
        if payload and payload.get("errors"):
            raise GhApiError(json.dumps(payload.get("errors")))
        pr = (((payload or {}).get("data") or {}).get("repository") or {}).get("pullRequest") or {}
        if not pr:
            raise GhApiError("graphql pullRequest missing")
        block = pr.get("reviewThreads") or {}
        nodes = block.get("nodes") or []
        if isinstance(nodes, list):
            all_threads.extend(item for item in nodes if isinstance(item, dict))
        page_info = block.get("pageInfo") or {}
        has_next = bool(page_info.get("hasNextPage"))
        cursor = page_info.get("endCursor")
        if has_next and not cursor:
            break

    labels = [n.get("name") for n in (pr.get("labels") or {}).get("nodes") or [] if n.get("name")]
    milestone = pr.get("milestone")
    return {
        "body": pr.get("body") or "",
        "mergeStateStatus": pr.get("mergeStateStatus"),
        "baseRefName": pr.get("baseRefName") or "",
        "headRefOid": pr.get("headRefOid") or "",
        "labels": labels,
        "milestone": (milestone or {}).get("title") if isinstance(milestone, dict) else None,
        "reviewThreads": all_threads,
        "review_threads_complete": not has_next,
    }


def _behind_by(http: HttpClient, repo: str, base_ref: str, head_sha: str) -> int | None:
    owner, name = repo.split("/", 1)
    _, _, body = http.get(f"/repos/{owner}/{name}/compare/{base_ref}...{head_sha}", None)
    if isinstance(body, dict) and "behind_by" in body:
        try:
            return int(body.get("behind_by") or 0)
        except (TypeError, ValueError):
            return None
    return None


def _fetch_check_runs(http: HttpClient, repo: str, head_sha: str) -> list[dict[str, Any]]:
    owner, name = repo.split("/", 1)
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        _, _, body = http.get(
            f"/repos/{owner}/{name}/commits/{head_sha}/check-runs?per_page=100&page={page}",
            {"Accept": "application/vnd.github+json"},
        )
        page_runs = body.get("check_runs", []) if isinstance(body, dict) else []
        if not isinstance(page_runs, list):
            break
        runs.extend(item for item in page_runs if isinstance(item, dict))
        if len(page_runs) < 100:
            break
        page += 1
    return runs


def _apply_size_cap(packet: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
    """Shrink lists until canonical JSON fits ``max_bytes``; set ``truncated`` when trimmed."""

    working = dict(packet)
    working.pop("byte_size", None)

    def _fits(obj: dict[str, Any]) -> tuple[bool, str]:
        text = serialize_pr_packet(obj)
        return len(text.encode("utf-8")) <= max_bytes, text

    ok, _ = _fits(working)
    if ok:
        return _stamp_byte_size(working)

    working["truncated"] = True
    threads = list(working.get("review_threads") or [])
    checks = list(working.get("checks") or [])

    def _fit() -> bool:
        working["review_threads"] = threads
        working["checks"] = checks
        ok, _text = _fits(working)
        return ok

    while checks and not _fit():
        last = checks[-1]
        if isinstance(last, dict) and last.get("log_excerpt"):
            last = dict(last)
            excerpt = list(last.get("log_excerpt") or [])
            if len(excerpt) > 1:
                last["log_excerpt"] = excerpt[:-1]
                checks[-1] = last
                continue
        checks.pop()

    while threads and not _fit():
        threads.pop()

    if not _fit():
        marker = working.get("truncation_marker") or "…packet truncated…"
        working["truncation_marker"] = marker
        while not _fit() and len(marker) < 200:
            if threads:
                threads[:] = threads[: max(0, len(threads) - 1)]
            elif checks:
                checks[:] = checks[: max(0, len(checks) - 1)]
            else:
                break
            working["truncation_marker"] = marker
            _fit()

    return _stamp_byte_size(working)


def assemble_packet(
    *,
    repo: str,
    pr_number: int,
    graphql: dict[str, Any],
    head_sha: str,
    behind_by: int | None,
    checks: list[dict[str, Any]],
    probe_meta: dict[str, Any],
    max_bytes: int = DEFAULT_MAX_BYTES,
    job_log_fetcher: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    body = graphql.get("body") or ""
    packet: dict[str, Any] = {
        "repo": repo,
        "pr_number": pr_number,
        "facts": {
            "base_branch": graphql.get("baseRefName") or "",
            "head_sha": head_sha,
            "behind_by": behind_by,
            "mergeStateStatus": graphql.get("mergeStateStatus"),
            "labels": list(graphql.get("labels") or []),
            "milestone": graphql.get("milestone"),
            "closes_issues": _parse_closes_links(body),
        },
        "review_threads": _format_thread_nodes(graphql.get("reviewThreads") or []),
        "checks": _summarize_check_runs(checks, repo=repo, job_log_fetcher=job_log_fetcher),
        "probe": probe_meta,
        "truncation_marker": "…packet truncated…",
    }
    if graphql.get("review_threads_complete") is False:
        packet["review_threads_complete"] = False
    return _apply_size_cap(packet, max_bytes=max_bytes)


def build_pr_packet(
    pr_number: int,
    repo: str | None = None,
    *,
    client: PacketClient | None = None,
    http: HttpClient | None = None,
    probe_root: Path | str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    record_ledger: bool = False,
    turns: int | None = None,
    run_id: str | None = None,
    cloud_agent_id: str | None = None,
    ledger_base_dir: Path | str | None = None,
    snapshot: dict[str, Any] | None = None,
    job_log_fetcher: Callable[[str], str | None] | None = None,
) -> PrPacketResult:
    """Build (and optionally ledger-record) a PR evidence packet."""
    target = resolve_repo(repo)
    gh = client or GhClient()
    http_client = http or GhApiHttp()

    probe_path = packet_probe_state_path(target, pr_number, root=probe_root)
    prior_state = load_probe_state(probe_path) or ProbeState()
    delta_since = prior_state.last_checked_at or _DELTA_EPOCH
    probe = probe_pr(http_client, target, pr_number, prior_state)
    delta = fetch_delta(http_client, target, pr_number, prior_state, since=delta_since)
    delta_state = delta.get("new_state") or prior_state
    merged_state = replace(
        probe.new_state,
        last_issue_comment_id=delta_state.last_issue_comment_id,
        last_review_comment_id=delta_state.last_review_comment_id,
        last_review_id=delta_state.last_review_id,
    )
    save_probe_state(probe_path, merged_state)

    if snapshot is not None:
        graphql = snapshot.get("graphql") or {}
        head_sha = snapshot.get("head_sha") or graphql.get("headRefOid") or ""
        behind = snapshot.get("behind_by")
        checks = snapshot.get("checks") or []
    else:
        graphql = _load_pr_graphql(gh, target, pr_number)
        head_sha = probe.new_state.head_sha or graphql.get("headRefOid") or ""
        base_ref = graphql.get("baseRefName") or probe.new_state.base_ref or "main"
        behind = _behind_by(http_client, target, base_ref, head_sha) if head_sha else None
        checks = _fetch_check_runs(http_client, target, head_sha) if head_sha else []

    probe_meta = {
        "changed": probe.changed,
        "not_modified": probe.not_modified,
        "etag": probe.new_state.etag,
        "since_delta": {
            "issue_comments": len(delta.get("issue_comments") or []),
            "review_comments": len(delta.get("review_comments") or []),
            "reviews": len(delta.get("reviews") or []),
        },
        "recommended_backoff_seconds": Backoff().next_interval(probe.changed),
    }

    packet = assemble_packet(
        repo=target,
        pr_number=pr_number,
        graphql=graphql,
        head_sha=head_sha,
        behind_by=behind,
        checks=checks,
        probe_meta=probe_meta,
        max_bytes=max_bytes,
        job_log_fetcher=job_log_fetcher,
    )
    json_text = serialize_pr_packet(packet)
    byte_size = packet.get("byte_size", len(json_text.encode("utf-8")))

    ledger_entry = None
    if record_ledger:
        from .ledger import record_spend_interval

        ledger_entry = record_spend_interval(
            run_id=run_id,
            cloud_agent_id=cloud_agent_id,
            related_pr=pr_number,
            turns=turns,
            handoff_packet_size=byte_size,
            handoff_packet_unit="bytes",
            lifecycle_task_type="pr_packet",
            session="pr-packet",
            base_dir=Path(ledger_base_dir) if ledger_base_dir else None,
        )

    return PrPacketResult(
        packet=packet,
        json_text=json_text,
        byte_size=byte_size,
        probe_changed=probe.changed,
        not_modified=probe.not_modified,
        ledger_entry=ledger_entry,
    )
