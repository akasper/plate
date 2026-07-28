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

    def test_cli_payload_registered(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("payload", help_text)


if __name__ == "__main__":
    unittest.main()
