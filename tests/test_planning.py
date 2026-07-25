"""Tests for Q&A-driven feature/product planning (#630 / #628)."""

from __future__ import annotations

import unittest

from pathlib import Path
import tempfile

from plate_core.planning import (
    apply_planning_answer,
    build_feature_plan,
    build_plan_from_session,
    build_product_plan,
    decide_pending_plan,
    estimate_planning_cost,
    get_planning_script,
    list_pending_plans,
    load_planning_session,
    planning_feed_items,
    start_planning_session,
)


class TestFeaturePlanning630(unittest.TestCase):
    def test_script_has_required_fields(self):
        script = get_planning_script("feature")
        self.assertEqual(script["kind"], "feature")
        self.assertGreaterEqual(script["count"], 6)
        ids = [q["id"] for q in script["questions"]]
        self.assertIn("problem", ids)
        self.assertIn("acceptance_criteria", ids)
        self.assertIn("media_plan", ids)

    def test_session_advances_and_builds(self):
        start = start_planning_session(
            "feature", persist=False, use_live_budget=False
        )
        self.assertTrue(start.get("ok", True))
        self.assertIn("cost_estimate_tokens", start)
        session = start["session"]
        self.assertFalse(session["complete"])
        self.assertIsNotNone(start["next_question"])

        answers_seq = [
            "Users cannot plan features without toil",
            "Agent runs Q&A and emits Feature stub",
            "AC1: creates Feature issue; AC2: includes tests section",
            "Unit tests for planning builders",
            "Fragment + wiki",
            "none",
            "risk:low",
            "gif of feed",
            "654",
        ]
        for text in answers_seq:
            out = apply_planning_answer(session, text, persist=False)
            session = out["session"]
        self.assertTrue(session["complete"])
        built = build_plan_from_session(
            session, persist_pending=False, use_live_budget=False
        )
        self.assertTrue(built["ok"])
        self.assertIn("cost_estimate_tokens", built)
        plan = built["plan"]
        self.assertEqual(plan["kind"], "feature")
        self.assertIn("[Feature]", plan["title"])
        self.assertIn("Feature", plan["labels"])
        self.assertTrue(plan["requires_approval"])
        self.assertIn("Acceptance criteria", plan["body"])
        self.assertIn("Media / demo plan", plan["body"])
        self.assertIn("PLATE-PLAN:BEGIN", plan["marker"])
        self.assertIn("ask_user_question", plan["prompt_segment"])

    def test_build_feature_with_design_and_research(self):
        plan = build_feature_plan(
            {
                "problem": "p",
                "desired_behavior": "does X",
                "acceptance_criteria": "works; tested",
                "tests": "unit",
                "design_needs": "both",
            },
            title_hint="Cool feature",
        )
        self.assertEqual(len(plan["linked_stubs"]), 2)
        types = {s["type"] for s in plan["linked_stubs"]}
        self.assertEqual(types, {"Design", "Research"})


class TestProductPlanning628(unittest.TestCase):
    def test_product_session_and_epics(self):
        start = start_planning_session(
            "product", persist=False, use_live_budget=False
        )
        session = start["session"]
        seq = [
            "Ship agentic SDLC",
            "Indie hackers; platform teams",
            "Autonomy; Feed; Safety",
            "No full PM UI",
            "Budget overruns",
            "Safety; Feed; PM loop",
            "SPEC Goals + roadmap",
        ]
        for text in seq:
            out = apply_planning_answer(session, text, persist=False)
            session = out["session"]
        self.assertTrue(session["complete"])
        plan = build_product_plan(session["answers"])
        self.assertEqual(plan["kind"], "product")
        self.assertGreaterEqual(len(plan["proposed_epics"]), 3)
        self.assertEqual(plan["proposed_epics"][0]["type"], "Epic")
        self.assertEqual(len(plan["proposed_epics"][0]["children"]), 3)
        self.assertTrue(plan["requires_approval"])


