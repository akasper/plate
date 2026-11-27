"""Regression tests for #1478 CI baseline (workflow shape)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def read_ci() -> str:
    return CI_WORKFLOW.read_text(encoding="utf-8")


class CiWorkflowBaselineTests(unittest.TestCase):
    def test_pr_triggers_omit_label_and_edit_noise(self):
        text = read_ci()
        pr_block = text[text.index("pull_request:") : text.index("concurrency:")]
        self.assertIn("types: [opened, synchronize, reopened]", pr_block)
        self.assertNotIn("labeled", pr_block)
        self.assertNotIn("edited", pr_block)

    def test_python_version_matrix(self):
        text = read_ci()
        self.assertIn('python-version: ["3.10", "3.11", "3.12", "3.13"]', text)

    def test_ruff_and_wheel_install_in_test_job(self):
        text = read_ci()
        test_idx = text.index("\n  test:")
        heavy_idx = text.index("\n  copilot-marketplace-smoke:")
        test_job = text[test_idx:heavy_idx]
        self.assertIn("python -m ruff check src tests", test_job)
        self.assertIn("python -m build -w", test_job)
        self.assertIn("dist/*.whl", test_job)

    def test_marketplace_smoke_is_separate_job(self):
        text = read_ci()
        self.assertIn("\n  copilot-marketplace-smoke:\n", text)
        smoke_job = text.split("copilot-marketplace-smoke:", 1)[1].split("\n  heavy-release:", 1)[0]
        self.assertIn("copilot plugin marketplace add akasper/plate", smoke_job)
        self.assertNotIn("copilot plugin marketplace add akasper/plate", text.split("\n  test:")[1].split("copilot-marketplace-smoke:")[0])

    def test_heavy_release_builds_wheel(self):
        text = read_ci()
        heavy = text.split("heavy-release:", 1)[1]
        self.assertIn("python -m build", heavy)
        self.assertIn("import plate_core", heavy)

    def test_actions_are_sha_pinned_not_floating_tags(self):
        text = read_ci()
        uses_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- uses: actions/")]
        self.assertGreaterEqual(len(uses_lines), 3)
        for line in uses_lines:
            self.assertRegex(line, r"@[0-9a-f]{40}", msg=line)
        nested_uses = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("uses: actions/")
        ]
        for line in nested_uses:
            self.assertRegex(line, r"@[0-9a-f]{40}", msg=line)
        self.assertNotRegex(text, re.compile(r"uses:\s+actions/checkout@v"))

    def test_e2e_uses_npm_ci(self):
        text = read_ci()
        self.assertIn("tests/e2e/package-lock.json", text)
        self.assertIn("npm ci", text)
        self.assertNotIn("npm install\n", text)

    def test_pyproject_documents_minimal_ruff_scope(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('[tool.ruff.lint]', pyproject)
        self.assertIn('select = ["E9", "F63", "F7", "F82"]', pyproject)


if __name__ == "__main__":
    unittest.main()