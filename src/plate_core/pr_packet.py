"""Compact PR evidence packets for agent handoffs (#1364).

Builds a size-capped JSON bundle (review threads, failing check excerpts, PR facts)
so downstream agents can act on feedback without re-reading raw bot comments or full
CI logs. Reuses babysit watch probe state (ETag / conditional GET) and REST ``since``
deltas from ``pr_watch_probe`` (#1077–#1081). Optional spend-ledger rows record
``handoff_packet_size`` and ``turns`` (#1352 / #1358).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .integration_close import parse_closing_issue_numbers
from .pr_watch_backoff import Backoff
from .pr_watch_probe import (
    GhApiHttp,
    HttpClient,
    ProbeState,
    fetch_delta,
    load_probe_state,
    probe_pr,
    probe_state_path,
    save_probe_state,
)

DEFAULT_MAX_BYTES = 6144
COMMENT_SNIPPET_LEN = 400
_FAIL_LOG_MAX_LINES = 16
_QUOTED_CODE_MAX_LINES = 12


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


def _comment_snippet(body: str | None) -> str:
    text = (body or "").strip()
    if len(text) <= COMMENT_SNIPPET_LEN:
        return text
    return text[:COMMENT_SNIPPET_LEN] + "…"


def _quoted_code_lines(diff_hunk: str | None) -> list[str]:
    if not diff_hunk:
        return []
    out: list[str] = []
    for line in diff_hunk.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-", " ")):
            out.append(line)
        if len(out) >= _QUOTED_CODE_MAX_LINES:
            break
    return out


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
        comment_count = int((thread.get("comments") or {}).get("totalCount") or len(comments) or 0)
        formatted.append(
            {
                "id": thread.get("id"),
                "file": thread.get("path") or first.get("path") or "",
                "line": thread.get("line") or first.get("line"),
                "quoted_code_lines": _quoted_code_lines(diff_hunk),
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


def _summarize_check_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for run in runs or []:
        if not isinstance(run, dict):
            continue
        name = run.get("name") or run.get("app", {}).get("name") or "check"
        conclusion = (run.get("conclusion") or run.get("status") or "").lower()
        entry: dict[str, Any] = {"name": name, "conclusion": conclusion or None}
        if conclusion in ("failure", "timed_out", "cancelled", "action_required", "startup_failure"):
            excerpt = _fail_log_excerpt(run.get("output"))
            if excerpt:
                entry["log_excerpt"] = excerpt
        summaries.append(entry)
    return summaries


def _parse_closes_links(body: str | None) -> list[int]:
    return parse_closing_issue_numbers(body)


def _load_pr_graphql(client: PacketClient, repo: str, pr_number: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $repo: String!, $number: Int!) {
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
      reviewThreads(first: 100) {
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
    payload = client.api(
        "graphql",
        method="POST",
        fields={"query": query, "owner": owner, "repo": name, "number": pr_number},
    )
    if payload and payload.get("errors"):
        raise GhApiError(json.dumps(payload.get("errors")))
    pr = (((payload or {}).get("data") or {}).get("repository") or {}).get("pullRequest") or {}
    if not pr:
        raise GhApiError("graphql pullRequest missing")
    labels = [n.get("name") for n in (pr.get("labels") or {}).get("nodes") or [] if n.get("name")]
    milestone = pr.get("milestone")
    return {
        "body": pr.get("body") or "",
        "mergeStateStatus": pr.get("mergeStateStatus"),
        "baseRefName": pr.get("baseRefName") or "",
        "headRefOid": pr.get("headRefOid") or "",
        "labels": labels,
        "milestone": (milestone or {}).get("title") if isinstance(milestone, dict) else None,
        "reviewThreads": (pr.get("reviewThreads") or {}).get("nodes") or [],
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
    """Shrink lists until JSON fits ``max_bytes``; set ``truncated`` when trimmed."""

    def _dump(obj: dict[str, Any]) -> str:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

    working = dict(packet)
    text = _dump(working)
    if len(text.encode("utf-8")) <= max_bytes:
        working["byte_size"] = len(text.encode("utf-8"))
        return working

    working["truncated"] = True
    threads = list(working.get("review_threads") or [])
    checks = list(working.get("checks") or [])

    def _fit() -> bool:
        nonlocal text
        working["review_threads"] = threads
        working["checks"] = checks
        text = _dump(working)
        return len(text.encode("utf-8")) <= max_bytes

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

    working["byte_size"] = len(_dump(working).encode("utf-8"))
    return working


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
        "checks": _summarize_check_runs(checks),
        "probe": probe_meta,
        "truncation_marker": "…packet truncated…",
    }
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
) -> PrPacketResult:
    """Build (and optionally ledger-record) a PR evidence packet."""
    target = resolve_repo(repo)
    gh = client or GhClient()
    http_client = http or GhApiHttp()

    probe_path = probe_state_path(target, pr_number, root=probe_root)
    prior_state = load_probe_state(probe_path) or ProbeState()
    probe = probe_pr(http_client, target, pr_number, prior_state)
    save_probe_state(probe_path, probe.new_state)
    delta = fetch_delta(http_client, target, pr_number, probe.new_state)
    save_probe_state(probe_path, delta.get("new_state") or probe.new_state)

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
    )
    json_text = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    byte_size = len(json_text.encode("utf-8"))

    ledger_entry = None
    if record_ledger:
        from .ledger import record_spend_interval

        ledger_entry = record_spend_interval(
            run_id=run_id,
            cloud_agent_id=cloud_agent_id,
            related_pr=pr_number,
            turns=turns,
            handoff_packet_size=packet.get("byte_size", byte_size),
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
