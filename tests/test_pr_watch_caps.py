"""Tests for pr_watch_caps spend limits (#1081)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from plate_core.pr_watch_caps import (
    CAP_NOTE_MARKER,
    CapLedger,
    WatchCaps,
    cap_note_body,
    caps_path,
    check_caps,
    has_cap_note,
    load_ledger,
    record_wake,
    save_ledger,
    status_line,
)

UTC = timezone.utc


def test_caps_path_uses_owner_repo_slug(tmp_path: Path) -> None:
    path = caps_path("acme/widgets", 42, root=tmp_path)
    assert path == tmp_path / ".agentic" / "babysit" / "acme-widgets-42.caps.json"


@pytest.mark.parametrize("repo", ["owner/repo/extra", "/repo", "owner/", "../repo", "owner/../../outside"])
def test_caps_path_rejects_invalid_repo_slug(repo: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        caps_path(repo, 42, root=tmp_path)


def test_ledger_round_trip(tmp_path: Path) -> None:
    path = caps_path("acme/widgets", 1, root=tmp_path)
    started = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat(), wakes=2, paused_reason=None)
    save_ledger(path, ledger)
    loaded = load_ledger(path)
    assert loaded == ledger


def test_load_ledger_creates_fresh_when_missing(tmp_path: Path) -> None:
    path = caps_path("acme/widgets", 9, root=tmp_path)
    now = datetime(2026, 10, 7, 8, 30, tzinfo=UTC)
    ledger = load_ledger(path, now=now)
    assert ledger.wakes == 0
    assert ledger.paused_reason is None
    assert ledger.started_at == now.isoformat()


def test_check_caps_max_wakes() -> None:
    caps = WatchCaps(max_wakes=3, max_hours=100.0)
    started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat(), wakes=0)
    now = started + timedelta(minutes=5)

    for _ in range(2):
        record_wake(ledger)
        assert check_caps(ledger, caps, now) is None

    record_wake(ledger)
    reason = check_caps(ledger, caps, now)
    assert reason is not None
    assert "max wakes" in reason
    assert ledger.paused_reason == reason


def test_check_caps_max_hours() -> None:
    caps = WatchCaps(max_wakes=100, max_hours=2.0)
    started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat(), wakes=1)
    now = started + timedelta(hours=2, minutes=1)

    reason = check_caps(ledger, caps, now)
    assert reason is not None
    assert "max hours" in reason


def test_status_line_format() -> None:
    caps = WatchCaps(max_wakes=10, max_hours=12.0)
    started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat(), wakes=3)
    now = started + timedelta(hours=2, minutes=30)
    assert status_line(ledger, caps, now) == "wakes 3/10, 2.5h/12h"


def test_status_line_rounds_tiny_elapsed_time_to_zero() -> None:
    caps = WatchCaps()
    started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat())
    assert status_line(ledger, caps, started + timedelta(microseconds=1)) == "wakes 0/10, 0h/12h"


def test_cap_note_body_includes_marker_and_resume() -> None:
    caps = WatchCaps()
    started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    ledger = CapLedger(started_at=started.isoformat(), wakes=10, paused_reason="max wakes reached (10)")
    body = cap_note_body(ledger.paused_reason, ledger, caps)
    assert body.startswith(CAP_NOTE_MARKER)
    assert "Babysit watch paused" in body
    assert "gh plate pr babysit <n> --watch --reset-caps" in body
    assert "wakes 10/10" in body


def test_has_cap_note_dedupe() -> None:
    assert has_cap_note([{"body": "unrelated"}]) is False
    assert has_cap_note([{"body": f"{CAP_NOTE_MARKER}\npaused"}]) is True
    assert has_cap_note([f"prefix {CAP_NOTE_MARKER} suffix"]) is True
