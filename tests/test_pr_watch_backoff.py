"""Tests for pr_watch_backoff (#1079)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from plate_core.pr_watch_backoff import Backoff, SystemWatchClock, should_stop


class FakeWatchClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


def test_backoff_quiet_ticks_double_up_to_cap() -> None:
    b = Backoff(min_interval=60, max_interval=1800, factor=2.0)
    assert b.next_interval(False) == 60
    assert b.next_interval(False) == 120
    assert b.next_interval(False) == 240
    assert b.next_interval(False) == 480
    assert b.next_interval(False) == 960
    assert b.next_interval(False) == 1800
    assert b.next_interval(False) == 1800


def test_backoff_change_resets_interval() -> None:
    b = Backoff(min_interval=60, max_interval=1800, factor=2.0)
    b.next_interval(False)
    b.next_interval(False)
    assert b.next_interval(True) == 60
    assert b.next_interval(False) == 60
    assert b.next_interval(False) == 120


def test_should_stop_merged() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = start + timedelta(hours=1)
    assert should_stop({"merged": True, "state": "MERGED"}, start, now, 24.0) == "merged"
    assert should_stop({"mergedAt": "2026-01-01T12:00:00Z"}, start, now, 24.0) == "merged"


def test_should_stop_closed() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = start + timedelta(hours=1)
    assert should_stop({"state": "CLOSED"}, start, now, 24.0) == "closed"
    assert should_stop({"state": "closed", "merged": False}, start, now, 24.0) == "closed"
    assert should_stop({"closedAt": "2026-01-01T12:00:00Z"}, start, now, 24.0) == "closed"


def test_should_stop_max_hours_exceeded() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = start + timedelta(hours=5)
    pr = {"state": "OPEN"}
    assert should_stop(pr, start, now, max_hours=4.0) == "max_hours_exceeded"
    assert should_stop(pr, start, now, max_hours=5.0) == "max_hours_exceeded"
    assert should_stop(pr, start, now - timedelta(seconds=1), max_hours=5.0) is None


def test_should_stop_open_pr_within_budget() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = start + timedelta(minutes=30)
    assert should_stop({"state": "OPEN"}, start, now, max_hours=8.0) is None


def test_system_watch_clock_advances_with_fake_pattern() -> None:
    clock = FakeWatchClock(datetime(2026, 6, 1, tzinfo=timezone.utc))
    t0 = clock.now()
    clock.sleep(90)
    assert clock.now() == t0 + timedelta(seconds=90)


def test_system_watch_clock_is_constructible() -> None:
    assert SystemWatchClock().now().tzinfo is not None
