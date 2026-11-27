"""Regression tests for template payload ci.yml check contexts (#1229)."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_CI = (
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "workflows" / "ci.yml"
)


def _extract_github_script_for_step(workflow_text: str, step_name: str) -> str:
    name_line = f"- name: {step_name}"
    if name_line not in workflow_text:
        raise AssertionError(f"{step_name!r} step not found in ci.yml workflow text")
    start = workflow_text.index(name_line)
    script_idx = workflow_text.index("script: |", start)
    lines: list[str] = []
    for line in workflow_text[script_idx:].splitlines()[1:]:
        if line.startswith("            "):
            lines.append(line[12:])
        elif not line.strip():
            lines.append("")
        else:
            break
    body = "\n".join(lines).strip()
    if not body:
        raise AssertionError(f"{step_name!r}: github-script body is empty")
    return body


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
        if "- name: Run Tests" not in text:
            self.fail("ci.yml missing 'Run Tests' step")
        run_tests = text.index("- name: Run Tests")
        snippet = text[run_tests : run_tests + 400]
        self.assertIn("shell: bash", snippet)
        self.assertIn("set -euo pipefail", snippet)

    def test_pr_type_label_check_requires_exact_label_names(self):
        text = PAYLOAD_CI.read_text(encoding="utf-8")
        script = _extract_github_script_for_step(text, "Validate PR type label")
        self.assertNotIn("prTypeByLower", script)
        self.assertNotIn("toLowerCase", script)
        self.assertIn("prTypeLabels.includes(label)", script)

    def test_pr_type_label_check_rejects_lowercase_labels(self):
        text = PAYLOAD_CI.read_text(encoding="utf-8")
        script = _extract_github_script_for_step(text, "Validate PR type label")
        self.assertNotIn("toLowerCase", script)
        self.assertNotIn("prTypeByLower", script)
        match = re.search(
            r"^const prTypeLabels = (\[[^\]]+\]);$",
            script,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, "ci.yml script must declare prTypeLabels")
        decl = match.group(0)
        self.assertIn("prTypeLabels.includes(label)", script)
        node_harness = f"""
{decl}
function countPrTypeMatches(labels) {{
  return labels.filter((label) => prTypeLabels.includes(label)).length;
}}
const low = countPrTypeMatches(['feature']);
const exact = countPrTypeMatches(['Feature']);
if (low !== 0) {{
  throw new Error(`lowercase 'feature' must not match, got ${{low}}`);
}}
if (exact !== 1) {{
  throw new Error(`exact 'Feature' must match once, got ${{exact}}`);
}}
"""
        subprocess.run(
            ["node", "-e", node_harness],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()