"""Tests for tiered CI policy config and selection (#1332)."""

from __future__ import annotations

import unittest

from plate_core.ci_tiered_policy import (
    CiTieredPolicyError,
    default_policy_config,
    forced_jobs_for_changes,
    max_job_size_for_kind,
    select_tiered_ci_jobs,
    validate_ci_tiered_policy_config,
)


def _path_config(**overrides):
    base = {
        "version": "1",
        "enabled": True,
        "unmatched_paths": "fail",
        "empty_selection": "run_all",
        "all_jobs": ["lint-fast", "unit", "integration", "e2e"],
        "modules": {
            "core": {
                "paths": ["src/core/**"],
                "jobs": ["unit"],
            },
            "docs": {
                "paths": ["docs/**"],
                "jobs": ["lint-fast"],
            },
            "e2e": {
                "paths": ["tests/e2e/**"],
                "jobs": ["e2e"],
            },
            "heavy": {
                "paths": ["services/**"],
                "jobs": ["integration"],
            },
        },
    }
    base.update(overrides)
    return base


def _policy_config(**overrides):
    base = {
        "version": "1",
        "enabled": True,
        "job_sizes": {
            "lint-fast": "small",
            "unit": "medium",
            "integration": "large",
            "e2e": "large",
        },
    }
    base.update(overrides)
    return base


class ValidatePolicyTests(unittest.TestCase):
    def test_defaults_merge_and_validate(self):
        validate_ci_tiered_policy_config(default_policy_config())

    def test_rejects_bad_job_size(self):
        cfg = _policy_config(job_sizes={"unit": "huge"})
        with self.assertRaises(CiTieredPolicyError):
            validate_ci_tiered_policy_config(cfg)

    def test_requires_all_jobs_classified_when_path_config_given(self):
        cfg = _policy_config(job_sizes={"lint-fast": "small"})
        with self.assertRaises(CiTieredPolicyError):
            validate_ci_tiered_policy_config(cfg, path_jobs_config=_path_config())

    def test_rejects_inverted_cost_tiers(self):
        cfg = _policy_config(
            cost_tiers={
                "small": {"max_usd": 5.0},
                "medium": {"min_usd": 0.10, "max_usd": 2.00},
                "large": {"min_usd": 2.00},
            }
        )
        with self.assertRaises(CiTieredPolicyError):
            validate_ci_tiered_policy_config(cfg)


class TierCapTests(unittest.TestCase):
    def test_ordinary_includes_small_and_path_medium_not_large(self):
        sel, meta = select_tiered_ci_jobs(
            ["src/core/x.py"],
            _path_config(),
            _policy_config(),
            pr_kind="ordinary",
        )
        self.assertIn("lint-fast", sel.jobs_to_run)
        self.assertIn("unit", sel.jobs_to_run)
        self.assertNotIn("integration", sel.jobs_to_run)
        self.assertNotIn("e2e", sel.jobs_to_run)
        self.assertEqual(meta.max_job_size, "medium")

    def test_docs_only_runs_small_plus_lint(self):
        sel, _meta = select_tiered_ci_jobs(
            ["docs/readme.md"],
            _path_config(),
            _policy_config(),
            pr_kind="ordinary",
        )
        self.assertEqual(set(sel.jobs_to_run), {"lint-fast"})

    def test_release_patch_blocks_large_even_when_path_selected(self):
        sel, _ = select_tiered_ci_jobs(
            ["services/x.py"],
            _path_config(),
            _policy_config(),
            pr_kind="release_patch",
        )
        self.assertIn("lint-fast", sel.jobs_to_run)
        self.assertNotIn("integration", sel.jobs_to_run)

    def test_release_minor_allows_large(self):
        sel, _ = select_tiered_ci_jobs(
            ["tests/e2e/a.spec.ts"],
            _path_config(),
            _policy_config(),
            pr_kind="release_minor",
        )
        self.assertIn("e2e", sel.jobs_to_run)

    def test_release_major_runs_all(self):
        sel, meta = select_tiered_ci_jobs(
            ["docs/x.md"],
            _path_config(),
            _policy_config(),
            pr_kind="release_major",
        )
        self.assertTrue(sel.run_all)
        self.assertIsNone(meta.max_job_size)

    def test_nightly_runs_all(self):
        sel, _ = select_tiered_ci_jobs(
            ["docs/x.md"],
            _path_config(),
            _policy_config(),
            pr_kind="nightly",
        )
        self.assertTrue(sel.run_all)


class ForceRunTests(unittest.TestCase):
    def test_workflow_change_forces_all_jobs(self):
        forced = forced_jobs_for_changes(
            [".github/workflows/ci.yml"],
            [],
            path_jobs_config=_path_config(),
            policy_config=_policy_config(),
        )
        self.assertEqual(set(forced), {"lint-fast", "unit", "integration", "e2e"})

    def test_map_change_forces_all_jobs(self):
        forced = forced_jobs_for_changes(
            [".agentic/ci-path-jobs.yml"],
            [],
            path_jobs_config=_path_config(),
            policy_config=_policy_config(),
        )
        self.assertEqual(len(forced), 4)

    def test_added_test_forces_path_job_even_when_tier_would_skip(self):
        sel, meta = select_tiered_ci_jobs(
            ["docs/x.md"],
            _path_config(),
            _policy_config(),
            pr_kind="ordinary",
            added_paths=["tests/e2e/new.spec.ts"],
        )
        self.assertIn("e2e", sel.jobs_to_run)
        self.assertIn("e2e", meta.forced_jobs)

    def test_large_path_on_ordinary_excluded_without_force(self):
        sel, _ = select_tiered_ci_jobs(
            ["services/x.py"],
            _path_config(),
            _policy_config(),
            pr_kind="ordinary",
        )
        self.assertNotIn("integration", sel.jobs_to_run)


class MaxJobSizeTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(max_job_size_for_kind("ordinary"), "medium")
        self.assertEqual(max_job_size_for_kind("release_patch"), "medium")
        self.assertEqual(max_job_size_for_kind("release_minor"), "large")
        self.assertIsNone(max_job_size_for_kind("release_major"))


if __name__ == "__main__":
    unittest.main()
