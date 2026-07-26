"""Tests for first-class template payload import (#616)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TestImportPayload(unittest.TestCase):
    def test_dry_run_empty_target_creates_plan(self):
        from plate_core.import_payload import import_payload, list_payload_relative_paths

        paths = list_payload_relative_paths()
        self.assertGreater(len(paths), 0)

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertTrue(report["ok"])
            self.assertFalse(report["apply_mode"])
            self.assertEqual(report["strategy"], "safe")
            self.assertGreater(report["counts"]["would_create"], 0)
            self.assertEqual(report["counts"]["created"], 0)
            # no side effects
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_safe_apply_then_skip_identical(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            first = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(first["ok"])
            self.assertGreater(first["counts"]["created"], 0)
            # files exist
            sample = first["created"][0]
            self.assertTrue((Path(tmp) / sample).is_file())

            second = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertGreater(second["counts"]["would_skip"], 0)
            self.assertEqual(second["counts"]["would_create"], 0)

    def test_conservative_conflict_on_differ(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            first = import_payload(tmp, strategy="safe", apply=True)
            rel = first["created"][0]
            dest = Path(tmp) / rel
            dest.write_text(dest.read_text(encoding="utf-8") + "\n# local change\n", encoding="utf-8")

            report = import_payload(tmp, strategy="conservative", dry_run=True)
            self.assertIn(rel, report["would_conflict"])
            apply_report = import_payload(tmp, strategy="conservative", apply=True)
            self.assertIn(rel, apply_report["conflicts"])
            # still has local marker
            self.assertIn("local change", dest.read_text(encoding="utf-8"))

    def test_force_overwrites(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            first = import_payload(tmp, strategy="safe", apply=True)
            rel = first["created"][0]
            dest = Path(tmp) / rel
            original = dest.read_bytes()
            dest.write_bytes(b"totally different content")

            report = import_payload(tmp, strategy="force", apply=True)
            self.assertIn(rel, report["overwritten"])
            self.assertEqual(dest.read_bytes(), original)

    def test_invalid_strategy(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="nope", dry_run=True)
            self.assertFalse(report["ok"])
            self.assertIn("Invalid strategy", report["error"] or "")

    def test_cli_dry_run_json(self):
        import argparse
        from io import StringIO
        from unittest.mock import patch

        from plate_core import cli as cli_mod

        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                target_dir=tmp,
                strategy="safe",
                template_repo=None,
                apply=False,
                json=True,
            )
            buf = StringIO()
            with patch("sys.stdout", buf):
                rc = cli_mod.cmd_import_payload(args)
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertGreater(data["counts"]["would_create"], 0)

    def test_parser_registers_import_payload(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("import-payload", help_text)

    def test_copy_template_payload_local_alias(self):
        """#620: bootstrap/agents can call copy_template_payload_local."""
        from plate_core.import_payload import copy_template_payload_local

        with tempfile.TemporaryDirectory() as tmp:
            report = copy_template_payload_local(tmp, dry_run=True)
            self.assertTrue(report["ok"])
            self.assertGreater(report["counts"]["would_create"], 0)
            applied = copy_template_payload_local(tmp, dry_run=False, strategy="safe")
            self.assertGreater(applied["counts"]["created"], 0)

    def test_bootstrap_shares_payload_path_planner(self):
        """#620: bootstrap remote applier uses same relative path set as local."""
        from plate_core.bootstrap import _template_payload_relative_paths
        from plate_core.import_payload import list_payload_relative_paths
        from plate_core.template_payload import resolve_template_source

        root, _ = resolve_template_source()
        self.assertEqual(
            _template_payload_relative_paths(root),
            list_payload_relative_paths(root),
        )

    def test_ci_yml_install_as_on_conflict(self):
        """#617: existing product ci.yml → write plate-ci.yml, preserve original."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            ci = Path(tmp) / ".github" / "workflows" / "ci.yml"
            ci.parent.mkdir(parents=True, exist_ok=True)
            ci.write_text("# product CI\n", encoding="utf-8")

            report = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(report["ok"])
            # original preserved
            self.assertEqual(ci.read_text(encoding="utf-8"), "# product CI\n")
            plate_ci = Path(tmp) / ".github" / "workflows" / "plate-ci.yml"
            self.assertTrue(plate_ci.is_file(), msg=report["created"][:10])
            # decision recorded
            decisions = [f for f in report["files"] if f["path"] == ".github/workflows/ci.yml"]
            self.assertEqual(len(decisions), 1)
            self.assertIn(decisions[0]["action"], ("create_as", "create"))
            if decisions[0]["action"] == "create_as":
                self.assertEqual(
                    decisions[0]["target_path"], ".github/workflows/plate-ci.yml"
                )


if __name__ == "__main__":
    unittest.main()
