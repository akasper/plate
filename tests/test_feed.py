"""Tests for Q+Task user feed (#631)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.feed import (
    build_feed_items,
    get_user_feed,
    issue_to_feed_item,
)


def _issue(number: int, title: str, labels: list[str], body: str = "body", updated: str = "2026-07-24T00:00:00Z"):
    return {
        "number": number,
        "title": title,
        "body": body,
        "html_url": f"https://github.com/akasper/plate/issues/{number}",
        "updated_at": updated,
        "labels": [{"name": n} for n in labels],
    }


class TestFeed631(unittest.TestCase):
    def test_issue_to_feed_item_question(self):
        it = issue_to_feed_item(_issue(10, "What is success metric?", ["Question", "risk:low"]), "question")
        self.assertEqual(it.item_type, "question")
        self.assertEqual(it.number, 10)
        self.assertEqual(it.impact, "low")
        self.assertIn("ask_user_question", it.prompt_segment)

    def test_task_defaults_high_impact(self):
        it = issue_to_feed_item(_issue(11, "Configure PyPI", ["Task"]), "task")
        self.assertEqual(it.impact, "high")
        self.assertIn("PLATE-TASK-CLOSED", it.prompt_segment)
        self.assertLess(it.rank, 40)

    def test_human_review_boosts_rank(self):
        a = issue_to_feed_item(_issue(1, "A", ["Question"]), "question")
        b = issue_to_feed_item(
            _issue(2, "B", ["Question", "need:human-review"]),
            "question",
        )
        self.assertLess(b.rank, a.rank)

    def test_build_feed_orders_tasks_and_checkpoints_first(self):
        items = build_feed_items(
            questions=[_issue(5, "Q about X", ["Question", "risk:low"])],
            tasks=[_issue(6, "Human publish", ["Task", "need:human-review"])],
            checkpoints=["cp-1: Approve deploy"],
            process_items=[{"title": "run bootstrap", "rank": 50}],
        )
        types = [i.item_type for i in items]
        self.assertIn("task", types)
        self.assertIn("question", types)
        self.assertIn("checkpoint", types)
        self.assertIn("process", types)
        # first item should be high-priority task or checkpoint, not low process
        self.assertIn(items[0].item_type, ("task", "checkpoint"))

    def test_get_user_feed_injected_offline(self):
        feed = get_user_feed(
            repo="akasper/plate",
            limit=5,
            include_process=False,
            include_autonomy=False,
            questions=[_issue(1, "Q1", ["Question"])],
            tasks=[_issue(2, "T1", ["Task"])],
        )
        self.assertEqual(feed["generated_for"], "user_feed")
        self.assertEqual(feed["counts"]["questions"], 1)
        self.assertEqual(feed["counts"]["tasks"], 1)
        self.assertEqual(feed["counts"]["returned"], 2)
        self.assertEqual(len(feed["presentation"]), 2)
        self.assertIn("PLATE Feed", feed["markdown"])
        self.assertIn("PLATE-FEED:BEGIN", feed["marker"])
        self.assertIn("ask_user_question", feed["tui_hint"])

    def test_get_user_feed_fetch_errors_tolerated(self):
        class Boom:
            def api(self, *a, **k):
                raise RuntimeError("gh down")

        feed = get_user_feed(
            repo="akasper/plate",
            client=Boom(),  # type: ignore[arg-type]
            limit=3,
            include_process=False,
            include_autonomy=False,
        )
        self.assertEqual(feed["counts"]["questions"], 0)
        self.assertIsNotNone(feed["errors"]["questions"])


if __name__ == "__main__":
    unittest.main()


    def test_structured_checkpoint_feed_item(self):
        items = build_feed_items(
            questions=[],
            tasks=[],
            checkpoints=[{
                "id": "cp-abc",
                "title": "Approve deploy",
                "impact": "critical",
                "action_kind": "deploy",
                "shadow_id": "shadow-x",
                "reason": "critical impact",
            }],
        )
        self.assertEqual(items[0].id, "cp-abc")
        self.assertEqual(items[0].item_type, "checkpoint")
        self.assertIn("plate_checkpoint_decide", items[0].prompt_segment)
        self.assertIn("checkpoint_id=cp-abc", items[0].prompt_segment)
        self.assertIn("shadow_ack=shadow-x", items[0].prompt_segment)
