"""Tests for Q&A-driven feature/product planning (#630 / #628)."""

from __future__ import annotations

import unittest

from plate_core.planning import (
    apply_planning_answer,
    build_feature_plan,
    build_plan_from_session,
    build_product_plan,
    get_planning_script,
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
        start = start_planning_session("feature")
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
            out = apply_planning_answer(session, text)
            session = out["session"]
        self.assertTrue(session["complete"])
        built = build_plan_from_session(session)
        self.assertTrue(built["ok"])
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
        start = start_planning_session("product")
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
            out = apply_planning_answer(session, text)
            session = out["session"]
        self.assertTrue(session["complete"])
        plan = build_product_plan(session["answers"])
        self.assertEqual(plan["kind"], "product")
        self.assertGreaterEqual(len(plan["proposed_epics"]), 3)
        self.assertEqual(plan["proposed_epics"][0]["type"], "Epic")
        self.assertEqual(len(plan["proposed_epics"][0]["children"]), 3)
        self.assertTrue(plan["requires_approval"])


if __name__ == "__main__":
    unittest.main()
