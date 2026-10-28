"""Regression tests for template payload ci.yml check contexts (#1229)."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_CI = (
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "workflows" / "ci.yml"
)


class TemplatePayloadCiWorkflowTests(unittest.TestCase):
    def test_labels_job_reports_labels_context(self):
        text = PAYLOAD_CI.read_text(encoding="utf-8")
        self.assertIn("\n  labels:\n", text)
        self.assertNotIn("\n    name: Labels\n", text)

    def test_test_job_resolves_namespaced_validate_script(self):
        text = PAYLOAD_CI.read_text(encoding="utf-8")
        self.assertIn("scripts/plate/validate_plate_repo.sh", text)
        self.assertIn("scripts/validate_plate_repo.sh", text)
        self.assertNotIn("run: bash scripts/validate_plate_repo.sh .\n", text)

    def test_test_job_validate_step_uses_bash_shell(self):
        text = PAYLOAD_CI.read_text(encoding="utf-8")
        run_tests = text.index("- name: Run Tests")
        snippet = text[run_tests : run_tests + 400]
        self.assertIn("shell: bash", snippet)
        self.assertIn("set -euo pipefail", snippet)


if __name__ == "__main__":
    unittest.main()
