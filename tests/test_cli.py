import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from plate_core.cli import main
from plate_core.bootstrap import BootstrapAction, BootstrapReport
from plate_core.epics import EpicStatusReport, EpicSummary
from plate_core.features import FeatureFlag, FeatureReport
from plate_core.health import HealthReport


class CliTests(unittest.TestCase):
    @patch("plate_core.cli.get_health")
    def test_health_json_output(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            branch_protection_enabled=True,
            open_epic_count=2,
            status="pass",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["health", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["status"], "pass")

    @patch("plate_core.cli.get_epic_status")
    def test_epic_status_json_output(self, mock_get_epic_status):
        mock_get_epic_status.return_value = EpicStatusReport(
            repo="akasper/plate_core",
            open_epic_count=1,
            epics=[
                EpicSummary(
                    epic_label="Epic: plate-core-v1",
                    epic_issue_number=4,
                    epic_issue_title="v1 epic",
                    epic_issue_state="open",
                    open_child_issues=5,
                    closed_child_issues=3,
                )
            ],
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["epic", "status", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["open_epic_count"], 1)
        self.assertEqual(payload["epics"][0]["epic_label"], "Epic: plate-core-v1")

    @patch("plate_core.cli.get_features")
    def test_features_json_output(self, mock_get_features):
        mock_get_features.return_value = FeatureReport(
            repo="akasper/plate_core",
            features=[FeatureFlag(name="copilot-plugin-root", enabled=True, evidence=".plugin/plugin.json")],
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["features", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["features"][0]["name"], "copilot-plugin-root")

    @patch("plate_core.cli.run_bootstrap")
    def test_bootstrap_json_output(self, mock_run_bootstrap):
        mock_run_bootstrap.return_value = BootstrapReport(
            repo="akasper/plate_core",
            apply_mode=False,
            actions=[BootstrapAction(name="enable-wiki", state="planned", detail="Set has_wiki=true")],
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["bootstrap", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "akasper/plate_core")
        self.assertEqual(payload["actions"][0]["name"], "enable-wiki")


if __name__ == "__main__":
    unittest.main()
