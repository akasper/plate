"""Tests for self-migrate dry-run plan (#939 / Epic #649)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plate_core.self_migrate import plan_self_migrate
from plate_core.cli import cmd_self_migrate


class PlanSelfMigrateTests(unittest.TestCase):
    def test_no_pin_no_drift_with_matching_target(self):
        """Proves: empty pin + default target uses installed version (#939)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# local\n", encoding="utf-8")
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["ok"])
        self.assertEqual(report["target_version"], "0.7.2")
        self.assertFalse(report["auto_apply"])
        self.assertEqual(report["mode"], "dry_run_plan")
        self.assertTrue(report["steps"])
        paths = {p["path"] for p in report["refresh_paths_present"]}
        self.assertIn("AGENTS.md", paths)

    def test_pin_behind_target_marks_drift(self):
        """Proves: VERSION pin behind target sets drift and upgrade step (#939)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "<!-- PLATES-CORE:BEGIN demo -->\nx\n<!-- PLATES-CORE:END demo -->\n",
                encoding="utf-8",
            )
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertTrue(report["drift"])
        self.assertEqual(report["pin"]["version"], "0.6.0")
        self.assertEqual(report["comparisons"]["pin_vs_target"], "behind")
        step_ids = [s["id"] for s in report["steps"]]
        self.assertIn("2_upgrade_runtime", step_ids)
        self.assertIn("4_import_payload", step_ids)
        markers = [
            p for p in report["refresh_paths_present"] if p["path"] == "AGENTS.md"
        ]
        self.assertTrue(markers[0]["has_plates_core_markers"])

    def test_pyproject_plate_core_pin(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\ndependencies = ["plate-core==0.5.1"]\n',
                encoding="utf-8",
            )
            report = plan_self_migrate(root, target_version="0.7.2")
        self.assertEqual(report["pin"]["version"], "0.5.1")
        self.assertEqual(report["pin"]["source"], "pyproject.toml")
        self.assertTrue(report["drift"])

    def test_no_payload_omits_import_step(self):
        with TemporaryDirectory() as tmp:
            report = plan_self_migrate(tmp, target_version="0.7.2", include_payload=False)
        ids = [s["id"] for s in report["steps"]]
        self.assertNotIn("4_import_payload", ids)

    def test_cmd_self_migrate_json(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "VERSION").write_text("0.7.2\n", encoding="utf-8")
            ns = type(
                "NS",
                (),
                {
                    "repo_root": tmp,
                    "target_version": "0.7.2",
                    "no_payload": False,
                    "plan": True,
                    "json": True,
                },
            )()
            import io
            import sys

            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = cmd_self_migrate(ns)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertIn("steps", data)


if __name__ == "__main__":
    unittest.main()
