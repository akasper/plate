"""Tests for hardened plate_what_next (#789 / #654)."""

from __future__ import annotations

import unittest

from plate_core.what_next import recommend_what_next


class TestRecommendWhatNext(unittest.TestCase):
    def test_budget_critical_first(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={
                "budget_pressure": "exhausted",
                "remaining_tokens": 0,
                "daily_limit": 50000,
                "risk_tolerance": "off",
            },
            open_prs=[{"number": 1, "title": "x", "baseRefName": "release"}],
        )
        self.assertEqual(out["priority"], "budget_gate")
        self.assertIn("budget", out["next_action"].lower())
        self.assertEqual(out["state_snapshot"]["budget_pressure"], "exhausted")

    def test_open_pr_before_epic(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 3},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[
                {
                    "number": 788,
                    "title": "Surface budget_gate",
                    "baseRefName": "release",
                }
            ],
        )
        self.assertEqual(out["priority"], "open_pr")
        self.assertIn("#788", out["next_action"])
        self.assertEqual(out["pr_number"], 788)

    def test_labels_bootstrap(self):
        out = recommend_what_next(
            health={"label_coverage_ok": False, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 50000},
            open_prs=[],
        )
        self.assertEqual(out["priority"], "bootstrap")

    def test_epic_when_healthy(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
        )
        self.assertEqual(out["priority"], "epic")

    def test_fragments_when_no_epics(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000},
            open_prs=[],
            pending_fragment_count=12,
        )
        self.assertEqual(out["priority"], "fragments")


class TestWhatNextCLI(unittest.TestCase):
    def test_cmd_what_next_json(self):
        import argparse
        import json
        from io import StringIO
        from unittest.mock import patch

        from plate_core import cli as cli_mod

        fake = {
            "next_action": "babysit open PR #1",
            "priority": "open_pr",
            "rationale": "test",
            "state_snapshot": {"open_pr_count": 1},
            "prompt_segment": "do it",
        }
        args = argparse.Namespace(
            repo="akasper/plate",
            agent_type="general",
            no_prs=True,
            no_budget=True,
            no_fragments=True,
            json=True,
        )
        buf = StringIO()
        # from .what_next import get_what_next binds name in cli_mod.cmd_what_next locals;
        # patch the module attribute before the call so the import loads the mock.
        with patch("plate_core.what_next.get_what_next", return_value=fake):
            with patch("sys.stdout", buf):
                rc = cli_mod.cmd_what_next(args)
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["priority"], "open_pr")

    def test_parser_registers_what_next(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("what-next", help_text)


if __name__ == "__main__":
    unittest.main()
