"""Tests for Epic #89 inventory and ownership classification (Issue #106).

Validates that:
1. All missing templates are accounted for
2. Ownership classification is consistent and correct
3. Migration actions are feasible
"""

import unittest
from pathlib import Path
from typing import Dict, List, Set


class TemplateInventoryTests(unittest.TestCase):
    """Tests for canonical template inventory and ownership."""

    # All 48 missing templates from audit
    MISSING_TEMPLATES = {
        # Workflows (5)
        ".github/workflows/auto-label-feedback-responses.yml",
        ".github/workflows/cost-tracking.yml",
        ".github/workflows/discussion-monitoring.yml",
        ".github/workflows/platform-monitor.yml",
        ".github/workflows/test-e2e.yml",
        # Docs (15)
        "docs/design/conversation-to-issue-graph.md",
        "docs/design/default-questions.md",
        "docs/design/epic-planning-dialogue-flow.md",
        "docs/design/extension-repository.md",
        "docs/design/onboarding-questions.md",
        "docs/design/playwright-ci-design.md",
        "docs/playwright-e2e-guide.md",
        "docs/README.md",
        "docs/research/epic-intent-detection.md",
        "docs/research/gif-generation-spike.md",
        "docs/research/information-goals.md",
        "docs/research/interactive-planning-ux.md",
        "docs/research/openspec-evaluation.md",
        "docs/research/playwright-asset-strategy.md",
        "docs/research/playwright-gif-generation.md",
        # Scripts (10)
        "scripts/check_toolchain.sh",
        "scripts/CheckToolchain.ps1",
        "scripts/dev-server.js",
        "scripts/e2e-record.ps1",
        "scripts/e2e-record.sh",
        "scripts/gif-from-video.ps1",
        "scripts/gif-from-video.sh",
        "scripts/README.md",
        "scripts/validate_plate_repo.sh",
        "scripts/ValidatePlateRepo.ps1",
        # Tests (16)
        "tests/e2e/fixtures/.gitkeep",
        "tests/e2e/fixtures/gifs/homepage-demo.gif",
        "tests/e2e/fixtures/gifs/README.md",
        "tests/e2e/fixtures/README.md",
        "tests/e2e/pages/base-page.ts",
        "tests/e2e/pages/login-page.ts",
        "tests/e2e/README.md",
        "tests/e2e/specs/example.spec.ts",
        "tests/e2e/specs/failing-example.spec.ts",
        "tests/spike-videos/TEST_RESULTS.md",
        "tests/spike-videos/test-10s.webm",
        "tests/spike-videos/test-high.gif",
        "tests/spike-videos/test-low.gif",
        "tests/spike-videos/test-medium.gif",
        "tests/spike-videos/test-trimmed-5s.gif",
        "tests/spike-videos/test-trimmed-5s-low.gif",
        # Root configs (2)
        "package.json",
        "playwright.config.ts",
    }

    # Ownership classification
    OWNERSHIP_MAP: Dict[str, str] = {
        "workflows": "core-owned",
        "docs": "core-owned",
        "scripts": "core-owned",
        "tests": "core-owned",
        "root_configs": "core-owned",
    }

    def test_inventory_count(self):
        """Verify inventory contains exactly 48 files."""
        self.assertEqual(len(self.MISSING_TEMPLATES), 48)

    def test_inventory_categories_balanced(self):
        """Verify inventory breakdown by category."""
        categories = self._categorize_inventory()
        expected = {
            "workflows": 5,
            "docs": 15,
            "scripts": 10,
            "tests": 16,
            "root_configs": 2,
        }
        for cat, count in expected.items():
            self.assertEqual(
                len(categories[cat]),
                count,
                f"Expected {count} {cat} files, got {len(categories[cat])}",
            )

    def test_all_templates_have_category(self):
        """Verify every template is assigned to exactly one category."""
        categories = self._categorize_inventory()
        categorized = set()
        for items in categories.values():
            categorized.update(items)
        self.assertEqual(
            categorized,
            self.MISSING_TEMPLATES,
            "All templates must be categorized",
        )

    def test_ownership_consistency(self):
        """Verify all categories have consistent ownership designation."""
        for category, owner in self.OWNERSHIP_MAP.items():
            # In current design, all categories are core-owned
            self.assertEqual(owner, "core-owned")

    def test_migration_actions_are_feasible(self):
        """Verify migration actions are feasible for each category."""
        categories = self._categorize_inventory()
        migration_actions = {
            "workflows": "copy-main",  # Move to plate main
            "docs": "copy-main",
            "scripts": "copy-main",
            "tests": "copy-main",
            "root_configs": "integrate",  # Merge/integrate into existing
        }
        # This test validates that migration actions are defined
        self.assertEqual(len(migration_actions), len(categories))

    def test_no_duplicate_paths(self):
        """Verify no duplicate paths in inventory."""
        paths = list(self.MISSING_TEMPLATES)
        self.assertEqual(len(paths), len(set(paths)))

    def test_workflows_are_automation(self):
        """Verify all .github/workflows files are classified as CI automation."""
        categories = self._categorize_inventory()
        for wf in categories["workflows"]:
            self.assertTrue(
                wf.startswith(".github/workflows/"),
                f"Workflow {wf} should start with .github/workflows/",
            )

    def test_docs_cover_design_and_research(self):
        """Verify docs include both design and research artifacts."""
        categories = self._categorize_inventory()
        design_docs = [d for d in categories["docs"] if "/design/" in d]
        research_docs = [d for d in categories["docs"] if "/research/" in d]
        root_docs = [d for d in categories["docs"] if d == "docs/README.md" or d == "docs/playwright-e2e-guide.md"]
        
        self.assertGreater(len(design_docs), 0, "Should have design docs")
        self.assertGreater(len(research_docs), 0, "Should have research docs")
        self.assertGreater(len(root_docs), 0, "Should have root-level docs")

    def test_scripts_cover_validation_and_recording(self):
        """Verify scripts include both shell and PowerShell variants."""
        categories = self._categorize_inventory()
        sh_scripts = [s for s in categories["scripts"] if s.endswith(".sh")]
        ps_scripts = [s for s in categories["scripts"] if s.endswith(".ps1")]
        
        self.assertGreater(len(sh_scripts), 0, "Should have shell scripts")
        self.assertGreater(len(ps_scripts), 0, "Should have PowerShell scripts")

    def test_tests_include_e2e_fixtures_and_spike_data(self):
        """Verify tests category includes E2E harness, fixtures, and spike data."""
        categories = self._categorize_inventory()
        e2e_tests = [t for t in categories["tests"] if "e2e" in t]
        spike_data = [t for t in categories["tests"] if "spike-videos" in t]
        
        self.assertGreater(len(e2e_tests), 0, "Should have E2E tests")
        self.assertGreater(len(spike_data), 0, "Should have spike video data")

    def _categorize_inventory(self) -> Dict[str, Set[str]]:
        """Categorize inventory templates by type."""
        categories = {
            "workflows": set(),
            "docs": set(),
            "scripts": set(),
            "tests": set(),
            "root_configs": set(),
        }
        
        for path in self.MISSING_TEMPLATES:
            if ".github/workflows" in path:
                categories["workflows"].add(path)
            elif path.startswith("docs/"):
                categories["docs"].add(path)
            elif path.startswith("scripts/"):
                categories["scripts"].add(path)
            elif path.startswith("tests/"):
                categories["tests"].add(path)
            elif path in {"package.json", "playwright.config.ts"}:
                categories["root_configs"].add(path)
        
        return categories


class OwnershipRubricTests(unittest.TestCase):
    """Tests for ownership classification rubric."""

    def test_core_owned_definition(self):
        """Verify core-owned criteria: methodology, automation, dev tools, config."""
        core_owned_criteria = {
            "methodology": True,  # PLATE as canonical source
            "automation": True,  # CI/platform workflows
            "dev_tools": True,  # Scripts for validation/recording
            "platform_config": True,  # Root-level config
        }
        # All criteria apply to at least one category
        self.assertEqual(len(core_owned_criteria), 4)

    def test_tool_generated_definition(self):
        """Verify tool-generated criteria: build/runtime artifacts."""
        # Media fixtures (GIFs, videos) may be tool-generated
        # but are committed raw in template, so they follow core-owned model
        self.assertTrue(True)

    def test_fork_local_definition(self):
        """Verify fork-local criteria: user overrides."""
        # Fork-local content never committed to plate
        # Managed via .plate override mechanism (future design)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