class TestPlanningDurableTUI(unittest.TestCase):
    def test_durable_session_and_tui_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "sessions"
            start = start_planning_session("feature", base_dir=sdir, persist=True, use_live_budget=False)
            self.assertIn("session_id", start)
            self.assertIn("ask_user_question", start)
            self.assertTrue(start["ask_user_question"]["allow_free_text"])
            sid = start["session_id"]
            loaded = load_planning_session(sid, base_dir=sdir)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["id"], sid)
            out = apply_planning_answer(
                start["session"], "problem text", base_dir=sdir, persist=True
            )
            self.assertIn("ask_user_question", out)
            loaded2 = load_planning_session(sid, base_dir=sdir)
            self.assertIn("problem", loaded2["answers"])

    def test_pending_plan_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start = start_planning_session("feature", base_dir=root / "sessions", persist=True, use_live_budget=False)
            session = start["session"]
            answers_seq = [
                "Users cannot plan features without toil",
                "Agent runs Q&A and emits Feature stub",
                "AC1: creates Feature issue; AC2: includes tests section",
                "Unit tests for planning builders",
                "Fragment + wiki",
                "none",
                "risk:low",
                "gif of feed",
                "654",
            ]
            for text in answers_seq:
                out = apply_planning_answer(session, text, base_dir=root / "sessions", persist=True)
                session = out["session"]
            built = build_plan_from_session(session, planning_root=root, persist_pending=True, use_live_budget=False)
            self.assertTrue(built["ok"])
            self.assertIn("ask_user_question", built)
            self.assertTrue((root / "pending").is_dir())
            pending = list_pending_plans(base_dir=root / "pending")
            self.assertGreaterEqual(len(pending), 1)
            self.assertTrue(pending[0].get("ask_user_question"))

    def test_decide_and_feed_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdir = root / "sessions"
            pdir = root / "pending"
            start = start_planning_session("feature", base_dir=sdir, persist=True, use_live_budget=False)
            session = start["session"]
            answers_seq = [
                "problem",
                "behavior",
                "ac1; ac2",
                "unit tests",
                "docs",
                "none",
                "risk:medium",
                "none",
                "none",
            ]
            for text in answers_seq:
                out = apply_planning_answer(session, text, base_dir=sdir, persist=True)
                session = out["session"]
            # incomplete session remains for feed
            start2 = start_planning_session("product", base_dir=sdir, persist=True, use_live_budget=False)
            self.assertFalse(start2["session"]["complete"])

            built = build_plan_from_session(session, planning_root=root, persist_pending=True, use_live_budget=False)
            self.assertTrue(built["ok"])
            pid = built["plan"]["id"]
            feed = planning_feed_items(pending_dir=pdir, sessions_dir=sdir, limit=10)
            types = {f.get("item_type") for f in feed}
            self.assertIn("planning_approval", types)
            self.assertIn("planning_session", types)
            appr = next(f for f in feed if f.get("item_type") == "planning_approval")
            self.assertTrue(appr["ask_user_question"]["options"])

            dec = decide_pending_plan(
                pid, "approve", decided_by="test", base_dir=pdir, archive=True
            )
            self.assertTrue(dec["ok"])
            self.assertEqual(dec["status"], "approved")
            self.assertTrue(dec["next_steps"])
            # no longer pending
            self.assertEqual(list_pending_plans(base_dir=pdir), [])
            again = decide_pending_plan(pid, "approve", base_dir=pdir)
            # archived under decided — get finds it but not pending_approval
            self.assertFalse(again.get("ok"))

    def test_revise_stays_actionable_and_resubmit(self):
        from plate_core.planning import (
            decide_pending_plan,
            list_actionable_plans,
            planning_feed_items,
            resubmit_pending_plan,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdir = root / "sessions"
            pdir = root / "pending"
            start = start_planning_session("feature", base_dir=sdir, persist=True, use_live_budget=False)
            session = start["session"]
            for text in [
                "problem",
                "behavior",
                "ac1",
                "tests",
                "docs",
                "none",
                "risk:low",
                "none",
                "none",
            ]:
                out = apply_planning_answer(session, text, base_dir=sdir, persist=True)
                session = out["session"]
            built = build_plan_from_session(session, planning_root=root, persist_pending=True, use_live_budget=False)
            pid = built["plan"]["id"]
            rev = decide_pending_plan(pid, "revise", decided_by="test", base_dir=pdir)
            self.assertTrue(rev["ok"])
            self.assertEqual(rev["status"], "revise_requested")
            # still in pending dir and feed
            actionable = list_actionable_plans(base_dir=pdir)
            self.assertTrue(any(p.get("id") == pid for p in actionable))
            feed = planning_feed_items(pending_dir=pdir, sessions_dir=sdir, limit=10)
            appr = next(f for f in feed if f.get("id") == pid)
            self.assertEqual(appr["status"], "revise_requested")
            self.assertTrue(any(o["id"] == "resubmit" for o in appr["ask_user_question"]["options"]))
            # cannot approve until resubmit
            blocked = decide_pending_plan(pid, "approve", base_dir=pdir)
            self.assertFalse(blocked["ok"])
            res = resubmit_pending_plan(
                pid, title="Revised title", note="fixed ACs", base_dir=pdir
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["status"], "pending_approval")
            self.assertGreaterEqual(res["version"], 2)
            ok = decide_pending_plan(pid, "approve", base_dir=pdir, archive=True)
            self.assertTrue(ok["ok"])
            self.assertEqual(ok["status"], "approved")



class TestPlanningBudget634(unittest.TestCase):
    def test_budget_gate(self):
        est = estimate_planning_cost(kind="feature", phase="start")
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        blocked = start_planning_session(
            "feature",
            persist=False,
            budget_remaining=10,
            use_live_budget=False,
        )
        self.assertFalse(blocked.get("ok"))
        self.assertTrue(blocked.get("blocked"))
        ok = start_planning_session(
            "feature",
            persist=False,
            budget_remaining=est["estimated_tokens"] + 1000,
            use_live_budget=False,
        )
        self.assertTrue(ok.get("ok", True))
        session = {
            "kind": "feature",
            "complete": True,
            "answers": {"problem": "p", "desired_behavior": "x"},
            "id": "plan-x",
        }
        b_block = build_plan_from_session(
            session,
            persist_pending=False,
            budget_remaining=10,
            use_live_budget=False,
        )
        self.assertFalse(b_block.get("ok"))
        self.assertTrue(b_block.get("blocked"))
        self.assertNotIn("budget_charge", ok)
        self.assertNotIn("budget_charge", b_block)



if __name__ == "__main__":
    unittest.main()
