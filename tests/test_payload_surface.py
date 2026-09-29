"""Tests for payload discoverability + scripts/plate namespacing (#621)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class TestPayloadSurface(unittest.TestCase):
    def test_list_and_root(self):
        from plate_core.payload_surface import list_payload_files, resolve_payload_root

        root = resolve_payload_root()
        self.assertTrue(root["ok"])
        self.assertTrue(Path(root["path"]).is_dir())

        listing = list_payload_files()
        self.assertTrue(listing["ok"])
        self.assertGreater(listing["count"], 50)
        paths = {f["path"] for f in listing["files"]}
        self.assertIn("scripts/validate_plate_repo.sh", paths)

    def test_classify_and_manifest(self):
        from plate_core.payload_surface import classify_path, show_manifest

        m = show_manifest()
        self.assertIn(m["schema_version"], (1, 2))
        self.assertTrue(m["path_rules"])

        c = classify_path(".github/workflows/ci.yml")
        self.assertTrue(c["ok"])
        self.assertEqual(c["path_rule"]["on_conflict"], "install_as")

    def test_namespace_when_product_scripts_exist(self):
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "scripts").mkdir()
            (Path(tmp) / "scripts" / "app-build.sh").write_text("#!/bin/sh\n", encoding="utf-8")

            dry = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertTrue(dry["namespace_scripts"])
            joined = " ".join(dry["would_create"])
            self.assertIn("scripts/plate/", joined)

            applied = import_payload(tmp, strategy="safe", apply=True)
            self.assertTrue(
                (Path(tmp) / "scripts" / "plate" / "validate_plate_repo.sh").is_file()
            )
            # product script preserved
            self.assertTrue((Path(tmp) / "scripts" / "app-build.sh").is_file())
            # workflow refs rewritten when present
            plate_ci = Path(tmp) / ".github" / "workflows" / "ci.yml"
            if plate_ci.is_file():
                text = plate_ci.read_text(encoding="utf-8")
                if "validate_plate_repo" in text:
                    self.assertIn("scripts/plate/validate_plate_repo", text)

    def test_namespace_when_product_docs_exist(self):
        """#1015: namespace PLATE docs under docs/plate/ when product docs present."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs" / "prototype").mkdir()
            (Path(tmp) / "docs" / "prototype" / "README.md").write_text(
                "# Product Prototype Docs\n", encoding="utf-8"
            )

            dry = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertTrue(dry["namespace_docs"])
            joined = " ".join(dry["would_create"])
            # PLATE docs subdirs should be namespaced
            self.assertIn("docs/plate/", joined)

            applied = import_payload(tmp, strategy="safe", apply=True)
            # PLATE scaffolding docs namespaced
            self.assertTrue(
                (Path(tmp) / "docs" / "plate" / "design").is_dir()
                or (Path(tmp) / "docs" / "plate" / "wiki").is_dir()
                or (Path(tmp) / "docs" / "plate" / "research").is_dir()
            )
            # product docs preserved
            self.assertTrue(
                (Path(tmp) / "docs" / "prototype" / "README.md").is_file()
            )
            # doc refs rewritten in AGENTS.md when present
            agents_md = Path(tmp) / "AGENTS.md"
            if agents_md.is_file():
                text = agents_md.read_text(encoding="utf-8")
                # Should have rewritten refs (if any existed)
                if "docs/design/" in text or "docs/research/" in text:
                    self.assertTrue(
                        "docs/plate/design/" in text or "docs/plate/research/" in text
                    )

    def test_product_readme_triggers_namespace_and_is_preserved(self):
        """A product docs/README.md is not PLATE just because of the filename."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            readme = docs / "README.md"
            readme.write_text("# Product handbook\n", encoding="utf-8")
            guide = docs / "playwright-e2e-guide.md"
            guide.write_text("# Our app e2e notes\n", encoding="utf-8")

            dry = import_payload(tmp, strategy="force", dry_run=True)
            self.assertTrue(dry["namespace_docs"])

            applied = import_payload(tmp, strategy="force", apply=True)
            self.assertTrue(applied["namespace_docs"])
            self.assertEqual(readme.read_text(encoding="utf-8"), "# Product handbook\n")
            self.assertEqual(guide.read_text(encoding="utf-8"), "# Our app e2e notes\n")
            plate_readme = (docs / "plate" / "README.md").read_text(encoding="utf-8")
            self.assertIn("docs/plate/wiki/", plate_readme)
            self.assertNotIn("docs/wiki/", plate_readme)
            home = (docs / "plate" / "wiki" / "Home.md").read_text(encoding="utf-8")
            self.assertIn("docs/plate/wiki/", home)
            self.assertNotIn("`docs/wiki/`", home)

    def test_namespace_migration_guide_ships_in_payload(self):
        from plate_core.payload_surface import list_payload_files

        paths = {item["path"] for item in list_payload_files()["files"]}
        self.assertIn("docs/migration/namespace-docs-migration.md", paths)

    def test_no_namespace_when_only_plate_docs_exist(self):
        """Should not namespace when only PLATE scaffolding docs exist."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            # Install first time (no product docs)
            first = import_payload(tmp, strategy="safe", apply=True)
            self.assertFalse(first["namespace_docs"])

            # Install again (only PLATE docs present, namespaced or not)
            second = import_payload(tmp, strategy="safe", dry_run=True)
            self.assertFalse(second["namespace_docs"])

    def test_cli_payload_registered(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("payload", help_text)


if __name__ == "__main__":
    unittest.main()
