"""Tests for epic/release Q&A planning (#640 / #629)."""

from __future__ import annotations

import unittest

import tempfile
from pathlib import Path

from plate_core.epic_release_planning import (
    apply_er_answer,
    build_epic_plan,
    build_er_plan_from_session,
    build_release_plan,
    get_er_script,
    load_er_session,
    start_er_session,
)
from plate_core.planning import list_pending_plans


class TestEpicPlanning640(unittest.TestCase):
    def test_script(self):
        s = get_er_script("epic")
        self.assertEqual(s["kind"], "epic")
        self.assertGreaterEqual(s["count"], 6)

    def test_auto_children_and_high_risk(self):
        plan = build_epic_plan(
            {
                "intent": "Ship safety gates",
                "problem": "Autonomy is unsafe without gates",
                "success": "Shadow + checkpoint live",
                "scope_in": "shadow; checkpoint",
                "children": "auto",
                "risk": "high",
            }
        )
        self.assertEqual(plan["kind"], "epic")
        self.assertIn("[Epic]", plan["title"])
        self.assertGreaterEqual(len(plan["children"]), 4)  # R+D+2 features at high
        self.assertTrue(plan["requires_approval"])
        self.assertIn("PLATE-EPIC-RELEASE-PLAN", plan["marker"])

    def test_session_walk(self):
        start = start_er_session("epic", persist=False)
        session = start["session"]
        answers = [
            "Feed UX",
            "Users lack a plan",
            "Epics exist with children",
            "Q&A; stubs",
            "Browser UI",
            "auto",
            "medium",
            "Minor",
        ]
        for a in answers:
            out = apply_er_answer(session, a, persist=False)
            session = out["session"]
        self.assertTrue(session["complete"])
        built = build_er_plan_from_session(session, persist_pending=False)
        self.assertTrue(built["ok"])
        self.assertEqual(built["plan"]["kind"], "epic")


class TestReleasePlanning629(unittest.TestCase):
    def test_release_plan(self):
        plan = build_release_plan(
            {
                "version_intent": "v1.0 safety + feed",
                "semver_hint": "minor",
                "scope_items": "645; 648; 631",
                "success_signals": "CI green; checklist E2E",
                "risks": "PyPI human Task",
                "marketing": "Autonomous PLATE 1.0",
                "media_plan": "demo gif",
                "cost_estimate": "50k tokens",
            }
        )
        self.assertEqual(plan["kind"], "release")
        self.assertEqual(plan["semver_hint"], "minor")
        self.assertEqual(plan["scope_items"], ["645", "648", "631"])
        self.assertIn("Ceremony checklist", plan["body"])
        self.assertTrue(plan["requires_approval"])
        self.assertIn("demo gif", plan["notes_skeleton"]["media_plan"])

    def test_release_session(self):
        start = start_er_session("release", persist=False)
        session = start["session"]
        for a in [
            "Ship 1.0 slice",
            "patch",
            "677; 678",
            "green CI",
            "none",
            "none",
            "none",
            "10k",
        ]:
            out = apply_er_answer(session, a, persist=False)
            session = out["session"]
        self.assertTrue(session["complete"])
        built = build_er_plan_from_session(session, persist_pending=False)
        self.assertTrue(built["ok"])
        self.assertEqual(built["plan"]["kind"], "release")


if __name__ == "__main__":
    unittest.main()


class TestERDurableTUI(unittest.TestCase):
    def test_er_durable_and_tui(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "er_sessions"
            start = start_er_session("epic", base_dir=sdir, persist=True)
            self.assertIn("session_id", start)
            self.assertIn("ask_user_question", start)
            self.assertTrue(start["ask_user_question"]["allow_free_text"])
            sid = start["session_id"]
            self.assertIsNotNone(load_er_session(sid, base_dir=sdir))
            out = apply_er_answer(start["session"], "Ship feed", base_dir=sdir, persist=True)
            self.assertIn("ask_user_question", out)
            loaded = load_er_session(sid, base_dir=sdir)
            self.assertIn("intent", loaded["answers"])

    def test_er_pending_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start = start_er_session("release", base_dir=root / "er_sessions", persist=True)
            session = start["session"]
            # walk remaining questions with dummy answers
            while not session.get("complete"):
                out = apply_er_answer(session, "x", base_dir=root / "er_sessions", persist=True)
                session = out["session"]
            built = build_er_plan_from_session(session, planning_root=root, persist_pending=True)
            self.assertTrue(built["ok"])
            self.assertIn("ask_user_question", built)
            pending = list_pending_plans(base_dir=root / "pending")
            self.assertGreaterEqual(len(pending), 1)
