"""Spend caps for ``gh plate pr babysit --watch`` (#1081).

Persisted per-PR ledgers under ``.agentic/babysit/`` so long-running watch loops
can stop after max wakes or max elapsed hours without re-polling GitHub every tick.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CAP_NOTE_MARKER = "<!-- plate-babysit-cap -->"


@dataclass
class WatchCaps:
    max_wakes: int = 10
    max_hours: float = 12.0


@dataclass
class CapLedger:
    started_at: str
    wakes: int = 0
    paused_reason: str | None = None


def _repo_slug(repo: str) -> str:
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"repo must be owner/name, got: {repo!r}")
    owner, name = parts
    if any(part in {".", ".."} or re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None for part in parts):
        raise ValueError(f"repo must be owner/name, got: {repo!r}")
    return f"{owner}-{name}"


def caps_path(repo: str, pr: int, root: Path | str | None = None) -> Path:
    """Path to the JSON ledger for ``repo`` PR ``pr``."""
    base = Path(root) if root is not None else Path.cwd()
    slug = _repo_slug(repo)
    return base / ".agentic" / "babysit" / f"{slug}-{pr}.caps.json"


def _parse_started_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.isoformat()


def load_ledger(path: Path, *, now: datetime | None = None) -> CapLedger:
    """Load a ledger from ``path``, or return a fresh one when missing."""
    if not path.is_file():
        t = now or datetime.now().astimezone()
        return CapLedger(started_at=_iso(t), wakes=0, paused_reason=None)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return CapLedger(
        started_at=str(raw["started_at"]),
        wakes=int(raw.get("wakes", 0)),
        paused_reason=raw.get("paused_reason"),
    )


def save_ledger(path: Path, ledger: CapLedger) -> None:
    """Persist ``ledger`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(ledger), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record_wake(ledger: CapLedger) -> None:
    """Increment the wake counter."""
    ledger.wakes += 1


def check_caps(ledger: CapLedger, caps: WatchCaps, now: datetime) -> str | None:
    """Return a pause reason when a cap is exceeded, else ``None``."""
    if ledger.paused_reason:
        return ledger.paused_reason

    started = _parse_started_at(ledger.started_at)
    if started.tzinfo is None and now.tzinfo is not None:
        started = started.replace(tzinfo=now.tzinfo)
    elif started.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=started.tzinfo)

    elapsed_h = (now - started).total_seconds() / 3600.0
    if elapsed_h >= caps.max_hours:
        reason = f"max hours reached ({caps.max_hours:g}h)"
        ledger.paused_reason = reason
        return reason

    if ledger.wakes >= caps.max_wakes:
        reason = f"max wakes reached ({caps.max_wakes})"
        ledger.paused_reason = reason
        return reason

    return None


def cap_note_body(reason: str, ledger: CapLedger, caps: WatchCaps) -> str:
    """PR comment body when babysitting pauses for a cap."""
    now = datetime.now(timezone.utc).astimezone()
    status = status_line(ledger, caps, now)
    return (
        f"{CAP_NOTE_MARKER}\n"
        f"Babysit watch paused: {reason}.\n"
        f"{status}\n"
        "Start a new watch budget with "
        "`gh plate pr babysit <n> --watch --reset-caps` (replace `<n>` with this PR number)."
    )


def _comment_body(comment: Any) -> str:
    if isinstance(comment, str):
        return comment
    if isinstance(comment, dict):
        return str(comment.get("body") or "")
    return str(comment)


def has_cap_note(comments: Iterable[Any]) -> bool:
    """True if any comment already contains the cap marker (dedupe)."""
    return any(CAP_NOTE_MARKER in _comment_body(c) for c in comments)


def status_line(ledger: CapLedger, caps: WatchCaps, now: datetime) -> str:
    """Human-readable cap usage, e.g. ``wakes 3/10, 2.5h/12h``."""
    started = _parse_started_at(ledger.started_at)
    if started.tzinfo is None and now.tzinfo is not None:
        started = started.replace(tzinfo=now.tzinfo)
    elif started.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=started.tzinfo)
    elapsed_h = max(0.0, (now - started).total_seconds() / 3600.0)
    if elapsed_h < 0.05:
        hours_fmt = "0h"
    elif abs(elapsed_h - round(elapsed_h)) > 0.05:
        hours_fmt = f"{elapsed_h:.1f}h"
    else:
        hours_fmt = f"{elapsed_h:g}h"
    max_h_fmt = f"{caps.max_hours:g}h"
    return f"wakes {ledger.wakes}/{caps.max_wakes}, {hours_fmt}/{max_h_fmt}"
