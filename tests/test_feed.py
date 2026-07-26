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
        # May include durable local fleet/planning signals; require injected Q+T present
        types = {i.get("item_type") for i in feed.get("items") or []}
        self.assertIn("question", types)
        self.assertIn("task", types)
        self.assertGreaterEqual(feed["counts"]["returned"], 2)
        self.assertGreaterEqual(len(feed["presentation"]), 2)
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
        self.assertIn(items[0].item_type, ("approval", "artifact_approval"))
        self.assertIn("design", items[0].title.lower())

    def test_revised_approvals_rank_and_tui(self):
        from plate_core.feed import ask_user_question_payload, build_feed_items

        items = build_feed_items(
            approval_items=[
                {
                    "id": "plan-1",
                    "item_type": "planning_approval",
                    "kind": "feature",
                    "title": "Feature plan A",
                    "status": "revise_requested",
                    "rank": 14,
                    "reason": "revise requested",
                    "ask_user_question": {
                        "question": "Resubmit?",
                        "options": [{"id": "resubmit", "label": "Resubmit"}],
                    },
                },
                {
                    "id": "plan-2",
                    "item_type": "planning_approval",
                    "kind": "feature",
                    "title": "Feature plan B",
                    "status": "pending_approval",
                    "rank": 16,
                },
            ],
        )
        self.assertEqual(items[0].id, "plan-1")
        self.assertLess(items[0].rank, items[1].rank)
        self.assertEqual(items[0].item_type, "planning_approval")
        tui = ask_user_question_payload(
            {
                "id": "plan-1",
                "item_type": "planning_approval",
                "title": "Feature plan A",
                "status": "revise_requested",
                "kind": "feature",
            }
        )
        self.assertTrue(any(o["id"] == "resubmit" for o in tui["options"]))
        art = ask_user_question_payload(
            {
                "id": "art-1",
                "item_type": "artifact_approval",
                "title": "Design",
                "status": "revised",
                "kind": "design",
            }
        )
        self.assertTrue(any(o["id"] == "resubmit" for o in art["options"]))

    def test_pm_assignment_in_build_feed(self):
        items = build_feed_items(
            pm_assignments=[{
                "assignment_id": "asg-abc",
                "work_title": "Implement auth",
                "work_type": "implement",
                "agent_id": "dev-cautious",
                "agent_name": "Cautious Implementer",
                "status": "proposed",
                "requires_checkpoint": False,
                "rationale": "matched skill",
                "packet": {"prompt_segment": "Do auth TDD"},
            }],
        )
        self.assertEqual(items[0].item_type, "pm_assignment")
        self.assertEqual(items[0].id, "asg-abc")
        self.assertIn("plate_pm_complete", items[0].prompt_segment)
        self.assertIn("status=run", items[0].prompt_segment)
        self.assertIn("Cautious", items[0].title)

    def test_ask_user_question_pm_assignment(self):
        from plate_core.feed import FeedItem

        payload = ask_user_question_payload(
            FeedItem(
                id="asg-1",
                item_type="pm_assignment",
                number=None,
                title="Ship X → Dev",
                rank=20,
                impact="medium",
                badges=["pm", "proposed", "implement", "medium"],
                labels=["implement", "proposed"],
            )
        )
        self.assertTrue(any(o["id"] == "approve_run" for o in payload["options"]))
        self.assertTrue(any(o["id"] == "cancel" for o in payload["options"]))
        approve = next(o for o in payload["options"] if o["id"] == "approve_run")
        self.assertIn("status=run", approve["description"])

    def test_loop_stage_rank_and_tui(self):
        from plate_core.feed import ask_user_question_payload, loop_stage_feed_rank

        self.assertLess(
            loop_stage_feed_rank("human_checkpoint"),
            loop_stage_feed_rank("plan"),
        )
        self.assertLess(loop_stage_feed_rank("babysit"), loop_stage_feed_rank("implement"))
        babysit = ask_user_question_payload(
            {
                "id": "featloop-1",
                "item_type": "feature_loop",
                "title": "Feed ranking",
                "stage": "babysit",
                "pr_number": 99,
            }
        )
        self.assertTrue(any(o["id"] == "babysit" for o in babysit["options"]))
        self.assertTrue(any(o["id"] == "tick_gates" for o in babysit["options"]))
        hc = ask_user_question_payload(
            {
                "id": "bugloop-1",
                "item_type": "bug_loop",
                "title": "Auth",
                "stage": "human_checkpoint",
            }
        )
        self.assertTrue(any(o["id"] == "approve_checkpoint" for o in hc["options"]))
        pm_loop = ask_user_question_payload(
            {
                "id": "asg-loop",
                "item_type": "pm_assignment",
                "title": "Impl",
                "agent_name": "Dev",
                "loop_run_id": "featloop-x",
                "loop_kind": "feature",
            }
        )
        self.assertTrue(any(o["id"] == "tick_loop" for o in pm_loop["options"]))

    def test_build_feed_ranks_babysit_loop_high(self):
        from plate_core.feed import build_feed_items, loop_stage_feed_rank

        items = build_feed_items(
            signal_items=[
                {
                    "id": "fl-1",
                    "type": "feature_loop",
                    "title": "Feature loop [babysit]: X",
                    "stage": "babysit",
                    "rank": loop_stage_feed_rank("babysit", kind="feature"),
                    "impact": "medium",
                },
                {
                    "id": "fl-2",
                    "type": "feature_loop",
                    "title": "Feature loop [plan]: Y",
                    "stage": "plan",
                    "rank": loop_stage_feed_rank("plan", kind="feature"),
                    "impact": "medium",
                },
            ],
        )
        self.assertEqual(items[0].id, "fl-1")
        self.assertLess(items[0].rank, items[1].rank)

    def test_get_user_feed_includes_pm_queue(self):
        fake_asg = [{
            "assignment_id": "asg-feed",
            "work_title": "Research market",
            "work_type": "research",
            "agent_id": "research-analyst",
            "agent_name": "Research Analyst",
            "status": "proposed",
            "requires_checkpoint": False,
            "rationale": "research",
            "packet": {},
            "ask_user_question": {
                "question": "Run research?",
                "options": [{"label": "Go"}],
            },
        }]

        def _queue(**kw):
            return fake_asg if kw.get("status") == "proposed" else []

        with patch("plate_core.pm.list_pm_queue", side_effect=_queue), patch(
            "plate_core.checkpoint.list_open_checkpoints", return_value=[]
        ), patch(
            "plate_core.autonomy.get_autonomy_status",
            return_value={"risk_tolerance": "off", "enabled": False},
        ), patch(
            "plate_core.costs.get_cost_dashboard",
            return_value={"feed_items": []},
        ), patch(
            "plate_core.design_research_approval.list_proposals",
            return_value=[],
        ), patch(
            "plate_core.planning.list_pending_plans",
            return_value=[],
        ):
            feed = get_user_feed(
                repo="akasper/plate",
                limit=10,
                include_process=False,
                include_autonomy=True,
                questions=[],
                tasks=[],
            )
        self.assertGreaterEqual(feed["counts"].get("pm_assignments", 0), 1)
        types = [p["type"] for p in feed["presentation"]]
        self.assertIn("pm_assignment", types)
        pm_row = next(p for p in feed["presentation"] if p["type"] == "pm_assignment")
        self.assertEqual(pm_row["ask_user_question"]["question"], "Run research?")


if __name__ == "__main__":
    unittest.main()
