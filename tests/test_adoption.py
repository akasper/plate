"""Tests for adoption readiness status (#935 / Epic #633)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plate_core.adoption import assess_adoption_readiness
from plate_core.cli import cmd_adopt


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
        self.assertIn("health", report["next_command"])

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

    def test_cmd_adopt_json(self):
        with TemporaryDirectory() as tmp:
            ns = type(
                "NS",
                (),
                {
                    "repo_root": tmp,
                    "no_optional": True,
                    "json": True,
                },
            )()
            with patch("sys.stdout") as out:
                # capture via real print path
                pass
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


if __name__ == "__main__":
    unittest.main()
