"""Tests for checkout isolation guard (#1542)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.checkout_isolation_guard import diff_snapshots, format_leak_report, snapshot_watched_paths


class TestCheckoutIsolationGuard(unittest.TestCase):
    def test_detects_planted_leak(self):
        repo = Path(__file__).resolve().parents[1]
        before = snapshot_watched_paths(repo)
        probe = repo / ".agentic" / "_isolation_guard_probe.txt"
        probe.parent.mkdir(parents=True, exist_ok=True)
        try:
            probe.write_text("probe\n", encoding="utf-8")
            after = snapshot_watched_paths(repo)
            leaks = diff_snapshots(before, after)
            self.assertIn(".agentic/_isolation_guard_probe.txt", leaks)
            report = format_leak_report(leaks)
            self.assertIn("_isolation_guard_probe.txt", report)
        finally:
            probe.unlink(missing_ok=True)

    def test_isolated_cwd_leaves_repo_snapshot_unchanged(self):
        from tests.isolation_support import isolated_cwd

        repo = Path(__file__).resolve().parents[1]
        before = snapshot_watched_paths(repo)
        with isolated_cwd() as sandbox:
            (sandbox / ".agentic" / "ledger" / "dec-probe.json").parent.mkdir(parents=True)
            (sandbox / ".agentic" / "ledger" / "dec-probe.json").write_text("{}", encoding="utf-8")
        after = snapshot_watched_paths(repo)
        self.assertEqual([], diff_snapshots(before, after))


if __name__ == "__main__":
    unittest.main()