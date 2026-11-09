"""Regression tests for #1451: timestamp-based database migration naming guidance."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GUIDANCE_MARKERS = (
    "20261109T111800Z_residue_baseline.sql",
    "YYYYMMDDTHHMMSSZ",
    "Do not rename existing migrations",
    "Sequential numbering only when required",
)


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class DatabaseMigrationNamingGuidanceTests(unittest.TestCase):
    """AGENTS.md and payload docs state the #1451 migration naming convention."""

    def test_core_agents_index_links_convention(self):
        agents = _read("AGENTS.md")
        self.assertIn("database-migration-naming.md", agents)
        self.assertIn("#1451", agents)

    def test_template_payload_agents_index_links_convention(self):
        agents = _read("src/plate_core/template_payload/AGENTS.md")
        self.assertIn("database-migration-naming.md", agents)
        self.assertIn("#1451", agents)

    def test_plate_and_payload_guidance_pages_match_convention(self):
        for rel in (
            "docs/agents/database-migration-naming.md",
            "src/plate_core/template_payload/docs/agents/database-migration-naming.md",
        ):
            text = _read(rel)
            for marker in GUIDANCE_MARKERS:
                self.assertIn(marker, text, msg=f"missing {marker!r} in {rel}")


if __name__ == "__main__":
  unittest.main()
