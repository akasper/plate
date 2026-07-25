"""Tests for Q+Task user feed (#631)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.feed import (
    ask_user_question_payload,
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

    def test_ask_user_question_payload_for_types(self):
        from plate_core.feed import ask_user_question_payload, FeedItem
        q = ask_user_question_payload(
            FeedItem(id="q-1", item_type="question", number=10, title="What?", rank=20, impact="low")
        )
        self.assertIn("options", q)
        self.assertEqual(q["options"][0]["id"], "answer_now")
        tsk = ask_user_question_payload(
            FeedItem(id="t-1", item_type="task", number=11, title="Do X", rank=5, impact="high")
        )
        self.assertTrue(any(o["id"] == "done_signal" for o in tsk["options"]))
        cp = ask_user_question_payload(
            FeedItem(id="cp-1", item_type="checkpoint", number=None, title="Approve", rank=10, impact="high")
        )
        self.assertTrue(any(o["id"] == "approve" for o in cp["options"]))

    def test_feed_presentation_includes_ask_user_question(self):
        feed = get_user_feed(
            repo="akasper/plate",
            limit=5,
            include_process=False,
            include_autonomy=False,
            questions=[{
                "number": 1,
                "title": "Q1",
                "body": "b",
                "html_url": "https://example.com/1",
                "updated_at": "2026-07-24T00:00:00Z",
                "labels": [{"name": "Question"}],
            }],
            tasks=[],
        )
        self.assertTrue(feed["presentation"])
        self.assertIn("ask_user_question", feed["presentation"][0])
        self.assertIn("options", feed["presentation"][0]["ask_user_question"])

    def test_approval_items_in_build_feed(self):
        items = build_feed_items(
            approval_items=[{
                "id": "ap-1",
                "kind": "design",
                "title": "Checkout UX",
                "status": "pending",
                "approval_prompt": "Approve design?",
            }],
        )
        self.assertEqual(items[0].item_type, "approval")
        self.assertIn("design", items[0].title.lower())


if __name__ == "__main__":
    unittest.main()
