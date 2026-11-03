"""Regression tests for #1050: UI screenshot agent guidance."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


class UiScreenshotsAgentGuidance1050Tests(unittest.TestCase):
    def test_on_demand_page_matches_payload_copy(self):
        repo_page = REPO_ROOT / "docs/agents/ui-screenshots-in-prs.md"
        payload_page = (
            REPO_ROOT / "src/plate_core/template_payload/docs/agents/ui-screenshots-in-prs.md"
        )
        self.assertEqual(
            repo_page.read_text(encoding="utf-8"),
            payload_page.read_text(encoding="utf-8"),
            "ui-screenshots-in-prs.md must match between repo and template_payload",
        )

    def test_agents_md_core_rule(self):
        agents = _read("AGENTS.md")
        self.assertIn("ui-screenshots-in-prs.md", agents)
        self.assertIn("320px", agents)
        self.assertIn("gh --version", agents)
        self.assertIn("--attach", agents)
        self.assertIn("2.99", agents)
        self.assertIn("raw.githubusercontent.com", agents)
        self.assertIn("gho_", agents)
        self.assertIn("Copilot's cloud coding agent", agents)

    def test_template_payload_agents_md_core_rule(self):
        agents = _read("src/plate_core/template_payload/AGENTS.md")
        self.assertIn("ui-screenshots-in-prs.md", agents)
        self.assertIn("320px", agents)
        self.assertIn("--attach", agents)

    def test_default_plate_persona_rule(self):
        for rel in (
            "docs/agents/default-plate-persona.md",
            "src/plate_core/template_payload/docs/agents/default-plate-persona.md",
        ):
            text = _read(rel)
            self.assertIn("ui-screenshots-in-prs.md", text, rel)
            self.assertIn("320px", text, rel)
            self.assertIn("--attach", text, rel)

    def test_agent_guidance_section(self):
        from plate_core.agent_guidance import (
            UI_SCREENSHOTS_IN_PRS_GUIDANCE,
            get_agent_guidance_sections,
        )

        sections = get_agent_guidance_sections()
        self.assertIn("ui_screenshots_in_prs", sections)
        self.assertIs(sections["ui_screenshots_in_prs"], UI_SCREENSHOTS_IN_PRS_GUIDANCE)
        self.assertIn("gh >= 2.99", UI_SCREENSHOTS_IN_PRS_GUIDANCE)
        self.assertIn("github_pat_", UI_SCREENSHOTS_IN_PRS_GUIDANCE)

    def test_plate_persona_references_ui_screenshots(self):
        for rel in ("plugin/agents/plate.agent.md", ".plugin/agents/plate.agent.md"):
            text = _read(rel)
            self.assertIn("320px", text, rel)
            self.assertIn("--attach", text, rel)
            self.assertIn("#1050", text, rel)


if __name__ == "__main__":
    unittest.main()
