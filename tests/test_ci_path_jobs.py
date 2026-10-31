"""Tests for path-to-CI-jobs config and selection (#1270)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core.ci_path_jobs import (
    CiPathJobsError,
    _path_matches_pattern,
    _paths_from_name_status_output,
    assert_selection_safe_for_merge,
    load_ci_path_jobs_config,
    select_ci_jobs,
    selection_for_repo,
    validate_ci_path_jobs_config,
)


def _sample_config(**overrides):
    base = {
        "version": "1",
        "enabled": True,
        "unmatched_paths": "fail",
        "empty_selection": "run_all",
        "all_jobs": ["core-unit", "web-unit", "e2e"],
        "modules": {
            "core": {
                "paths": ["src/plate_core/**"],
                "jobs": ["core-unit"],
            },
            "iface": {
                "interface": True,
                "paths": ["src/plate_core/mcp_server.py"],
                "jobs": ["core-unit"],
            },
            "cli": {
                "paths": ["src/plate_core/cli.py"],
                "depends_on": ["iface"],
                "jobs": ["core-unit"],
            },
            "web": {
                "paths": ["tests/e2e/**"],
                "jobs": ["e2e"],
            },
        },
    }
    base.update(overrides)
    return base


class ValidateCiPathJobsConfigTests(unittest.TestCase):
    def test_valid_sample(self):
        validate_ci_path_jobs_config(_sample_config())

    def test_rejects_bad_unmatched_policy(self):
        with self.assertRaises(CiPathJobsError):
            validate_ci_path_jobs_config(_sample_config(unmatched_paths="ignore"))

    def test_rejects_unknown_depends_on(self):
        cfg = _sample_config()
        cfg["modules"]["cli"]["depends_on"] = ["missing"]
        with self.assertRaises(CiPathJobsError):
            validate_ci_path_jobs_config(cfg)

    def test_rejects_incomplete_all_jobs(self):
        cfg = _sample_config(all_jobs=["core-unit"])
        with self.assertRaises(CiPathJobsError):
            validate_ci_path_jobs_config(cfg)


class PathPatternTests(unittest.TestCase):
    def test_double_star_matches_zero_directories(self):
        self.assertTrue(_path_matches_pattern("src/**/api.py", "src/api.py"))
        self.assertTrue(_path_matches_pattern("src/**/api.py", "src/pkg/api.py"))

    def test_wildcard_segment_prefix(self):
        self.assertTrue(_path_matches_pattern("src/*/**", "src/foo/bar.py"))

    def test_directory_glob_suffix(self):
        self.assertTrue(_path_matches_pattern("src/plate_core/**", "src/plate_core/x.py"))


class RenameAndDiffTests(unittest.TestCase):
    def test_name_status_includes_both_rename_paths(self):
        output = "R100\told/path.py\tnew/path.py\n"
        self.assertEqual(
            _paths_from_name_status_output(output),
            ["old/path.py", "new/path.py"],
        )

    def test_rename_selects_both_modules(self):
        cfg = _sample_config(
            modules={
                "old_mod": {"paths": ["legacy/**"], "jobs": ["core-unit"]},
                "new_mod": {"paths": ["modern/**"], "jobs": ["web-unit"]},
            },
            all_jobs=["core-unit", "web-unit"],
        )
        sel = select_ci_jobs(["legacy/a.py", "modern/b.py"], cfg)
        self.assertEqual(set(sel.jobs_to_run), {"core-unit", "web-unit"})


class ExampleConfigGlobTests(unittest.TestCase):
    def test_root_api_triggers_interface_dependent(self):
        cfg = {
            "version": "1",
            "enabled": True,
            "unmatched_paths": "fail",
            "empty_selection": "run_all",
            "all_jobs": ["product-unit", "product-e2e"],
            "modules": {
                "product_code": {
                    "paths": ["src/**"],
                    "jobs": ["product-unit"],
                },
                "public_contract": {
                    "interface": True,
                    "paths": ["src/**/api.py"],
                    "jobs": ["product-unit"],
                },
                "product_ui": {
                    "paths": ["tests/e2e/**"],
                    "depends_on": ["public_contract"],
                    "jobs": ["product-e2e"],
                },
            },
        }
        validate_ci_path_jobs_config(cfg)
        sel = select_ci_jobs(["src/api.py"], cfg)
        self.assertIn("product-e2e", sel.jobs_to_run)


class SelectionForRepoTests(unittest.TestCase):
    def test_missing_change_source_fails_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agentic = root / ".agentic"
            agentic.mkdir()
            (agentic / "ci-path-jobs.yml").write_text(
                "version: '1'\nenabled: true\nall_jobs: [j]\n"
                "modules:\n  m:\n    paths: ['src/**']\n    jobs: [j]\n",
                encoding="utf-8",
            )
            sel = selection_for_repo(root)
            self.assertEqual(sel.safety, "fail")
            with self.assertRaises(CiPathJobsError):
                assert_selection_safe_for_merge(sel)


class SelectCiJobsTests(unittest.TestCase):
    def test_disabled_runs_all(self):
        cfg = _sample_config(enabled=False)
        sel = select_ci_jobs(["mystery/file.py"], cfg)
        self.assertTrue(sel.run_all)
        self.assertEqual(set(sel.jobs_to_run), {"core-unit", "web-unit", "e2e"})

    def test_core_path_selects_core_job_only(self):
        sel = select_ci_jobs(["src/plate_core/foo.py"], _sample_config())
        self.assertFalse(sel.run_all)
        self.assertEqual(sel.jobs_to_run, ["core-unit"])
        self.assertIn("web-unit", sel.jobs_to_skip)

    def test_e2e_path_selects_e2e_job(self):
        sel = select_ci_jobs(["tests/e2e/spec.ts"], _sample_config())
        self.assertEqual(sel.jobs_to_run, ["e2e"])

    def test_interface_change_runs_dependent_module_jobs(self):
        sel = select_ci_jobs(["src/plate_core/mcp_server.py"], _sample_config())
        self.assertIn("core", sel.matched_modules)
        self.assertIn("cli", sel.matched_modules)
        self.assertEqual(sel.jobs_to_run, ["core-unit"])

    def test_hidden_change_fails_when_unmatched_paths_fail(self):
        """Deliberately hide a change: path outside the map must not yield a green skip."""
        sel = select_ci_jobs(["vendor/secret_module.py"], _sample_config())
        self.assertEqual(sel.safety, "fail")
        self.assertFalse(sel.run_all)
        self.assertEqual(sel.jobs_to_run, [])
        with self.assertRaises(CiPathJobsError):
            assert_selection_safe_for_merge(sel)

    def test_hidden_change_run_all_fallback(self):
        cfg = _sample_config(unmatched_paths="run_all")
        sel = select_ci_jobs(["vendor/secret_module.py"], cfg)
        self.assertTrue(sel.run_all)
        assert_selection_safe_for_merge(sel)

    def test_full_suite_flag_runs_all(self):
        sel = select_ci_jobs(["vendor/x.py"], _sample_config(), full_suite=True)
        self.assertTrue(sel.run_all)
        self.assertEqual(len(sel.jobs_to_run), 3)


class LoadConfigTests(unittest.TestCase):
    def test_load_from_agentic_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agentic = root / ".agentic"
            agentic.mkdir()
            (agentic / "ci-path-jobs.yml").write_text(
                "version: '1'\nenabled: false\n",
                encoding="utf-8",
            )
            cfg, src = load_ci_path_jobs_config(root)
            self.assertFalse(cfg["enabled"])
            self.assertIn("ci-path-jobs.yml", src)

    def test_load_from_plate_ci_path_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = {"version": "1.3", "ci": {"path_jobs": {"version": "1", "enabled": False}}}
            (root / ".plate").write_text(json.dumps(nested), encoding="utf-8")
            cfg, src = load_ci_path_jobs_config(root)
            self.assertFalse(cfg["enabled"])
            self.assertIn("ci.path_jobs", src)

    def test_missing_config_disables_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, src = load_ci_path_jobs_config(Path(tmp))
            self.assertFalse(cfg["enabled"])
            self.assertEqual(src, "")


class SelectCiJobsScriptSafetyTests(unittest.TestCase):
    def test_assert_safe_rejects_empty_jobs_with_changes(self):
        sel = select_ci_jobs(["vendor/hidden.py"], _sample_config())
        self.assertEqual(sel.safety, "fail")
        with self.assertRaises(CiPathJobsError):
            assert_selection_safe_for_merge(sel)


if __name__ == "__main__":
    unittest.main()
