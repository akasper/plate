"""Tests for pr_watch_caps spend limits (#1081)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


class TestPrWatchCaps(unittest.TestCase):
    def test_caps_path_uses_owner_repo_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = caps_path("acme/widgets", 42, root=root)
            self.assertEqual(
                path,
                root / ".agentic" / "babysit" / "4-acme-7-widgets-42.caps.json",
            )
            self.assertNotEqual(
                caps_path("a-b/c", 42, root=root),
                caps_path("a/b-c", 42, root=root),
            )

    def test_caps_path_rejects_invalid_repo_slug(self) -> None:
        invalid_repos = [
            "owner/repo/extra",
            "/repo",
            "owner/",
            "../repo",
            "owner/../../outside",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for repo in invalid_repos:
                with self.subTest(repo=repo):
                    with self.assertRaises(ValueError):
                        caps_path(repo, 42, root=root)

    def test_ledger_round_trip_keeps_saved_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = caps_path("acme/widgets", 3, root=Path(tmp))
            ledger = CapLedger(
                started_at="2026-10-07T00:00:00+00:00",
                wakes=1,
                max_wakes=2,
                max_hours=4.0,
            )
            save_ledger(path, ledger)
            self.assertEqual(load_ledger(path), ledger)

    def test_ledger_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = caps_path("acme/widgets", 1, root=root)
            started = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
            ledger = CapLedger(started_at=started.isoformat(), wakes=2, paused_reason=None)
            save_ledger(path, ledger)
            loaded = load_ledger(path)
            self.assertEqual(loaded, ledger)

    def test_load_ledger_creates_fresh_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = caps_path("acme/widgets", 9, root=root)
            now = datetime(2026, 10, 7, 8, 30, tzinfo=UTC)
            ledger = load_ledger(path, now=now)
            self.assertEqual(ledger.wakes, 0)
            self.assertIsNone(ledger.paused_reason)
            self.assertEqual(ledger.started_at, now.isoformat())

    def test_check_caps_max_wakes(self) -> None:
        caps = WatchCaps(max_wakes=3, max_hours=100.0)
        started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
        ledger = CapLedger(started_at=started.isoformat(), wakes=0)
        now = started + timedelta(minutes=5)

        for _ in range(2):
            record_wake(ledger)
            self.assertIsNone(check_caps(ledger, caps, now))

        record_wake(ledger)
        reason = check_caps(ledger, caps, now)
        self.assertIsNotNone(reason)
        self.assertIn("max wakes", reason)
        self.assertEqual(ledger.paused_reason, reason)

    def test_check_caps_max_hours(self) -> None:
        caps = WatchCaps(max_wakes=100, max_hours=2.0)
        started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
        ledger = CapLedger(started_at=started.isoformat(), wakes=1)
        now = started + timedelta(hours=2, minutes=1)

        reason = check_caps(ledger, caps, now)
        self.assertIsNotNone(reason)
        self.assertIn("max hours", reason)

    def test_status_line_format(self) -> None:
        caps = WatchCaps(max_wakes=10, max_hours=12.0)
        started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
        ledger = CapLedger(started_at=started.isoformat(), wakes=3)
        now = started + timedelta(hours=2, minutes=30)
        self.assertEqual(status_line(ledger, caps, now), "wakes 3/10, 2.5h/12h")

    def test_status_line_rounds_tiny_elapsed_time_to_zero(self) -> None:
        caps = WatchCaps()
        started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
        ledger = CapLedger(started_at=started.isoformat())
        self.assertEqual(
            status_line(ledger, caps, started + timedelta(microseconds=1)),
            "wakes 0/10, 0h/12h",
        )

    def test_cap_note_body_includes_marker_and_resume(self) -> None:
        caps = WatchCaps()
        started = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
        ledger = CapLedger(
            started_at=started.isoformat(),
            wakes=10,
            paused_reason="max wakes reached (10)",
        )
        body = cap_note_body(ledger.paused_reason, ledger, caps)
        self.assertTrue(body.startswith(CAP_NOTE_MARKER))
        self.assertIn("Babysit watch paused", body)
        self.assertIn("gh plate pr babysit <n> --watch --reset-caps", body)
        self.assertIn("wakes 10/10", body)

    def test_has_cap_note_dedupe(self) -> None:
        self.assertFalse(has_cap_note([{"body": "unrelated"}]))
        self.assertTrue(has_cap_note([{"body": f"{CAP_NOTE_MARKER}\npaused"}]))
        self.assertTrue(has_cap_note([f"prefix {CAP_NOTE_MARKER} suffix"]))


if __name__ == "__main__":
    unittest.main()
