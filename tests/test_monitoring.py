"""Tests for scheduled discussion + market monitoring (#642)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.monitoring import (
    classify_discussion_title,
    decide_proposal,
    estimate_monitor_cost,
    list_proposals,
    monitor_market_signals,
    monitoring_feed_items,
    review_discussions,
    run_discussion_review_procedure,
    run_market_monitor_procedure,
    score_discussion,
    score_market_signal,
)


class TestClassify(unittest.TestCase):
    def test_epic_and_feature(self):
        t, s = classify_discussion_title("Platform roadmap for autonomous lifecycle")
        self.assertEqual(t, "Epic")
        self.assertGreater(s, 30)
        t2, _ = classify_discussion_title("Add support for marketplace packaging")
        self.assertEqual(t2, "Feature")

    def test_market_signal_score(self):
        d = score_market_signal(
            {
                "title": "Competitor launches pricing change",
                "detail": "Affects adoption",
                "sources": ["https://example.com"],
                "impact": "high",
            }
        )
        self.assertEqual(d["proposed_type"], "Question")
        self.assertGreaterEqual(d["score"], 40)


class TestReviewPersist(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_review_discussions_persist_and_decide(self):
        discussions = [
            {
                "number": 12,
                "title": "Add autonomous budget dashboards",
                "body": "We should implement feed-driven budgets for 1.0",
                "url": "https://github.com/ex/discussions/12",
                "category": "ideas",
            },
            {
                "number": 13,
                "title": "hi",
                "body": "",
            },
        ]
        out = review_discussions(
            discussions,
            min_score=25,
            persist=True,
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["n_proposed"], 1)
        self.assertIn("cost_estimate_tokens", out)
        props = list_proposals(base_dir=self.base)
        self.assertTrue(props)
        pid = props[0]["id"]
        dec = decide_proposal(pid, "approve", base_dir=self.base)
        self.assertTrue(dec["ok"])
        self.assertEqual(dec["proposal"]["status"], "approved")

    def test_market_and_feed(self):
        out = monitor_market_signals(
            [
                {
                    "title": "New competitor feature for Q&A feed",
                    "detail": "Competitor Y added endless Q&A",
                    "url": "https://x.example/1",
                    "impact": "high",
                }
            ],
            persist=True,
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertEqual(out["n_proposed"], 1)
        self.assertIn("cost_estimate_tokens", out)
        feed = monitoring_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        self.assertIn("ask_user_question", feed[0])

    def test_dry_run_never_charges_live_budget(self):
        from plate_core.autonomy import load_budget_spend
        from plate_core.monitoring import review_discussions

        root_before = int((load_budget_spend() or {}).get("spent_today") or 0)
        out = review_discussions(
            [{"title": "Epic idea for feed", "body": "feature planning"}],
            persist=False,
            fetch_live=False,
            base_dir=self.base,
            use_live_budget=True,
        )
        self.assertTrue(out["ok"])
        self.assertNotIn("budget_charge", out)
        self.assertTrue(
            any("skipped budget charge" in n for n in (out.get("notes") or []))
        )
        self.assertEqual(
            int((load_budget_spend() or {}).get("spent_today") or 0), root_before
        )

    def test_procedure_dry_run(self):
        d = run_discussion_review_procedure(
            discussions=[{"number": 1, "title": "Implement release ceremony automation", "body": "feature"}],
            dry_run=True,
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertEqual(d["status"], "dry-run")
        self.assertEqual(d["proc_id"], "weekly-discussion-review")
        # dry_run does not persist
        self.assertEqual(list_proposals(base_dir=self.base), [])

        m = run_market_monitor_procedure(
            signals=[{"title": "Pricing change", "impact": "medium", "sources": ["a"]}],
            dry_run=True,
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertEqual(m["proc_id"], "market-condition-monitor")
        self.assertTrue(m["dry_run"])

    def test_budget_gate(self):
        est = estimate_monitor_cost(kind="discussion", n_items=2, persist=True)
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        blocked = review_discussions(
            [{"number": 1, "title": "Add feature X for autonomy", "body": "detail"}],
            min_score=10,
            persist=False,
            budget_remaining=10,
            use_live_budget=False,
            base_dir=self.base,
        )
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked.get("blocked"))
        self.assertIn("budget", blocked.get("error") or "")
        ok = monitor_market_signals(
            [{"title": "Pricing", "impact": "high", "sources": ["a"]}],
            persist=False,
            budget_remaining=est["estimated_tokens"] + 5000,
            use_live_budget=False,
            base_dir=self.base,
        )
        self.assertTrue(ok["ok"])

    def test_budget_blocks_on_durable_would_pause_risk_off(self):
        """#877: monitoring blocks on would_pause even when est < remaining."""
        from unittest.mock import patch

        from plate_core.autonomy import save_budget_spend

        bdir = self.base / "budget"
        today = (
            __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .date()
            .isoformat()
        )
        # remaining=5000, per_cycle=10000 → would_pause; discussion est ~2.6k < 5k
        save_budget_spend(
            {
                "date": today,
                "spent_today": 45000,
                "spent_this_cycle": 0,
                "spent_usd_today": 0.0,
            },
            base_dir=bdir,
        )

        class _Cfg:
            autonomy = {
                "enabled": False,
                "risk_tolerance": "off",
                "token_budget": {
                    "daily": 50000,
                    "per_cycle": 10000,
                    "action": "pause",
                },
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            out = review_discussions(
                [{"number": 1, "title": "Add feature X for autonomy", "body": "detail"}],
                min_score=10,
                persist=False,
                use_live_budget=True,
                base_dir=self.base,
            )

        self.assertFalse(out.get("ok"), out)
        self.assertTrue(out.get("blocked"))
        self.assertIn("budget", out.get("error") or "")
        self.assertTrue(out.get("would_pause_next_cycle"))
        self.assertEqual(out.get("budget_remaining"), 5000)


class TestScoreDiscussion(unittest.TestCase):
    def test_score_includes_body(self):
        s = score_discussion({"title": "Should we adopt X?", "body": "poll for team"})
        self.assertEqual(s["proposed_type"], "Question")
        self.assertIn("body", s)


if __name__ == "__main__":
    unittest.main()
