"""Tests for adoption readiness and first Q&A seed (#935/#949 / Epic #633)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plate_core.adoption import (
    adoption_session_status,
    assess_adoption_readiness,
    complete_adoption_session,
    first_qa_seed_status,
    plan_first_qa_seed,
    start_adoption_session,
)
from plate_core.cli import cmd_adopt
from plate_core.what_next import recommend_what_next


class AssessAdoptionReadinessTests(unittest.TestCase):
    def test_empty_repo_not_core_ready_within_30m(self):
        """Proves: bare repo fails core checks with estimate ≤30m (#935)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = assess_adoption_readiness(root)
        self.assertTrue(report["ok"])
        self.assertFalse(report["core_ready"])
        self.assertGreater(report["core_failed"], 0)
        self.assertGreater(report["estimated_minutes_remaining"], 0)
        self.assertLessEqual(report["estimated_minutes_remaining"], 30)
        self.assertTrue(report["within_30m_budget"])
        self.assertIn("import-payload", report["next_command"])
        self.assertIn("ask_user_question", report)
        ids = {c["id"] for c in report["checks"]}
        self.assertIn("plate_config", ids)
        self.assertIn("agents_md", ids)
        self.assertIn("goals_wiki", ids)

    def test_core_ready_when_minimum_files_present(self):
        """Proves: minimum adopt artifacts flip core_ready (#935)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text("{}\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
            goals = root / "docs" / "wiki"
            goals.mkdir(parents=True)
            (goals / "Goals.md").write_text("# Goals\n", encoding="utf-8")
            unreleased = root / ".agentic" / "releases" / "unreleased"
            unreleased.mkdir(parents=True)
            (unreleased / "README.md").write_text("x\n", encoding="utf-8")
            wf = root / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "plate-ci.yml").write_text("name: plate\n", encoding="utf-8")
            report = assess_adoption_readiness(root, include_optional=False)
        self.assertTrue(report["core_ready"])
        self.assertEqual(report["estimated_minutes_remaining"], 0)
        self.assertEqual(report["core_failed"], 0)
        # Unseeded first Q&A is the post-core next step (#949)
        self.assertIn("first-qa-plan", report["next_command"])

    def test_optional_checks_do_not_block_core_ready(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text("{}\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# a\n", encoding="utf-8")
            g = root / "docs" / "wiki"
            g.mkdir(parents=True)
            (g / "Goals.md").write_text("# g\n", encoding="utf-8")
            (root / ".agentic" / "releases" / "unreleased").mkdir(parents=True)
            (root / ".github").mkdir(parents=True)
            (root / ".github" / "labels.yml").write_text("labels: []\n", encoding="utf-8")
            report = assess_adoption_readiness(root, include_optional=True)
        self.assertTrue(report["core_ready"])
        # SPEC/CURRENT optional missing may add optional minutes only
        self.assertGreaterEqual(report.get("optional_minutes_remaining", 0), 0)

    def test_core_ready_next_cmd_first_qa_when_not_seeded(self):
        """Proves: core_ready without seed marker points at first-qa-plan (#949)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text("{}\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
            goals = root / "docs" / "wiki"
            goals.mkdir(parents=True)
            (goals / "Goals.md").write_text("# Goals\n", encoding="utf-8")
            unreleased = root / ".agentic" / "releases" / "unreleased"
            unreleased.mkdir(parents=True)
            (unreleased / "README.md").write_text("x\n", encoding="utf-8")
            wf = root / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "plate-ci.yml").write_text("name: plate\n", encoding="utf-8")
            report = assess_adoption_readiness(root, include_optional=False)
        self.assertTrue(report["core_ready"])
        self.assertFalse(report["first_qa"]["seeded"])
        self.assertIn("first-qa-plan", report["next_command"])

    def test_first_qa_plan_dry_run(self):
        """Proves: dry-run plan lists 3 starter Questions without writing marker (#949)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = plan_first_qa_seed(root, apply=False)
            status = first_qa_seed_status(root)
        self.assertTrue(report["ok"])
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["count"], 3)
        self.assertFalse(report["applied"])
        self.assertFalse(status["seeded"])
        self.assertEqual(len(report["gh_argv_list"]), 3)

    def test_first_qa_apply_with_runner_writes_marker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            def runner(plan):
                return {"created": plan["count"]}

            report = plan_first_qa_seed(root, apply=True, runner=runner)
            status = first_qa_seed_status(root)
        self.assertTrue(report["ok"])
        self.assertTrue(report["applied"])
        self.assertTrue(status["seeded"])
        self.assertEqual(status["count"], 3)

    def test_first_qa_apply_without_runner_blocked(self):
        with TemporaryDirectory() as tmp:
            report = plan_first_qa_seed(tmp, apply=True, runner=None)
        self.assertFalse(report["ok"])
        self.assertEqual(report["error"], "runner_required")

    def test_what_next_ranks_first_qa_when_core_ready_unseeded(self):
        """Proves: what_next priority first_qa_seed after adoption ready (#949)."""
        adoption = {
            "core_ready": True,
            "first_qa": {"seeded": False},
            "estimated_minutes_remaining": 0,
        }
        rec = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 50000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[],
            adoption=adoption,
            agent_type="general",
        )
        self.assertEqual(rec.get("priority"), "first_qa_seed")
        self.assertIn("first-qa-plan", rec.get("next_command") or "")

    def test_adoption_session_start_complete_within_30m(self):
        """Proves: session records duration and within_30m for under-30m proof (#955)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_adoption_session(
                root, now_iso="2026-07-27T10:00:00+00:00"
            )
            self.assertTrue(started["ok"])
            self.assertTrue(started["started"])
            status = adoption_session_status(root)
            self.assertTrue(status["active"])
            done = complete_adoption_session(
                root, now_iso="2026-07-27T10:18:00+00:00"
            )
        self.assertTrue(done["ok"])
        self.assertTrue(done["completed"])
        self.assertEqual(done["duration_minutes"], 18.0)
        self.assertTrue(done["within_30m"])

    def test_adoption_session_over_30m(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            start_adoption_session(root, now_iso="2026-07-27T10:00:00+00:00")
            done = complete_adoption_session(
                root, now_iso="2026-07-27T10:45:00+00:00"
            )
        self.assertTrue(done["ok"])
        self.assertEqual(done["duration_minutes"], 45.0)
        self.assertFalse(done["within_30m"])

    def test_adoption_session_complete_without_start(self):
        with TemporaryDirectory() as tmp:
            done = complete_adoption_session(tmp)
        self.assertFalse(done["ok"])
        self.assertEqual(done["error"], "no_session")

    def test_cmd_adopt_json(self):
        with TemporaryDirectory() as tmp:
            ns = type(
                "NS",
                (),
                {
                    "repo_root": tmp,
                    "no_optional": True,
                    "json": True,
                    "first_qa_plan": False,
                    "apply_first_qa": False,
                    "start_session": False,
                    "complete_session": False,
                    "session_status": False,
                    "force": False,
                    "require_core_ready": False,
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_adopt(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertIn("checks", data)


class AdoptionGuideRegressionTests(unittest.TestCase):
    def test_guide_documents_under_30m_command_path(self):
        """Proves: adoption-guide lists full #633 CLI path phrases (#961)."""
        root = Path(__file__).resolve().parents[1]
        guide = (root / "docs" / "migration" / "adoption-guide.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "gh plate adopt --start-session",
            "gh plate adopt --json",
            "gh plate import-payload --dry-run --strategy conservative",
            "gh plate bootstrap --repo OWNER/REPO --adopt --apply",
            "gh plate adopt --first-qa-plan",
            "gh plate health --json",
            "gh plate feed --json",
            "gh plate adopt --complete-session",
            "first_qa_seeded",
            "within_30m",
            "#955",
            "#959",
        ):
            self.assertIn(phrase, guide, f"missing guide phrase: {phrase}")


if __name__ == "__main__":
    unittest.main()
