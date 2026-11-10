"""Local JSONL issue lifecycle event log (#1422 / #1383).

Append-only log under ``.agentic/events/`` (git-ignored). Each clone keeps a
``writer_id`` (ULID). ``seq`` is monotonic per (repository, ``writer_id``).
``event_key`` dedupes transition retries: ``<transition_id>:<type>``.

See issue #1422 for the full contract. Scrubbing removes obvious secret/token
material from string fields before append; it is not an injection defence.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Iterator, Literal

from .state_store import _lockfile, locked_json

__all__ = [
    "ISSUE_LIFECYCLE_SCHEMA_VERSION",
    "EventType",
    "append_issue_lifecycle_event",
    "iterate_issue_lifecycle_events",
    "mint_ulid",
    "scrub_issue_lifecycle_payload",
]

ISSUE_LIFECYCLE_SCHEMA_VERSION = 1

# Crockford base32 (no I L O U).
_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

EventType = Literal[
    "state_transition",
    "pm_decision",
    "approval",
    "lease_take",
    "lease_release",
    "budget_reserve",
    "spend_settle",
    "spend_run",
    "pr_opened",
    "pr_updated",
    "pr_merged",
    "pr_closed",
    "ci_gate",
    "error",
    "retry",
    "abandon",
]

_REPO_SLUG_RE = re.compile(r"^[^/]+/[^/]+$")

# Token / credential patterns (scrubbed to a fixed placeholder).
_SCRUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"ghp_[A-Za-z0-9]{20,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"ghu_[A-Za-z0-9]{20,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"ghs_[A-Za-z0-9]{20,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]+", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{10,}\b", re.I), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9]{10,}", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]+", re.I), "[REDACTED_TOKEN]"),
)

_SUMMARY_MAX = 500


def _scrub_str(text: str) -> str:
    """Apply token redactions to a single string."""
    s = text
    for pattern, repl in _SCRUB_PATTERNS:
        s = pattern.sub(repl, s)
    return s


def mint_ulid(when_ms: int | None = None) -> str:
    """Return a 26-character ULID (time ordering + randomness)."""
    ts = int(time.time() * 1000) if when_ms is None else int(when_ms)
    if ts < 0 or ts > 0xFFFFFFFFFFFF:
        raise ValueError("timestamp out of ULID range")
    rnd = secrets.token_bytes(10)
    ms48 = ts & 0xFFFFFFFFFFFF
    buf = ms48.to_bytes(6, "big") + rnd
    if len(buf) != 16:
        raise RuntimeError("internal ULID payload size")
    # Encode 128 bits as 26 Crockford base32 chars (5 bits per char).
    bits = int.from_bytes(buf, "big")
    chars: list[str] = []
    for _ in range(26):
        chars.append(_BASE32[bits & 31])
        bits >>= 5
    return "".join(reversed(chars))


def _mint_writer_id() -> str:
    """ULID for a new clone ``writer_id`` file (indirection for tests)."""
    return mint_ulid()


def _repo_slug(repo: str) -> str:
    s = str(repo).strip()
    if not _REPO_SLUG_RE.match(s):
        raise ValueError(f"repo must be owner/name, got {repo!r}")
    owner, name = s.split("/", 1)
    return f"{owner}-{name}"


def _events_root(plate_root: Path | None) -> Path:
    root = Path.cwd() if plate_root is None else Path(plate_root)
    return root / ".agentic" / "events"


def _writer_id_path(plate_root: Path | None) -> Path:
    return _events_root(plate_root) / "writer_id"


def _read_writer_id_file(path: Path) -> str | None:
    """Return the writer id if the file exists and looks like a ULID."""
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if len(raw) == 26 and raw.isalnum():
        return raw
    return None


def _unlink_corrupt_writer_id(path: Path) -> None:
    """Remove empty or invalid ``writer_id`` (interrupted create or truncation).

    Only call while holding ``writer_id.lock``. A valid 26-char ULID line is
    never removed.
    """
    if not path.exists():
        return
    if _read_writer_id_file(path) is not None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _get_or_create_writer_id(plate_root: Path | None) -> str:
    """Return the stable writer id for this clone, creating it if needed.

    Uses a repo-wide lock file plus ``O_CREAT|O_EXCL`` so concurrent processes
    cannot mint two ids for the same ``writer_id`` path. If a process crashes
    after ``O_EXCL`` but before the ULID line is written, the path can exist
    empty or truncated; that is detected and removed under the same lock, then
    initialization is retried.
    """
    path = _writer_id_path(plate_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")

    with _lockfile(lock_path):
        max_rounds = 32
        for _ in range(max_rounds):
            existing = _read_writer_id_file(path)
            if existing is not None:
                return existing
            _unlink_corrupt_writer_id(path)
            try:
                fd = os.open(
                    str(path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
            except FileExistsError:
                # Peer or prior round left a file; re-read after unlink or valid fill.
                continue
            try:
                wid = _mint_writer_id()
                data = (wid + "\n").encode("ascii")
                os.write(fd, data)
                os.fsync(fd)
                return wid
            finally:
                os.close(fd)
        raise RuntimeError(
            f"writer_id at {path} could not be initialized after {max_rounds} attempts"
        )


def scrub_issue_lifecycle_payload(value: Any) -> Any:
    """Recursively scrub strings in JSON-like structures."""

    if isinstance(value, str):
        return _scrub_str(value)
    if isinstance(value, dict):
        return {str(k): scrub_issue_lifecycle_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_issue_lifecycle_payload(v) for v in value]
    if isinstance(value, tuple):
        return tuple(scrub_issue_lifecycle_payload(v) for v in value)
    return value


def _truncate_summary(summary: str) -> str:
    s = summary
    if len(s) <= _SUMMARY_MAX:
        return s
    return s[: _SUMMARY_MAX - 1] + "…"


def _seq_path(plate_root: Path | None, repo: str, writer_id: str) -> Path:
    return _events_root(plate_root) / _repo_slug(repo) / writer_id / "seq.json"


def _log_path(plate_root: Path | None, repo: str, issue_number: int) -> Path:
    return _events_root(plate_root) / _repo_slug(repo) / f"issue-{int(issue_number)}.jsonl"


def _compute_event_key(
    *,
    event_type: str,
    transition_id: str | None,
) -> str:
    if transition_id is not None and str(transition_id).strip():
        # Same redaction as payload fields so secrets cannot leak via ``event_key``.
        tid = _scrub_str(str(transition_id).strip())
        return f"{tid}:{event_type}"
    return mint_ulid()


def append_issue_lifecycle_event(
    repo: str,
    issue_number: int,
    *,
    event_type: str,
    summary: str,
    transition_id: str | None = None,
    links: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
    plate_root: Path | str | None = None,
) -> dict[str, Any]:
    """Append one scrubbed JSONL event; return the stored record (with seq, event_id).

    Uses ``state_store.locked_json`` for the per-repo sequence counter and an
    exclusive lock on the log file during append so concurrent writers do not
    interleave torn lines.
    """
    root = Path(plate_root) if plate_root is not None else None
    writer_id = _get_or_create_writer_id(root)
    event_id = mint_ulid()

    raw_record: dict[str, Any] = {
        "schema_version": ISSUE_LIFECYCLE_SCHEMA_VERSION,
        "event_id": event_id,
        "repo": str(repo).strip(),
        "issue": int(issue_number),
        "writer_id": writer_id,
        "type": str(event_type),
        "summary": str(summary),
    }
    if links:
        raw_record["links"] = dict(links)
    if extra:
        raw_record["extra"] = dict(extra)

    scrubbed = scrub_issue_lifecycle_payload(raw_record)
    assert isinstance(scrubbed, dict)
    summary_scrubbed = _truncate_summary(str(scrubbed.get("summary", "")))
    scrubbed["summary"] = summary_scrubbed

    event_key = _compute_event_key(event_type=str(event_type), transition_id=transition_id)
    scrubbed["event_key"] = event_key

    log = _log_path(root, repo, issue_number)
    seq_json = _seq_path(root, repo, writer_id)
    lock_path = log.with_suffix(".jsonl.lock")

    with _lockfile(lock_path):
        with locked_json(
            seq_json,
            missing_factory=lambda: {"next_seq": 1},
        ) as st:
            seq = int(st.get("next_seq", 1))
            st["next_seq"] = seq + 1
        scrubbed["seq"] = seq

        line = json.dumps(scrubbed, ensure_ascii=False, sort_keys=True) + "\n"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "ab") as f:
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())

    return scrubbed


def iterate_issue_lifecycle_events(
    repo: str,
    issue_number: int,
    *,
    plate_root: Path | str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield events for ``repo`` + ``issue_number`` in append order (stable for one file)."""
    root = Path(plate_root) if plate_root is not None else None
    log = _log_path(root, repo, issue_number)
    if log.is_file():
        yield from _iter_jsonl_file(log)


def _iter_jsonl_file(path: Path) -> Iterator[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row
