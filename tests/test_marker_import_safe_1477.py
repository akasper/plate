"""Regression tests for #1477 marker merge bases and safe import overwrite guard."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.import_payload import import_payload
from plate_core.payload_surface import namespace_docs_path
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
            persisted = load_persisted_marker_base(root, "AGENTS.md")
            self.assertTrue(report["ok"])
            self.assertEqual(report["written"], 1)
            self.assertTrue(any(backup_root.iterdir()))
            self.assertEqual(persisted, upstream)

    def test_persisted_base_is_upstream_after_apply_not_merged(self):
        """Merged output must not become base; upstream snapshot must (#1518 review)."""
        upstream_v1 = """<!-- PLATES-CORE:BEGIN demo -->
plate v1 marker
<!-- PLATES-CORE:END demo -->
"""
        upstream_v2 = """outstream header v2

<!-- PLATES-CORE:BEGIN demo -->
plate v2 marker REPLACEMENT
<!-- PLATES-CORE:END demo -->
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(upstream_v1, encoding="utf-8")
            save_persisted_marker_base(root, "AGENTS.md", upstream_v1)
            plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream_v1},
                apply=True,
            )
            customized = """outstream header adopter

<!-- PLATES-CORE:BEGIN demo -->
adopter customization protected
<!-- PLATES-CORE:END demo -->
"""
            agents.write_text(customized, encoding="utf-8")
            report = plan_marker_merge(
                root,
                paths=["AGENTS.md"],
                upstream_texts={"AGENTS.md": upstream_v2},
                apply=True,
            )
            text = agents.read_text(encoding="utf-8")
            base = load_persisted_marker_base(root, "AGENTS.md")
        self.assertTrue(report["ok"])
        self.assertIn("adopter customization protected", text)
        self.assertNotIn("plate v2 marker REPLACEMENT", text)
        self.assertIn("plate v2 marker REPLACEMENT", base or "")
        self.assertNotIn("adopter customization protected", base or "")

    def test_import_then_customize_then_merge_keeps_marker_edit(self):
        """Import seeds upstream base; upstream marker edit must not clobber adopter text."""
        rel = "docs/agents/upstream-template-sync.md"
        marker_token = "ADOPTER_MARKER_EDIT_1477"
        upstream_line = "UPSTREAM_REPLACED_WHOLE_UPGRADES_LINE_1477"
        inside_marker = "Do not overwrite customized files wholesale during upgrades."
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            doc = root / rel
            if not doc.is_file():
                self.skipTest(f"{rel} missing from import payload")
            base_v1 = load_persisted_marker_base(root, rel)
            self.assertIsNotNone(base_v1)
            self.assertIn(inside_marker, base_v1)
            local = doc.read_text(encoding="utf-8")
            local = local.replace(
                "<!-- PLATES-CORE:BEGIN upstream-template-sync -->",
                f"<!-- PLATES-CORE:BEGIN upstream-template-sync -->\n{marker_token}\n",
                1,
            )
            doc.write_text(local, encoding="utf-8")
            upstream_v2 = base_v1.replace(inside_marker, upstream_line)
            self.assertNotEqual(upstream_v2, base_v1)
            self.assertNotIn(marker_token, upstream_v2)
            report = plan_marker_merge(
                root,
                paths=[rel],
                upstream_texts={rel: upstream_v2},
                apply=True,
            )
            final = doc.read_text(encoding="utf-8")
        self.assertTrue(report["ok"])
        self.assertIn(marker_token, final)
        self.assertIn(inside_marker, final)
        self.assertNotIn(upstream_line, final)
        self.assertIn(
            "upstream-template-sync",
            report["files"][0]["preserved_local_sections"],
        )

    def test_import_payload_seeds_marker_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            base = load_persisted_marker_base(root, "AGENTS.md")
            self.assertIsNotNone(base)
            self.assertIn("PLATES-CORE", base or "")

    def test_two_blocks_second_apply_same_upstream_preserves_custom(self):
        """Upstream-only block-b refresh must not clobber customized block-a on repeat apply."""
        upstream_v1 = """<!-- PLATES-CORE:BEGIN block-a -->
upstream a v1
<!-- PLATES-CORE:END block-a -->

<!-- PLATES-CORE:BEGIN block-b -->
upstream b v1
<!-- PLATES-CORE:END block-b -->
"""
        upstream_v2 = """<!-- PLATES-CORE:BEGIN block-a -->
upstream a v1
<!-- PLATES-CORE:END block-a -->

<!-- PLATES-CORE:BEGIN block-b -->
upstream b v2 RELEASE
<!-- PLATES-CORE:END block-b -->
"""
        local_custom = """<!-- PLATES-CORE:BEGIN block-a -->
adopter custom a MUST STAY
<!-- PLATES-CORE:END block-a -->

<!-- PLATES-CORE:BEGIN block-b -->
upstream b v1
<!-- PLATES-CORE:END block-b -->
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "sync.md"
            doc.write_text(local_custom, encoding="utf-8")
            save_persisted_marker_base(root, "sync.md", upstream_v1)
            report1 = plan_marker_merge(
                root,
                paths=["sync.md"],
                upstream_texts={"sync.md": upstream_v2},
                apply=True,
            )
            after_first = doc.read_text(encoding="utf-8")
            report2 = plan_marker_merge(
                root,
                paths=["sync.md"],
                upstream_texts={"sync.md": upstream_v2},
                apply=True,
            )
            final = doc.read_text(encoding="utf-8")
            poisoned_base = load_persisted_marker_base(root, "sync.md")
            save_persisted_marker_base(root, "sync.md", after_first)
            report_poisoned = plan_marker_merge(
                root,
                paths=["sync.md"],
                upstream_texts={"sync.md": upstream_v2},
                apply=True,
            )
            if report_poisoned["ok"]:
                poisoned_final = doc.read_text(encoding="utf-8")
            else:
                poisoned_final = after_first
        self.assertTrue(report1["ok"])
        self.assertEqual(report1["written"], 1)
        self.assertIn("adopter custom a MUST STAY", after_first)
        self.assertIn("upstream b v2 RELEASE", after_first)
        self.assertNotIn("upstream b v1", after_first)
        self.assertEqual(poisoned_base, upstream_v2)
        self.assertTrue(report2["ok"])
        self.assertIn("adopter custom a MUST STAY", final)
        self.assertIn("upstream b v2 RELEASE", final)
        if report_poisoned["ok"]:
            self.assertNotIn(
                "adopter custom a MUST STAY",
                poisoned_final,
                "merged-as-base would clobber customized block on repeat apply",
            )

    def test_identical_reimport_seeds_marker_base_via_skip_path(self):
        """Second apply must re-seed base via skip path, not recreate."""
        rel = "docs/agents/upstream-template-sync.md"
        base_path = Path(".agentic/marker-merge/bases") / rel
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(first["ok"])
            base_after_first = load_persisted_marker_base(root, rel)
            self.assertIsNotNone(base_after_first)
            (root / base_path).unlink()
            self.assertIsNone(load_persisted_marker_base(root, rel))
            second = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(second["ok"])
            self.assertIn(rel, second["skipped"])
            reseeded = load_persisted_marker_base(root, rel)
            self.assertIsNotNone(reseeded)
            self.assertEqual(reseeded, base_after_first)

    def test_namespaced_docs_records_marker_base_at_installed_path(self):
        rel = "docs/agents/upstream-template-sync.md"
        namespaced = namespace_docs_path(rel)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "product.md").write_text("# product\n", encoding="utf-8")
            import_payload(root, strategy="safe", apply=True, namespace_docs=True)
            self.assertTrue((root / namespaced).is_file())
            self.assertIsNotNone(load_persisted_marker_base(root, namespaced))
            self.assertIsNone(load_persisted_marker_base(root, rel))


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

    def test_hash_ledger_refuses_symlink_escape(self):
        from plate_core.import_payload import record_payload_content_hash

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath(".agentic").mkdir()
            root.joinpath(".agentic").joinpath("import-payload").symlink_to("/tmp")
            with self.assertRaises(OSError):
                record_payload_content_hash(root, ".github/labels.yml", b"x")

    def test_hash_ledger_load_refuses_symlink_path(self):
        from plate_core.import_payload import _load_payload_hash_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath(".agentic").mkdir()
            root.joinpath(".agentic").joinpath("import-payload").symlink_to("/tmp")
            self.assertEqual(_load_payload_hash_ledger(root), {})

    def test_hash_ledger_load_refuses_corrupt_json(self):
        from plate_core.import_payload import _load_payload_hash_ledger

        rel = ".agentic/import-payload/content-hashes.json"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / rel
            ledger.parent.mkdir(parents=True)
            ledger.write_text("{not-valid-json", encoding="utf-8")
            self.assertEqual(_load_payload_hash_ledger(root), {})

    def test_safe_import_skips_overwrite_when_ledger_unreadable(self):
        """Unreadable ledger must not unlock manifest safe overwrites."""
        rel = ".github/labels.yml"
        ledger_rel = ".agentic/import-payload/content-hashes.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            dest = root / rel
            dest.write_text(
                "# adopter customized labels\n" + dest.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / ledger_rel).write_text("{bad", encoding="utf-8")
            report = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(report["ok"])
            self.assertIn(rel, report["skipped"])
            self.assertNotIn(rel, report["overwritten"])
            self.assertIn("# adopter customized labels", dest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()