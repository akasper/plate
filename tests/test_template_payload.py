import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from plate_core.mcp.tools import InitPlaywrightTool
from plate_core.template_payload import (
    classify_template_file,
    load_template_payload_manifest,
    manifest_path,
    payload_root,
    resolve_template_source,
    should_include_template_file,
)


class ResolveTemplateSourceTests(unittest.TestCase):
    def test_resolve_template_source_defaults_to_package_payload(self):
        root, kind = resolve_template_source()
        self.assertEqual(kind, "package_payload")
        self.assertEqual(root, payload_root())
        self.assertTrue(root.exists())

    def test_resolve_template_source_raises_without_payload_or_opt_in(self):
        missing = Path("/tmp/plate-nonexistent-payload-for-test")
        with patch("plate_core.template_payload.payload_root", return_value=missing):
            env = os.environ.copy()
            env.pop("PLATE_ALLOW_LEGACY_TEMPLATE_SIBLING", None)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError) as ctx:
                    resolve_template_source()
        self.assertIn("gh plate bootstrap", str(ctx.exception))
        self.assertIn("do not clone", str(ctx.exception).lower())

    def test_legacy_sibling_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "my-repo"
            legacy = base / "plate_template"
            repo.mkdir()
            legacy.mkdir()
            missing_payload = base / "no-payload"
            with patch("plate_core.template_payload.payload_root", return_value=missing_payload):
                with patch("plate_core.template_payload.Path.cwd", return_value=repo):
                    with patch.dict(os.environ, {"PLATE_ALLOW_LEGACY_TEMPLATE_SIBLING": "1"}):
                        with warnings.catch_warnings(record=True) as caught:
                            warnings.simplefilter("always")
                            root, kind = resolve_template_source()
        self.assertEqual(kind, "legacy_sibling_fallback")
        self.assertEqual(root, legacy)
        self.assertTrue(any(isinstance(w.message, DeprecationWarning) for w in caught))


class TemplatePayloadManifestTests(unittest.TestCase):
    def test_manifest_exists_and_loads(self):
        self.assertTrue(manifest_path().exists())
        manifest = load_template_payload_manifest()
        self.assertIn(manifest.schema_version, (1, 2))
        self.assertGreater(len(manifest.include_globs), 0)
        self.assertGreater(len(manifest.path_rules), 0)

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

    def test_path_rules_ci_install_as(self):
        """#617: differing ci.yml plans install as plate-ci.yml."""
        from plate_core.template_payload import match_path_rule, resolve_conflict_plan

        manifest = load_template_payload_manifest()
        rule = match_path_rule(".github/workflows/ci.yml", manifest)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.on_conflict, "install_as")
        self.assertEqual(rule.install_as, ".github/workflows/plate-ci.yml")

        plan = resolve_conflict_plan(
            ".github/workflows/ci.yml",
            dest_exists=True,
            identical=False,
            strategy="safe",
            manifest=manifest,
        )
        self.assertEqual(plan["action"], "create_as")
        self.assertEqual(plan["target_path"], ".github/workflows/plate-ci.yml")

        green = resolve_conflict_plan(
            ".github/workflows/ci.yml",
            dest_exists=False,
            identical=False,
            strategy="safe",
            manifest=manifest,
        )
        self.assertEqual(green["action"], "create")
        self.assertEqual(green["target_path"], ".github/workflows/ci.yml")

    def test_path_rules_root_conflict(self):
        from plate_core.template_payload import resolve_conflict_plan

        manifest = load_template_payload_manifest()
        plan = resolve_conflict_plan(
            "package.json",
            dest_exists=True,
            identical=False,
            strategy="safe",
            manifest=manifest,
        )
        self.assertEqual(plan["action"], "conflict")


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


class TemplatePayloadAdopterClaimsTests(unittest.TestCase):
    """Proves: template_payload ships adopter harness claims (#917 / #364 residual).

    Claim: greenfield import gets AGENTS/SPEC, e2e scaffolding, and core PLATE
    workflows — without requiring monorepo-only plugin-structure.spec.ts paths.
    """

    REQUIRED_PATHS = (
        "AGENTS.md",
        "SPEC.md",
        "README.md",
        "playwright.config.ts",
        "tests/e2e/README.md",
        "tests/e2e/specs/example.spec.ts",
        ".github/workflows/ci.yml",
        ".github/workflows/feedback-resolution-check.yml",
        ".github/workflows/pr-title-check.yml",
        ".github/workflows/label-check.yml",
    )

    def test_payload_contains_adopter_harness_files(self):
        root = payload_root()
        missing = [p for p in self.REQUIRED_PATHS if not (root / p).is_file()]
        self.assertEqual(missing, [], f"payload missing adopter files: {missing}")

    def test_list_payload_files_includes_adopter_paths(self):
        from plate_core.payload_surface import list_payload_files

        listing = list_payload_files()
        self.assertTrue(listing.get("ok"))
        paths = {f["path"] for f in listing.get("files") or []}
        for p in self.REQUIRED_PATHS:
            self.assertIn(p, paths, f"list_payload_files missing {p}")

    def test_import_dry_run_plans_adopter_scaffold(self):
        """Proves: import-payload dry-run would create key adopter scaffold files."""
        from plate_core.import_payload import import_payload

        with tempfile.TemporaryDirectory() as tmp:
            report = import_payload(tmp, strategy="safe", dry_run=True)
            would = set(report.get("would_create") or [])
            # Paths may be namespaced for scripts; AGENTS and e2e should be direct
            for p in (
                "AGENTS.md",
                "playwright.config.ts",
                "tests/e2e/README.md",
                ".github/workflows/ci.yml",
            ):
                self.assertTrue(
                    any(w == p or w.endswith("/" + p) for w in would),
                    f"dry-run would_create missing {p}; sample={sorted(would)[:12]}",
                )

    def test_e2e_readme_documents_harness_purpose(self):
        text = (payload_root() / "tests" / "e2e" / "README.md").read_text(encoding="utf-8")
        self.assertIn("CLI-agnostic", text)
        self.assertIn("npm test", text)


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
