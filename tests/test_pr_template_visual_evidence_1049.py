"""Regression tests for #1049 slim PR template and visual evidence section."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PR_TEMPLATE_PATHS = (
    REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "PULL_REQUEST_TEMPLATE.md",
)

_REQUIRED_HEADINGS = (
    "## Summary",
    "## What changed",
    "## How verified",
    "## Links",
    "## Visual evidence",
)

_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


class PrTemplateVisualEvidence1049Tests(unittest.TestCase):
    def test_repo_and_template_payload_pr_templates_match(self):
        texts = [p.read_text(encoding="utf-8") for p in PR_TEMPLATE_PATHS]
        self.assertEqual(texts[0], texts[1])

    def test_slim_sections_and_no_markdown_tables(self):
        for path in PR_TEMPLATE_PATHS:
            text = path.read_text(encoding="utf-8")
            for heading in _REQUIRED_HEADINGS:
                self.assertIn(heading, text, msg=f"{path.name} missing {heading}")
            for line in text.splitlines():
                if line.strip().startswith("<!--"):
                    continue
                self.assertIsNone(
                    _TABLE_ROW.match(line),
                    msg=f"table row in {path.name}: {line!r}",
                )

    def test_visual_evidence_attach_pattern_and_na_escape(self):
        for path in PR_TEMPLATE_PATHS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("--attach", text)
            self.assertIn("![alt text](./shot.png)", text)
            self.assertIn("Do **not** commit images", text)
            self.assertIn("320px", text)
            self.assertIn("Visual evidence: not applicable —", text)

    def test_required_process_notes(self):
        for path in PR_TEMPLATE_PATHS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("Closes #N", text)
            self.assertIn("exactly one", text.lower())
            self.assertIn(".agentic/releases/", text)


if __name__ == "__main__":
    unittest.main()
