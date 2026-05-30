import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.tools import InitPlaywrightTool
from plate_core.template_payload import (
    classify_template_file,
    load_template_payload_manifest,
    manifest_path,
    payload_root,
    should_include_template_file,
)


class TemplatePayloadManifestTests(unittest.TestCase):
    def test_manifest_exists_and_loads(self):
        self.assertTrue(manifest_path().exists())
        manifest = load_template_payload_manifest()
        self.assertEqual(manifest.schema_version, 1)
        self.assertGreater(len(manifest.include_globs), 0)

    def test_manifest_classifies_payload_files_as_scaffolding(self):
        manifest = load_template_payload_manifest()
        self.assertEqual(classify_template_file("playwright.config.ts", manifest), "copy_to_downstream")
        self.assertEqual(
            classify_template_file(".github/workflows/plates-start-feature.yml", manifest),
            "copy_to_downstream",
        )

    def test_manifest_excludes_agentic_costs(self):
        manifest = load_template_payload_manifest()
        self.assertFalse(should_include_template_file(".agentic/COSTS.md", manifest))
        self.assertEqual(classify_template_file(".agentic/COSTS.md", manifest), "exclude")


class TemplatePayloadInventoryTests(unittest.TestCase):
    def test_inventory_file_exists_and_matches_payload(self):
        inventory_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "plate_core"
            / "data"
            / "template_payload_inventory.json"
        )
        self.assertTrue(inventory_path.exists(), "Missing template_payload_inventory.json")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        self.assertEqual(inventory.get("schema_version"), 1)
        files = inventory.get("files", [])
        self.assertGreater(len(files), 0)

        payload = payload_root()
        self.assertTrue(payload.exists(), "Template payload directory is missing")
        listed_paths = {item["path"] for item in files}
        actual_paths = {
            p.relative_to(payload).as_posix()
            for p in payload.rglob("*")
            if p.is_file()
        }
        self.assertEqual(listed_paths, actual_paths)

        for item in files:
            self.assertEqual(item.get("classification"), "copy_to_downstream")


class InitPlaywrightPayloadTests(unittest.TestCase):
    def test_init_playwright_uses_payload_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp = Path(tmpdir)
            template = temp / "template-source"
            repo = temp / "target-repo"
            (template / "tests" / "e2e" / "specs").mkdir(parents=True)
            (template / "scripts").mkdir(parents=True)
            repo.mkdir(parents=True)

            (template / "playwright.config.ts").write_text("// config\n", encoding="utf-8")
            (template / "tests" / "e2e" / "specs" / "example.spec.ts").write_text(
                "test('ok', async () => {});\n",
                encoding="utf-8",
            )
            (template / "scripts" / "e2e-record.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (template / "scripts" / "e2e-record.ps1").write_text("Write-Host 'ok'\n", encoding="utf-8")
            (repo / "package.json").write_text('{"name":"demo","devDependencies":{}}', encoding="utf-8")

            with patch("plate_core.mcp.tools.resolve_template_source_root", return_value=template):
                result = InitPlaywrightTool.execute(str(repo))

            self.assertEqual(result.get("status"), "success")
            self.assertTrue((repo / "playwright.config.ts").exists())
            self.assertTrue((repo / "tests" / "e2e" / "specs" / "example.spec.ts").exists())
            self.assertTrue((repo / "scripts" / "e2e-record.sh").exists())
            self.assertTrue((repo / "scripts" / "e2e-record.ps1").exists())


if __name__ == "__main__":
    unittest.main()
