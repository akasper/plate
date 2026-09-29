"""`.plate` platform selects PLATE-owned script twins at copy time."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import resolve_bootstrap_platform, run_bootstrap
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport
from plate_core.import_payload import import_payload, list_payload_relative_paths
from plate_core.payload_surface import (
    PLATE_SCRIPT_BASENAMES,
    filter_plate_scripts,
    prepare_copied_text,
)
from plate_core.plate_config import (
    CURRENT_CONFIG_VERSION,
    PlateConfig,
    PlateConfigError,
    _migrate_1_2_to_1_3,
    load_plate_config,
    upgrade_plate_config_dict,
    validate_plate_config,
)
from plate_core.template_payload import payload_root


PS1_TWINS = sorted(name for name in PLATE_SCRIPT_BASENAMES if name.endswith(".ps1"))
SH_TWINS = sorted(name for name in PLATE_SCRIPT_BASENAMES if name.endswith(".sh"))
CI_TEST_JOB = "  test:\n    needs: labels\n    runs-on: ubuntu-latest\n"
CI_WINDOWS_JOB = "  test:\n    needs: labels\n    runs-on: windows-latest\n"
BASH_VALIDATE = "bash scripts/validate_plate_repo.sh ."
PWSH_VALIDATE = "pwsh -File scripts/ValidatePlateRepo.ps1 -Root ."
PWSH_VALIDATE_NAMESPACED = "pwsh -File scripts/plate/ValidatePlateRepo.ps1 -Root ."


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def _twin_names(paths: list[str], suffix: str) -> list[str]:
    names = []
    for rel in paths:
        name = Path(rel).name
        if name.endswith(suffix) and name in PLATE_SCRIPT_BASENAMES:
            names.append(name)
    return sorted(names)


class PlatformFilterTests(unittest.TestCase):
    def test_list_payload_keeps_the_superset(self):
        paths = list_payload_relative_paths()
        self.assertIn("scripts/gif-from-video.ps1", paths)
        self.assertIn("scripts/gif-from-video.sh", paths)
        self.assertIn("scripts/README.md", paths)
        self.assertIn("scripts/dev-server.js", paths)

    def test_posix_omits_only_plate_ps1_twins(self):
        paths = list_payload_relative_paths()
        kept, omitted = filter_plate_scripts(paths, "posix")
        self.assertEqual(_twin_names(omitted, ".ps1"), PS1_TWINS)
        self.assertEqual(len(PS1_TWINS), 6)
        self.assertEqual(_twin_names(omitted, ".sh"), [])
        self.assertIn("scripts/README.md", kept)
        self.assertIn("scripts/dev-server.js", kept)
        self.assertNotIn("scripts/custom.ps1", omitted)

    def test_windows_omits_only_plate_sh_twins(self):
        paths = list_payload_relative_paths()
        kept, omitted = filter_plate_scripts(paths, "windows")
        self.assertEqual(_twin_names(omitted, ".sh"), SH_TWINS)
        self.assertEqual(_twin_names(omitted, ".ps1"), [])
        self.assertIn("scripts/README.md", kept)
        self.assertIn("scripts/dev-server.js", kept)

    def test_dual_stack_omits_nothing(self):
        paths = list_payload_relative_paths()
        kept, omitted = filter_plate_scripts(paths, "posix-and-windows")
        self.assertEqual(omitted, [])
        self.assertEqual(kept, paths)

    def test_adopter_owned_script_is_not_a_plate_flavor(self):
        kept, omitted = filter_plate_scripts(
            ["scripts/custom.ps1", "scripts/plate/mine.ps1", "scripts/README.md"],
            "posix",
        )
        self.assertEqual(omitted, [])
        self.assertEqual(len(kept), 3)

    def test_windows_ci_rewrite_is_limited_to_the_test_job(self):
        source = (
            "  labels:\n    runs-on: ubuntu-latest\n"
            + CI_TEST_JOB
            + "    steps:\n      - run: "
            + BASH_VALIDATE
            + "\n"
        )
        rewritten = prepare_copied_text(
            ".github/workflows/ci.yml",
            source,
            "windows",
            namespaced=False,
        )
        self.assertIn(CI_WINDOWS_JOB, rewritten)
        self.assertNotIn(CI_TEST_JOB, rewritten)
        self.assertIn(PWSH_VALIDATE, rewritten)
        self.assertNotIn(BASH_VALIDATE, rewritten)
        self.assertIn("  labels:\n    runs-on: ubuntu-latest\n", rewritten)

        namespaced = prepare_copied_text(
            ".github/workflows/ci.yml",
            source,
            "windows",
            namespaced=True,
        )
        self.assertIn(PWSH_VALIDATE_NAMESPACED, namespaced)
        self.assertIn(CI_WINDOWS_JOB, namespaced)

        untouched = prepare_copied_text(
            ".github/workflows/ci.yml",
            source,
            "posix",
            namespaced=False,
        )
        self.assertEqual(untouched, source)

    def test_windows_e2e_gif_job_calls_powershell_helper(self):
        source = _lf((payload_root() / ".github" / "workflows" / "test-e2e.yml").read_text(encoding="utf-8"))
        rewritten = _lf(
            prepare_copied_text(
                ".github/workflows/test-e2e.yml",
                source,
                "windows",
                namespaced=False,
            )
        )
        self.assertNotIn("gif-from-video.sh", rewritten)
        self.assertIn('gif_script="./scripts/gif-from-video.ps1"', rewritten)
        self.assertIn('pwsh -File "$gif_script"', rewritten)
        self.assertIn("sudo apt-get install -y ffmpeg", rewritten)
        self.assertIn("Required GIF script is missing", rewritten)
        self.assertIn("name: Playwright E2E Tests", rewritten)
        self.assertIn("runs-on: ubuntu-latest", rewritten)

        namespaced = _lf(
            prepare_copied_text(
                ".github/workflows/test-e2e.yml",
                source,
                "windows",
                namespaced=True,
            )
        )
        self.assertIn('gif_script="./scripts/plate/gif-from-video.ps1"', namespaced)
        self.assertNotIn("gif-from-video.sh", namespaced)

        posix = _lf(
            prepare_copied_text(
                ".github/workflows/test-e2e.yml",
                source,
                "posix",
                namespaced=False,
            )
        )
        self.assertEqual(posix, source)
        self.assertIn("./scripts/gif-from-video.sh", source)

    def test_windows_package_json_and_namespaced_recorder_paths(self):
        source = _lf((payload_root() / "package.json").read_text(encoding="utf-8"))
        windows = _lf(prepare_copied_text("package.json", source, "windows", namespaced=False))
        self.assertIn('"record:e2e": "pwsh -File scripts/e2e-record.ps1"', windows)
        self.assertNotIn("e2e-record.sh", windows)
        namespaced_windows = _lf(
            prepare_copied_text("package.json", source, "windows", namespaced=True)
        )
        self.assertIn(
            '"record:e2e": "pwsh -File scripts/plate/e2e-record.ps1"',
            namespaced_windows,
        )
        self.assertNotIn("e2e-record.sh", namespaced_windows)
        posix = _lf(prepare_copied_text("package.json", source, "posix", namespaced=False))
        self.assertEqual(posix, source)
        posix_namespaced = _lf(
            prepare_copied_text("package.json", source, "posix", namespaced=True)
        )
        self.assertIn("bash scripts/plate/e2e-record.sh", posix_namespaced)
        self.assertIn("node scripts/plate/dev-server.js", posix_namespaced)

        recorder = '$gifScript = ".\\scripts\\gif-from-video.ps1"\n'
        rewritten = prepare_copied_text(
            "scripts/e2e-record.ps1",
            recorder,
            "windows",
            namespaced=True,
        )
        self.assertIn('.\\scripts\\plate\\gif-from-video.ps1', rewritten)
        self.assertNotIn('.\\scripts\\gif-from-video.ps1', rewritten.replace(".\\scripts\\plate\\", ".\\"))

    def test_upgrade_missing_platform_becomes_posix_and_keeps_explicit(self):
        upgraded, _guidance, origin = upgrade_plate_config_dict(
            {"version": "1.2", "autonomy": {"enabled": False, "risk_tolerance": "off"}}
        )
        self.assertEqual(origin, "1.2")
        self.assertEqual(upgraded["version"], CURRENT_CONFIG_VERSION)
        self.assertEqual(upgraded["platform"], "posix")
        self.assertFalse(upgraded["autonomy"]["enabled"])

        kept, _guidance, _origin = upgrade_plate_config_dict(
            {
                "version": "1.2",
                "platform": "posix-and-windows",
                "autonomy": {"enabled": False, "risk_tolerance": "off"},
            }
        )
        self.assertEqual(kept["platform"], "posix-and-windows")
        self.assertEqual(kept["version"], "1.3")

    def test_invalid_platform_fails_closed(self):
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.3", "platform": "auto"}, strict=True)
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.3", "platform": ["posix"]}, strict=True)


class ImportPlatformTests(unittest.TestCase):
    def test_posix_apply_omits_ps1_and_keeps_adopter_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "scripts").mkdir()
            (target / "scripts" / "custom.ps1").write_text("Write-Host custom\n", encoding="utf-8")
            (target / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.2",
                        "platform": "windows",
                        "autonomy": {"enabled": False},
                    }
                ),
                encoding="utf-8",
            )
            report = import_payload(
                target,
                apply=True,
                dry_run=False,
                platform="posix",
                namespace_scripts=False,
            )
            self.assertTrue(report["ok"], report.get("error"))
            self.assertEqual(report["platform"], "posix")
            self.assertEqual(_twin_names(report["omitted_for_platform"], ".ps1"), PS1_TWINS)
            self.assertTrue((target / "scripts" / "custom.ps1").is_file())
            self.assertTrue((target / "scripts" / "gif-from-video.sh").is_file())
            self.assertFalse((target / "scripts" / "gif-from-video.ps1").exists())
            self.assertTrue((target / "scripts" / "README.md").is_file())
            self.assertTrue((target / "scripts" / "dev-server.js").is_file())
            stored = json.loads((target / ".plate").read_text(encoding="utf-8"))
            self.assertEqual(stored["platform"], "posix")
            self.assertEqual(stored["version"], "1.2")
            self.assertFalse(stored["autonomy"]["enabled"])

    def test_windows_apply_rewrites_ci_and_can_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            report = import_payload(
                target,
                apply=True,
                dry_run=False,
                platform="windows",
                namespace_scripts=True,
            )
            self.assertTrue(report["ok"], report.get("error"))
            self.assertEqual(_twin_names(report["omitted_for_platform"], ".sh"), SH_TWINS)
            self.assertTrue((target / "scripts" / "plate" / "gif-from-video.ps1").is_file())
            self.assertFalse((target / "scripts" / "gif-from-video.sh").exists())
            self.assertFalse((target / "scripts" / "plate" / "gif-from-video.sh").exists())
            ci = _lf((target / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
            self.assertIn(CI_WINDOWS_JOB, ci)
            self.assertNotIn(CI_TEST_JOB, ci)
            self.assertIn(PWSH_VALIDATE_NAMESPACED, ci)
            source = _lf((payload_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
            self.assertIn(CI_TEST_JOB, source)
            self.assertIn(BASH_VALIDATE, source)
            seeded = json.loads((target / ".plate").read_text(encoding="utf-8"))
            self.assertEqual(seeded["platform"], "windows")

    def test_stored_and_explicit_invalid_platform_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": "auto"}),
                encoding="utf-8",
            )
            stored = import_payload(target, dry_run=True)
            self.assertFalse(stored["ok"])
            self.assertIn("invalid platform", stored["error"])
            explicit = import_payload(target, dry_run=True, platform="laptop")
            self.assertFalse(explicit["ok"])
            self.assertIn("invalid platform", explicit["error"])

    def test_absent_platform_key_means_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".plate").write_text(json.dumps({"version": "1.2"}), encoding="utf-8")
            report = import_payload(target, dry_run=True)
            self.assertTrue(report["ok"], report.get("error"))
            self.assertEqual(report["platform"], "posix")
            self.assertIn("scripts/gif-from-video.ps1", report["omitted_for_platform"])

    def test_empty_stored_platform_fails_and_null_means_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": ""}),
                encoding="utf-8",
            )
            empty = import_payload(target, dry_run=True)
            self.assertFalse(empty["ok"])
            self.assertIn("invalid platform", empty["error"])
            (target / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": None}),
                encoding="utf-8",
            )
            null = import_payload(target, dry_run=True)
            self.assertTrue(null["ok"], null.get("error"))
            self.assertEqual(null["platform"], "posix")
            for explicit in ("", " ", "\t"):
                overridden = import_payload(target, dry_run=True, platform=explicit)
                self.assertFalse(overridden["ok"], explicit)
                self.assertIn("invalid platform", overridden["error"])

    def test_null_platform_loads_as_posix_and_empty_stays_invalid(self):
        self.assertEqual(PlateConfig.from_dict({"version": "1.3", "platform": None}).platform, "posix")
        self.assertEqual(PlateConfig.from_dict({"version": "1.3"}).platform, "posix")
        self.assertEqual(PlateConfig.from_dict({"version": "1.3", "platform": ""}).platform, "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": None}),
                encoding="utf-8",
            )
            loaded = load_plate_config(root)
            self.assertEqual(loaded.platform, "posix")
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "platform": ""}),
                encoding="utf-8",
            )
            with self.assertRaises(PlateConfigError):
                load_plate_config(root)

    def test_migration_leaves_empty_platform_for_the_schema(self):
        with self.assertRaises(PlateConfigError):
            validate_plate_config({"version": "1.3", "platform": ""})
        left = _migrate_1_2_to_1_3({"version": "1.2", "platform": ""})
        self.assertEqual(left["platform"], "")
        self.assertEqual(_migrate_1_2_to_1_3({"version": "1.2"})["platform"], "posix")
        self.assertEqual(
            _migrate_1_2_to_1_3({"version": "1.2", "platform": None})["platform"],
            "posix",
        )
        with self.assertRaises(PlateConfigError):
            upgrade_plate_config_dict({"version": "1.2", "platform": ""})


class BootstrapPlatformTests(unittest.TestCase):
    def _health(self, *, present: bool, open_epics: int = 1, open_questions: int = 1) -> HealthReport:
        return HealthReport(
            repo="akasper/plat",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=open_epics,
            status="pass",
            goals_page_present=True,
            open_question_count=open_questions,
            plate_config_present=present,
            plate_config_valid=present,
            curiosity_answers_present=False,
        )

    def _template(self, root: Path) -> None:
        (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "gif-from-video.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (root / "scripts" / "gif-from-video.ps1").write_text("Write-Host gif\n", encoding="utf-8")
        workflow = root / ".github" / "workflows"
        workflow.mkdir(parents=True)
        (workflow / "ci.yml").write_text(
            "name: ci\n"
            "jobs:\n"
            "  labels:\n"
            "    runs-on: ubuntu-latest\n"
            + CI_TEST_JOB
            + "    steps:\n"
            + f"      - run: {BASH_VALIDATE}\n",
            encoding="utf-8",
        )

    def test_remote_platform_filters_and_rewrites_without_deleting_plan_phrase(self):
        puts: list[dict] = []
        plate = {
            "type": "file",
            "sha": "sha-1",
            "encoding": "base64",
            "content": base64.b64encode(
                json.dumps({"version": "1.3", "platform": "windows"}).encode("utf-8")
            ).decode("ascii"),
        }

        def api_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            method = kwargs.get("method", "GET")
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint.endswith("/git/ref/heads/main"):
                return {"ref": "refs/heads/main"}
            if "/issues?" in endpoint:
                return [{"title": "[Question]: existing"}]
            if endpoint.endswith("/contents/.plate") and method == "GET":
                return plate
            if "/contents/" in endpoint and method == "GET":
                raise GhApiError("HTTP 404 Not Found")
            if "/contents/" in endpoint and method == "PUT":
                puts.append({"endpoint": endpoint, "fields": kwargs.get("fields")})
                return {}
            if "/branches/" in endpoint:
                return {"name": "main", "commit": {"sha": "abc123"}}
            return {}

        client = Mock()
        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._template(root)
            with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                with patch("plate_core.bootstrap.get_health", return_value=self._health(present=True)):
                    report = run_bootstrap("akasper/plat", apply_mode=True, client=client)
        self.assertEqual(report.platform, "windows")
        endpoints = [item["endpoint"] for item in puts]
        self.assertTrue(any(item.endswith("gif-from-video.ps1") for item in endpoints))
        self.assertFalse(any(item.endswith("gif-from-video.sh") for item in endpoints))
        ci_put = next(item for item in puts if item["endpoint"].endswith("ci.yml"))
        body = _lf(base64.b64decode(ci_put["fields"]["content"]).decode("utf-8"))
        self.assertIn(CI_WINDOWS_JOB, body)
        self.assertIn(PWSH_VALIDATE, body)
        self.assertFalse(any(item["endpoint"].endswith("/contents/.plate") for item in puts))

    def test_explicit_platform_updates_existing_plate_and_copy_phrase_survives(self):
        puts: list[dict] = []
        plate = {
            "type": "file",
            "sha": "sha-9",
            "encoding": "base64",
            "content": base64.b64encode(
                json.dumps({"version": "1.2", "platform": "windows", "autonomy": {"enabled": False}}).encode("utf-8")
            ).decode("ascii"),
        }

        def api_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            method = kwargs.get("method", "GET")
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main"}
            if "/issues?" in endpoint:
                return []
            if endpoint.endswith("/contents/.plate") and method == "GET":
                return plate
            if "/contents/" in endpoint and method == "GET":
                return {"type": "file"}
            return {}

        client = Mock()
        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._template(root)
            empty = root / "empty-checkout"
            empty.mkdir()
            with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                with patch(
                    "plate_core.bootstrap.get_health",
                    return_value=self._health(present=False, open_epics=0, open_questions=0),
                ):
                    planned = run_bootstrap(
                        "akasper/plat",
                        apply_mode=False,
                        client=client,
                        local_root=empty,
                    )
        copy_action = next(action for action in planned.actions if action.name == "copy-template-payload")
        self.assertIn("Copy 3 template payload files", copy_action.detail)
        self.assertIn("for platform posix", copy_action.detail)
        self.assertEqual(planned.platform, "posix")

        def apply_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            method = kwargs.get("method", "GET")
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint.endswith("/git/ref/heads/main"):
                return {"ref": "refs/heads/main"}
            if "/issues?" in endpoint:
                return [{"title": "[Question]: existing"}]
            if endpoint.endswith("/contents/.plate") and method == "GET":
                return plate
            if "/contents/" in endpoint and method == "GET":
                raise GhApiError("HTTP 404 Not Found")
            if method == "PUT":
                puts.append({"endpoint": endpoint, "fields": kwargs.get("fields")})
                return {}
            if "/branches/" in endpoint:
                return {"name": "main", "commit": {"sha": "abc123"}}
            return {}

        client.api.side_effect = apply_side
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._template(root)
            with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                with patch("plate_core.bootstrap.get_health", return_value=self._health(present=True)):
                    applied = run_bootstrap(
                        "akasper/plat",
                        apply_mode=True,
                        client=client,
                        platform="posix",
                    )
        self.assertEqual(applied.platform, "posix")
        plate_put = next(item for item in puts if item["endpoint"].endswith("/contents/.plate"))
        stored = json.loads(base64.b64decode(plate_put["fields"]["content"]).decode("utf-8"))
        self.assertEqual(stored["platform"], "posix")
        self.assertEqual(stored["version"], "1.2")
        self.assertFalse(stored["autonomy"]["enabled"])
        self.assertEqual(plate_put["fields"]["sha"], "sha-9")
        endpoints = [item["endpoint"] for item in puts]
        self.assertTrue(endpoints[0].endswith("/contents/.plate"))
        self.assertTrue(any(item.endswith("gif-from-video.sh") for item in endpoints))
        self.assertFalse(any(item.endswith("gif-from-video.ps1") for item in endpoints))

    def test_unreadable_remote_plate_falls_back_to_posix(self):
        def api_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main"}
            if "/issues?" in endpoint:
                return []
            if endpoint.endswith("/contents/.plate"):
                return {"type": "file"}
            return {}

        client = Mock()
        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._template(root)
            with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                with patch("plate_core.bootstrap.get_health", return_value=self._health(present=True)):
                    report = run_bootstrap("akasper/plat", apply_mode=False, client=client)
        self.assertEqual(report.platform, "posix")

    def test_invalid_remote_platform_fails_closed(self):
        plate = {
            "content": base64.b64encode(json.dumps({"platform": "auto"}).encode("utf-8")).decode("ascii"),
            "sha": "sha",
        }

        def api_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main"}
            if endpoint.endswith("/contents/.plate"):
                return plate
            return {}

        client = Mock()
        client.api.side_effect = api_side
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._template(root)
            with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                with patch("plate_core.bootstrap.get_health", return_value=self._health(present=True)):
                    with self.assertRaises(PlateConfigError):
                        run_bootstrap("akasper/plat", apply_mode=False, client=client)

    def test_malformed_remote_plate_json_fails_closed(self):
        plate = {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(b'{"platform": "posix",}').decode("ascii"),
        }
        client = Mock()
        client.api.return_value = plate
        with self.assertRaises(PlateConfigError) as caught:
            resolve_bootstrap_platform(None, "akasper/plat", client, plate_config_present=True)
        self.assertIn("invalid JSON", str(caught.exception))
        client.api.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(b"[]").decode("ascii"),
        }
        with self.assertRaises(PlateConfigError) as caught:
            resolve_bootstrap_platform(None, "akasper/plat", client, plate_config_present=True)
        self.assertIn("top-level object", str(caught.exception))

    def test_empty_stored_platform_fails_and_null_means_posix(self):
        client = Mock()
        client.api.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(b'{"version":"1.3","platform":""}').decode("ascii"),
        }
        with self.assertRaises(PlateConfigError) as caught:
            resolve_bootstrap_platform(None, "akasper/plat", client, plate_config_present=True)
        self.assertIn("invalid platform", str(caught.exception))
        client.api.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(b'{"version":"1.3","platform":null}').decode("ascii"),
        }
        self.assertEqual(
            resolve_bootstrap_platform(None, "akasper/plat", client, plate_config_present=True),
            "posix",
        )
        client.api.reset_mock()
        for explicit in ("", " ", "\t"):
            with self.assertRaises(PlateConfigError) as caught:
                resolve_bootstrap_platform(explicit, "akasper/plat", client, plate_config_present=True)
            self.assertIn("invalid platform", str(caught.exception))
        client.api.assert_not_called()
        self.assertEqual(
            resolve_bootstrap_platform(" posix ", "akasper/plat", client, plate_config_present=True),
            "posix",
        )

    def test_explicit_platform_rejects_bad_plate_before_writes(self):
        puts: list[str] = []
        plate: dict = {}

        def api_side(endpoint, *args, **kwargs):
            endpoint = str(endpoint)
            method = kwargs.get("method", "GET")
            if method == "PUT":
                puts.append(endpoint)
                return {}
            if endpoint == "repos/akasper/plat":
                return {"has_wiki": True, "default_branch": "main", "permissions": {"push": True}}
            if endpoint.endswith("/git/ref/heads/main"):
                return {"ref": "refs/heads/main"}
            if endpoint.endswith("/contents/.plate"):
                return plate
            return {}

        bodies = (
            {
                "type": "file",
                "sha": "sha-bad",
                "encoding": "base64",
                "content": base64.b64encode(b'{"platform": "posix",}').decode("ascii"),
            },
            {"type": "file", "sha": "sha-unread"},
        )
        for body in bodies:
            plate.clear()
            plate.update(body)
            puts.clear()
            client = Mock()
            client.api.side_effect = api_side
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._template(root)
                with patch("plate_core.bootstrap.resolve_template_source", return_value=(root, "explicit_path")):
                    with patch("plate_core.bootstrap.get_health", return_value=self._health(present=True)):
                        with self.assertRaises(RuntimeError):
                            run_bootstrap(
                                "akasper/plat",
                                apply_mode=False,
                                client=client,
                                platform="windows",
                            )
                        with self.assertRaises(RuntimeError):
                            run_bootstrap(
                                "akasper/plat",
                                apply_mode=True,
                                client=client,
                                platform="windows",
                            )
            self.assertEqual(puts, [])


def _bash_executable() -> str | None:
    found = shutil.which("bash")
    if found:
        return found
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    if candidate.is_file():
        return str(candidate)
    return None


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _validator_fixture(root: Path, *, platform: str | None, gifs: list[str]) -> None:
    for rel in (
        "AGENTS.md",
        "CURRENT.md",
        "SPEC.md",
        ".agentic/process.yml",
        ".agentic/skills.yml",
        ".github/copilot-instructions.md",
        ".github/workflows/ci.yml",
        ".github/workflows/test-e2e.yml",
        "playwright.config.ts",
        "tests/e2e/specs/one.spec.ts",
        "tests/e2e/pages/.gitkeep",
        "tests/e2e/fixtures/.gitkeep",
    ):
        _write(root / rel, "ok\n")
    _write(
        root / "package.json",
        json.dumps({"scripts": {"test:e2e": "echo e2e", "record:e2e": "echo rec"}}),
    )
    _write(root / ".github" / "workflows" / "ci.yml", "name: ci\njobs:\n  test:\n    run: python -m unittest\n")
    _write(root / ".github" / "copilot-instructions.md", "toolchain is configured\n")
    _write(root / "CURRENT.md", "# CURRENT\n")
    if platform is not None:
        _write(root / ".plate", json.dumps({"version": "1.3", "platform": platform}))
    for name in gifs:
        _write(root / "scripts" / name, "echo gif\n")


class ValidatorPlatformTests(unittest.TestCase):
    def setUp(self):
        bash = _bash_executable()
        if bash is None:
            self.skipTest("bash is not on PATH")
        self.bash = bash
        self.script = payload_root() / "scripts" / "validate_plate_repo.sh"

    def _run(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.bash, str(self.script), str(root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_gif_matrix(self):
        cases = (
            ("posix", ["gif-from-video.sh"], 0),
            ("posix", ["gif-from-video.ps1"], 1),
            ("windows", ["gif-from-video.ps1"], 0),
            ("windows", ["gif-from-video.sh"], 1),
            ("posix-and-windows", ["gif-from-video.sh", "gif-from-video.ps1"], 0),
            ("posix-and-windows", ["gif-from-video.sh"], 1),
            (None, ["gif-from-video.sh"], 0),
            ("", ["gif-from-video.sh"], 1),
        )
        for platform, gifs, expected in cases:
            with self.subTest(platform=platform, gifs=gifs):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _validator_fixture(root, platform=platform, gifs=gifs)
                    result = self._run(root)
                    self.assertEqual(
                        result.returncode,
                        expected,
                        result.stdout + result.stderr,
                    )

    def test_namespaced_gif_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(root, platform="posix", gifs=[])
            _write(root / "scripts" / "plate" / "gif-from-video.sh", "echo gif\n")
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_platform_and_json_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(root, platform="auto", gifs=["gif-from-video.sh", "gif-from-video.ps1"])
            result = self._run(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("invalid platform", result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(root, platform=None, gifs=["gif-from-video.sh"])
            _write(root / ".plate", "{not-json")
            result = self._run(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("invalid JSON", result.stderr)

    def _run_with_env(self, root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.bash, str(self.script), str(root)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_no_parser_fallback_rejects_plate_file(self):
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as bin_dir:
            env["PATH"] = bin_dir
            for raw in ('{"platform":"posix",}', '{"version": "1.3"}', "{not-json"):
                with self.subTest(raw=raw):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        _validator_fixture(root, platform=None, gifs=["gif-from-video.sh"])
                        _write(root / ".plate", raw)
                        result = self._run_with_env(root, env)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertIn("invalid JSON", result.stderr)

    def test_jq_fallback_parses_and_rejects_malformed(self):
        jq = shutil.which("jq")
        # The success cases run the rest of the validator, which calls find and wc.
        needed = {
            "jq": jq,
            "grep": shutil.which("grep"),
            "find": shutil.which("find"),
            "wc": shutil.which("wc"),
        }
        if any(path is None for path in needed.values()):
            self.skipTest("jq, grep, find, and wc are required for the parser fallback")
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as bin_dir:
            for tool in needed.values():
                src = Path(tool)
                shutil.copy2(src, Path(bin_dir) / src.name)
            env["PATH"] = bin_dir
            cases = (
                ('{"platform":"posix",}', 1, "invalid JSON"),
                ('{"platform": ["posix"]}', 1, "invalid platform"),
                ('{"platform": " "}', 1, "invalid platform"),
                ('{"platform": ""}', 1, "invalid platform"),
                ('{"platform": null}', 0, "gif-from-video.sh"),
                ('{"version": "1.3"}', 0, "gif-from-video.sh"),
                ('{"platform": "windows"}', 0, "platform: windows"),
            )
            for raw, expected, needle in cases:
                with self.subTest(raw=raw):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        gifs = ["gif-from-video.ps1"] if '"windows"' in raw else ["gif-from-video.sh"]
                        _validator_fixture(root, platform=None, gifs=gifs)
                        _write(root / ".plate", raw)
                        result = self._run_with_env(root, env)
                        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                        blob = result.stdout + result.stderr
                        self.assertIn(needle, blob)


class PowerShellValidatorTests(unittest.TestCase):
    def setUp(self):
        exe = _powershell_executable()
        if exe is None:
            self.skipTest("pwsh or powershell is not on PATH")
        self.exe = exe
        self.script = payload_root() / "scripts" / "ValidatePlateRepo.ps1"

    def _run(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.exe,
                "-NoProfile",
                "-File",
                str(self.script),
                "-Root",
                str(root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_gif_matrix(self):
        cases = (
            ("posix", ["gif-from-video.sh"], 0),
            ("windows", ["gif-from-video.ps1"], 0),
            ("windows", ["gif-from-video.sh"], 1),
            ("posix-and-windows", ["gif-from-video.sh"], 1),
            ("posix-and-windows", ["gif-from-video.sh", "gif-from-video.ps1"], 0),
        )
        for platform, gifs, expected in cases:
            with self.subTest(platform=platform, gifs=gifs):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _validator_fixture(root, platform=platform, gifs=gifs)
                    result = self._run(root)
                    self.assertEqual(
                        result.returncode,
                        expected,
                        result.stdout + result.stderr,
                    )

    def test_whitespace_platform_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(
                root,
                platform=None,
                gifs=["gif-from-video.sh", "gif-from-video.ps1"],
            )
            _write(root / ".plate", json.dumps({"version": "1.3", "platform": " "}))
            result = self._run(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("invalid platform", result.stdout + result.stderr)

    def test_empty_platform_fails_and_null_means_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(
                root,
                platform=None,
                gifs=["gif-from-video.sh", "gif-from-video.ps1"],
            )
            _write(root / ".plate", json.dumps({"version": "1.3", "platform": ""}))
            result = self._run(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("invalid platform", result.stdout + result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _validator_fixture(root, platform=None, gifs=["gif-from-video.sh"])
            _write(root / ".plate", json.dumps({"version": "1.3", "platform": None}))
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
