import unittest
from unittest.mock import Mock, patch

from plate_core.bootstrap import run_bootstrap
from plate_core.health import HealthReport


class BootstrapTests(unittest.TestCase):
    @patch("plate_core.bootstrap.get_health")
    def test_dry_run_reports_planned_actions(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=False,
            missing_labels=["Feature", "Epic"],
            branch_protection_enabled=False,
            open_epic_count=0,
            status="warn",
        )
        client = Mock()
        client.api.return_value = {"has_wiki": False}
        report = run_bootstrap("akasper/plate_core", apply_mode=False, client=client)
        states = {a.name: a.state for a in report.actions if a.name in {"enable-wiki", "branch-protection"}}
        self.assertEqual(states["enable-wiki"], "planned")
        self.assertEqual(states["branch-protection"], "manual-required")


if __name__ == "__main__":
    unittest.main()

