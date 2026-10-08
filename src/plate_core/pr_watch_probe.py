"""Cheap PR change detection for babysit watch loops (#1078).

Uses conditional GET (``If-None-Match``) on the pull request resource so an
unchanged PR costs one PR-resource round-trip per probe. Compares ``head.sha``,
``updated_at``, and ``mergeable_state``; commit status and check runs are
polled on every probe so CI-only transitions are detected.

Default HTTP client: ``gh api -i`` via :func:`plate_core.procutil.run_hidden`,
which reliably returns ``304 Not Modified`` with response headers (including
``ETag``). Tests inject a fake ``get(path, headers) -> (status, headers, json)``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from .procutil import run_hidden

_REPO_RE = re.compile(r"^([^/]+)/([^/]+)$")


def _split_repo(repo: str) -> tuple[str, str]:
    m = _REPO_RE.match(repo.strip())
    if not m:
        raise ValueError(f"repo must be owner/name, got: {repo!r}")
    return m.group(1), m.group(2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _header_get(headers: Mapping[str, str], name: str) -> str | None:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


@dataclass
class ProbeState:
    """Persisted probe snapshot (JSON-serializable)."""

    etag: str | None = None
    head_sha: str | None = None
    updated_at: str | None = None
    mergeable_state: str | None = None
    ci_state: str | None = None
    last_checked_at: str | None = None
    last_issue_comment_id: int = 0
    last_review_comment_id: int = 0
    last_review_id: int = 0


@dataclass
class ProbeResult:
    changed: bool
    not_modified: bool
    pr: dict[str, Any] | None
    new_state: ProbeState


class HttpClient(Protocol):
    def get(self, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, dict[str, str], Any]:
        """GET ``path`` (e.g. ``/repos/o/r/pulls/1``). Returns status, headers, JSON body."""


def probe_state_path(repo: str, pr: int, root: Path | str | None = None) -> Path:
    owner, name = _split_repo(repo)
    base = Path(root) if root is not None else Path.cwd()
    return base / ".agentic" / "babysit" / f"{owner}-{name}-{pr}.probe.json"


def load_probe_state(path: Path | str) -> ProbeState | None:
    p = Path(path)
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return ProbeState(**data)


def save_probe_state(path: Path | str, state: ProbeState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_gh_api_i(raw: str) -> tuple[int, dict[str, str], Any]:
    """Parse ``gh api -i`` combined header/body output."""
    if not raw.strip():
        raise RuntimeError("empty gh api -i response")
    parts = raw.split("\r\n\r\n")
    if len(parts) == 1:
        parts = raw.split("\n\n", 1)
    header_block = parts[0]
    body = parts[1] if len(parts) > 1 else ""
    lines = header_block.replace("\r\n", "\n").split("\n")
    status_line = lines[0]
    m = re.match(r"HTTP/\S+\s+(\d+)", status_line)
    if not m:
        raise RuntimeError(f"could not parse status line: {status_line!r}")
    status = int(m.group(1))
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    parsed: Any = {}
    if body.strip():
        parsed = json.loads(body)
    return status, headers, parsed


class GhApiHttp:
    """Default :class:`HttpClient` using authenticated ``gh api -i``."""

    def get(self, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, dict[str, str], Any]:
        endpoint = path.lstrip("/")
        cmd = ["gh", "api", endpoint, "-i"]
        for key, value in (headers or {}).items():
            cmd.extend(["-H", f"{key}: {value}"])
        proc = run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if proc.returncode != 0:
            try:
                response = _parse_gh_api_i(proc.stdout or "")
                if response[0] == 304:
                    return response
            except (RuntimeError, json.JSONDecodeError):
                pass
            err = (proc.stderr or proc.stdout or "gh api failed").strip()
            raise RuntimeError(err)
        return _parse_gh_api_i(proc.stdout or "")


def probe_pr(
    http: HttpClient,
    repo: str,
    pr: int,
    state: ProbeState | None,
) -> ProbeResult:
    """Probe PR for changes using conditional GET and optional status fetch."""
    state = state or ProbeState()
    owner, name = _split_repo(repo)
    pull_path = f"/repos/{owner}/{name}/pulls/{pr}"
    req_headers: dict[str, str] = {}
    if state.etag:
        req_headers["If-None-Match"] = state.etag

    checked_at = _utc_now_iso()
    status, resp_headers, body = http.get(pull_path, req_headers)

    if status not in (200, 304):
        raise RuntimeError(f"unexpected status {status} for {pull_path}")

    etag = _header_get(resp_headers, "etag") or state.etag
    if status == 200:
        head_sha = (body.get("head") or {}).get("sha")
        updated_at = body.get("updated_at")
        mergeable_state = body.get("mergeable_state")
    else:
        head_sha = state.head_sha
        updated_at = state.updated_at
        mergeable_state = state.mergeable_state

    ci_state = state.ci_state
    if head_sha:
        _, _, status_json = http.get(f"/repos/{owner}/{name}/commits/{head_sha}/status", None)
        _, _, checks_json = http.get(
            f"/repos/{owner}/{name}/commits/{head_sha}/check-runs",
            {"Accept": "application/vnd.github+json"},
        )
        status_state = status_json.get("state") if isinstance(status_json, dict) else None
        check_runs = checks_json.get("check_runs", []) if isinstance(checks_json, dict) else []
        check_states = [
            "pending"
            if str(run.get("status") or "").lower() != "completed"
            else str(run.get("conclusion") or "").lower()
            for run in check_runs
            if isinstance(run, dict)
        ]
        if "pending" in check_states or str(status_state or "").lower() in ("pending", "expected"):
            ci_state = "pending"
        elif any(value in ("failure", "timed_out", "cancelled", "action_required", "startup_failure") for value in check_states):
            ci_state = "failure"
        elif str(status_state or "").lower() in ("failure", "error"):
            ci_state = str(status_state).lower()
        elif status_state or check_states:
            ci_state = "success"

    changed = (
        head_sha != state.head_sha
        or updated_at != state.updated_at
        or mergeable_state != state.mergeable_state
        or ci_state != state.ci_state
    )

    new_state = ProbeState(
        etag=etag,
        head_sha=head_sha,
        updated_at=updated_at,
        mergeable_state=mergeable_state,
        ci_state=ci_state,
        last_checked_at=checked_at,
        last_issue_comment_id=state.last_issue_comment_id,
        last_review_comment_id=state.last_review_comment_id,
        last_review_id=state.last_review_id,
    )
    return ProbeResult(changed=changed, not_modified=status == 304, pr=body if status == 200 else None, new_state=new_state)


def _filter_since(items: list[dict[str, Any]], last_id: int) -> list[dict[str, Any]]:
    out = [item for item in items if int(item.get("id") or 0) > last_id]
    out.sort(key=lambda x: int(x.get("id") or 0))
    return out


def fetch_delta(
    http: HttpClient,
    repo: str,
    pr: int,
    state: ProbeState | None,
) -> dict[str, Any]:
    """Return only new issue comments, review comments, and reviews since last probe."""
    state = state or ProbeState()
    owner, name = _split_repo(repo)
    since = state.last_checked_at or "1970-01-01T00:00:00Z"

    _, _, issue_comments = http.get(
        f"/repos/{owner}/{name}/issues/{pr}/comments?since={since}",
        None,
    )
    _, _, review_comments = http.get(
        f"/repos/{owner}/{name}/pulls/{pr}/comments?since={since}",
        None,
    )
    reviews: list[dict[str, Any]] = []
    page = 1
    while True:
        _, _, page_reviews = http.get(
            f"/repos/{owner}/{name}/pulls/{pr}/reviews?per_page=100&page={page}",
            None,
        )
        if not isinstance(page_reviews, list):
            break
        reviews.extend(page_reviews)
        if len(page_reviews) < 100:
            break
        page += 1

    ic_list = issue_comments if isinstance(issue_comments, list) else []
    rc_list = review_comments if isinstance(review_comments, list) else []
    return {
        "issue_comments": _filter_since(ic_list, state.last_issue_comment_id),
        "review_comments": _filter_since(rc_list, state.last_review_comment_id),
        "reviews": _filter_since(reviews, state.last_review_id),
    }
