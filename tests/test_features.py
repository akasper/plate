import base64
import json
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

    def test_get_features_playwright_e2e_requires_dep_with_e2e_dir_on_gh(self):
        client = Mock()
        package_json = {
            "content": base64.b64encode(
                json.dumps({"devDependencies": {"@playwright/test": "^1.55.0"}}).encode("utf-8")
            ).decode("ascii")
        }

        def api_side_effect(endpoint: str):
            if endpoint.endswith("/contents/tests/e2e"):
                return {"name": "e2e"}
            if endpoint.endswith("/contents/package.json"):
                return package_json
            raise GhApiError("not found")

        client.api.side_effect = api_side_effect
        report = get_features(repo="akasper/plate_core", client=client)
        flags = {x.name: x.enabled for x in report.features}
        self.assertTrue(flags["playwright-e2e"])

    def test_get_features_playwright_e2e_not_enabled_by_e2e_dir_alone_on_gh(self):
        client = Mock()

        def api_side_effect(endpoint: str):
            if endpoint.endswith("/contents/tests/e2e"):
                return {"name": "e2e"}
            if endpoint.endswith("/contents/package.json"):
                return {"content": base64.b64encode(json.dumps({"dependencies": {}}).encode("utf-8")).decode("ascii")}
            raise GhApiError("not found")

        client.api.side_effect = api_side_effect
        report = get_features(repo="akasper/plate_core", client=client)
        flags = {x.name: x.enabled for x in report.features}
        self.assertFalse(flags["playwright-e2e"])


if __name__ == "__main__":
    unittest.main()
