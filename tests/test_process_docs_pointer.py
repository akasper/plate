"""Tests for remote process docs pointer and import behavior (#1511)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core import __version__
from plate_core.import_payload import import_payload
from plate_core.plate_config import CURRENT_CONFIG_VERSION, upgrade_plate_config_dict
from plate_core.plate_config import apply_plate_config_upgrade
from plate_core.process_docs import (
    PROCESS_SUMMARY_GENERATED_MARKER,
    PROCESS_SUMMARY_REL,
    build_process_summary_markdown,
    default_process_docs_config,
    detect_legacy_copied_plate_guides,
    installed_plate_release_tag,
    reconcile_process_docs_artifacts,
    sync_process_docs_in_plate,
)


class TestProcessDocsPointer(unittest.TestCase):
    def test_default_config_matches_installed_version(self):
        cfg = default_process_docs_config()
        self.assertEqual(cfg["base_url"], "https://plateprocess.dev")
        self.assertEqual(cfg["mcp_url"], "https://plateprocess.dev/mcp")
        self.assertEqual(cfg["version"], installed_plate_release_tag())
        self.assertEqual(installed_plate_release_tag(), f"v{__version__}")

    def test_fresh_import_writes_pointer_and_summary_not_guides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            applied = import_payload(root, strategy="safe", apply=True)
            self.assertTrue(applied["ok"])
            summary = root / PROCESS_SUMMARY_REL
            self.assertTrue(summary.is_file())
            self.assertNotIn("docs/agents/", [p.split()[0] for p in applied["created"]])
            self.assertFalse((root / "docs" / "agents").exists())
            plate = json.loads((root / ".plate").read_text(encoding="utf-8"))
            self.assertEqual(plate["version"], CURRENT_CONFIG_VERSION)
            self.assertEqual(
                plate["process_docs"]["version"],
                installed_plate_release_tag(),
            )

    def test_import_respects_custom_endpoint_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(parents=True, exist_ok=True)
            custom_url = "https://docs.example.com"
            plate_path = root / ".plate"
            plate_path.write_text(
                json.dumps(
                    {
                        "version": "1.3",
                        "platform": "posix",
                        "process_docs": {
                            "base_url": custom_url,
                            "mcp_url": f"{custom_url}/mcp",
                            "version": "v9.9.9-custom",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            import_payload(root, strategy="safe", apply=True)
            plate = json.loads(plate_path.read_text(encoding="utf-8"))
            self.assertEqual(plate["process_docs"]["base_url"], custom_url)
            self.assertEqual(plate["process_docs"]["mcp_url"], f"{custom_url}/mcp")
            self.assertEqual(plate["process_docs"]["version"], "v9.9.9-custom")
            text = (root / PROCESS_SUMMARY_REL).read_text(encoding="utf-8")
            self.assertIn(custom_url, text)
            self.assertIn("v9.9.9-custom", text)

    def test_safe_reimport_preserves_edited_process_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_payload(root, strategy="safe", apply=True)
            summary = root / PROCESS_SUMMARY_REL
            summary.write_text(
                summary.read_text(encoding="utf-8")
                + "\n## Air-gapped operations\nKeep local copies.\n",
                encoding="utf-8",
            )
            report = import_payload(root, strategy="safe", apply=True)
            self.assertIn("Air-gapped operations", summary.read_text(encoding="utf-8"))
            self.assertIn(PROCESS_SUMMARY_REL, report["would_skip"])
            self.assertTrue(
                any("Preserved local edits" in n for n in report.get("process_docs_notes") or [])
            )

    def test_default_host_bumps_version_on_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            plate_path = Path(tmp) / ".plate"
            plate_path.write_text(
                json.dumps(
                    {
                        "version": "1.4",
                        "platform": "posix",
                        "process_docs": default_process_docs_config(),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (plate_path.parent / "docs" / "plate").mkdir(parents=True)
            sync_process_docs_in_plate(plate_path, apply=True)
            data = json.loads(plate_path.read_text(encoding="utf-8"))
            self.assertEqual(data["process_docs"]["version"], installed_plate_release_tag())

    def test_config_upgrade_apply_seeds_process_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": "posix"}) + "\n",
                encoding="utf-8",
            )
            report = apply_plate_config_upgrade(root, apply=True)
            self.assertTrue(report.applied)
            self.assertTrue((root / PROCESS_SUMMARY_REL).is_file())
            self.assertIn(PROCESS_SUMMARY_GENERATED_MARKER, (root / PROCESS_SUMMARY_REL).read_text())
            self.assertIn(PROCESS_SUMMARY_REL, report.process_docs_written)

    def test_upgrade_bumps_docs_version_in_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            plate_path = Path(tmp) / ".plate"
            plate_path.write_text(
                json.dumps({"version": "1.3", "platform": "posix"}) + "\n",
                encoding="utf-8",
            )
            upgraded, guidance, _ = upgrade_plate_config_dict(
                json.loads(plate_path.read_text(encoding="utf-8"))
            )
            self.assertEqual(upgraded["version"], "1.4")
            self.assertIn("process_docs", upgraded)
            self.assertTrue(any("plateprocess.dev" in g for g in guidance))
            changed, merged = sync_process_docs_in_plate(plate_path, apply=True)
            self.assertTrue(changed or merged["version"] == installed_plate_release_tag())
            data = json.loads(plate_path.read_text(encoding="utf-8"))
            self.assertEqual(data["process_docs"]["version"], installed_plate_release_tag())

    def test_legacy_guides_left_in_place_with_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "docs" / "bootstrap"
            agents.mkdir(parents=True)
            (agents / "pre-push-hook.md").write_text("# legacy\n", encoding="utf-8")
            self.assertTrue(detect_legacy_copied_plate_guides(root))
            report = import_payload(root, strategy="safe", apply=True)
            self.assertTrue((agents / "pre-push-hook.md").is_file())
            self.assertTrue(report.get("process_docs_notes"))
            self.assertIn("Legacy copied PLATE guides", report["process_docs_notes"][0])

    def test_payload_doc_filter_keeps_goals_only(self):
        from plate_core.process_docs import GOALS_WIKI_PAYLOAD_REL, is_plate_payload_doc_path

        self.assertFalse(is_plate_payload_doc_path(GOALS_WIKI_PAYLOAD_REL))
        self.assertTrue(is_plate_payload_doc_path("docs/agents/autonomous-mode.md"))

    def test_build_process_summary_contains_mcp_hints(self):
        md = build_process_summary_markdown(
            base_url="https://plateprocess.dev",
            mcp_url="https://plateprocess.dev/mcp",
            version="v0.12.0",
        )
        self.assertIn("list_docs", md)
        self.assertIn("plateprocess.dev/mcp", md)


if __name__ == "__main__":
    unittest.main()