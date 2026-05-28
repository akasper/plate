import unittest
from pathlib import Path
from unittest.mock import Mock

from plate_core.features import detect_playwright_e2e_local, get_features
from plate_core.github_client import GhApiError


class FeatureDetectionTests(unittest.TestCase):
    def test_get_features_reports_expected_flags(self):
        client = Mock()

        def api_side_effect(endpoint: str):
            if endpoint.endswith("/contents/.plugin/plugin.json"):
                return {"name": "plugin.json"}
            if endpoint.endswith("/contents/src/plate_core/data/baseline_catalog.yml"):
                return {"name": "baseline_catalog.yml"}
            if endpoint.endswith("/contents/CURRENT.md"):
                return {"name": "CURRENT.md"}
            # playwright flexible: none of the config candidates present -> disabled
            raise GhApiError("not found")

        client.api.side_effect = api_side_effect
        report = get_features(repo="akasper/plate_core", client=client)
        flags = {x.name: x.enabled for x in report.features}
        self.assertTrue(flags["copilot-plugin-root"])
        self.assertTrue(flags["baseline-agents-catalog"])
        self.assertTrue(flags["current-md"])
        self.assertFalse(flags["autonomous-mode"])
        self.assertIn("playwright-e2e", flags)

    def test_detect_playwright_e2e_local_flexible_heuristic(self):
        # Simulate a minimal playwright setup dir (no real files, just structure for test)
        # Use this file's parent as base; playwright not present here so expect False
        here = Path(__file__).parent
        self.assertFalse(detect_playwright_e2e_local(here))

        # The plate_template sibling (from workspace layout) should have it
        template = here.parent.parent / "plate_template"
        if template.exists():
            self.assertTrue(detect_playwright_e2e_local(template))


if __name__ == "__main__":
    unittest.main()
