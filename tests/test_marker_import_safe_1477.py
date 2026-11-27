"""Regression tests for #1477 marker merge bases and safe import overwrite guard."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.import_payload import import_payload
from plate_core.self_migrate import (
    load_persisted_marker_base,
    plan_marker_merge,
    record_marker_merge_bases,
    save_persisted_marker_base,
)


class MarkerMergeBaseTests(unittest.TestCase):
    def test_apply_without_base_refuses_and_preserves_custom_marker(self):
        local = """<!-- PLATES-CORE:BEGIN demo -->
adopter customized
<!-- PLATES-CORE:END demo -->
"""
        upstream = """<!-- PLATES-CORE:BEGIN demo -->
upstream takeover
<!-- PLATES-CORE:END demo -->
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(local, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream},
                apply=True,
            )
            self.assertFalse(report["ok"])
            self.assertEqual(report["written"], 0)
            self.assertEqual(report["files"][0]["action"], "missing_base")
            self.assertIn("adopter customized", agents.read_text(encoding="utf-8"))

    def test_dry_run_without_base_does_not_plan_upstream_takeover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "<!-- PLATES-CORE:BEGIN x -->\nlocal\n<!-- PLATES-CORE:END x -->\n",
                encoding="utf-8",
            )
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={
                    "AGENTS.md": (
                        "<!-- PLATES-CORE:BEGIN x -->\nupstream\n"
                        "<!-- PLATES-CORE:END x -->\n"
                    )
                },
                apply=False,
            )
            self.assertEqual(report["files"][0]["action"], "missing_base")
            self.assertEqual(report["would_write"], 0)

    def test_apply_with_base_preserves_marker_customization(self):
        base = """<!-- PLATES-CORE:BEGIN demo -->
shared old
<!-- PLATES-CORE:END demo -->
"""
        local = """<!-- PLATES-CORE:BEGIN demo -->
adopter customized
<!-- PLATES-CORE:END demo -->
"""
        upstream = """<!-- PLATES-CORE:BEGIN demo -->
upstream new
<!-- PLATES-CORE:END demo -->
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(local, encoding="utf-8")
            save_persisted_marker_base(root, "AGENTS.md", base)
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream},
                apply=True,
            )
            text = agents.read_text(encoding="utf-8")
        self.assertTrue(report["ok"])
        self.assertIn("adopter customized", text)
        self.assertNotIn("upstream new", text)
        self.assertEqual(report["written"], 0)

    def test_apply_writes_backup_before_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = """<!-- PLATES-CORE:BEGIN demo -->
old core
<!-- PLATES-CORE:END demo -->
"""
            upstream = """<!-- PLATES-CORE:BEGIN demo -->
new core
<!-- PLATES-CORE:END demo -->
"""
            agents = root / "AGENTS.md"
            agents.write_text(local, encoding="utf-8")
            save_persisted_marker_base(root, "AGENTS.md", local)
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream},
                apply=True,
            )
            backup_root = root / ".agentic/marker-merge/backups"
            self.assertTrue(report["ok"])
            self.assertEqual(report["written"], 1)
            self.assertTrue(any(backup_root.iterdir()))

    def test_import_payload_seeds_marker_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            base = load_persisted_marker_base(root, "AGENTS.md")
            self.assertIsNotNone(base)
            self.assertIn("PLATES-CORE", base or "")


class SafeImportOverwriteTests(unittest.TestCase):
    def test_safe_skips_taxonomy_when_adopter_edited_since_import(self):
        taxonomy_paths = (
            ".github/labels.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(first["ok"])
            for rel in taxonomy_paths:
                dest = root / rel
                self.assertTrue(dest.is_file(), msg=rel)
                dest.write_text(
                    "# adopter customized\n" + dest.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            second = import_payload(root, strategy="safe", dry_run=True)
            self.assertTrue(second["ok"])
            for rel in taxonomy_paths:
                self.assertIn(rel, second["would_skip"])
                self.assertNotIn(rel, second["would_overwrite"])
            applied = import_payload(root, strategy="safe", apply=True)
            for rel in taxonomy_paths:
                self.assertNotIn(rel, applied.get("overwritten") or [])
                self.assertIn("# adopter customized", (root / rel).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()