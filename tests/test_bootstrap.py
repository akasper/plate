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
            binary_artifacts_tracked=0,
            branch_protection_enabled=False,
            open_epic_count=0,
            status="warn",
        )
        client = Mock()
        # api side effect: repo_obj dict for /repos/* (no ?), [] for questions list endpoint
        def api_side(endpoint, *a, **k):
            if "/issues?" in str(endpoint) and "labels=Question" in str(endpoint):
                return []
            return {"has_wiki": False}
        client.api.side_effect = api_side
        report = run_bootstrap("akasper/plate_core", apply_mode=False, client=client)
        states = {a.name: a.state for a in report.actions}
        self.assertEqual(states["enable-wiki"], "planned")
        self.assertEqual(states["branch-protection"], "manual-required")
        seed_action = next((a for a in report.actions if a.name == "seed-initial-questions"), None)
        self.assertIsNotNone(seed_action, "seed-initial-questions action must be present")
        self.assertEqual(seed_action.state, "planned")
        self.assertIn("Seed 3 initial Curiosity Questions", seed_action.detail)

    @patch("plate_core.bootstrap.get_health")
    def test_apply_wiki_passes_bool_not_string(self, mock_get_health):
        """has_wiki must be sent as Python bool True so GhClient uses -F and gh
        interprets it as a JSON boolean, not the string 'true'."""
        mock_get_health.return_value = HealthReport(
            repo="akasper/test-repo",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=1,
            status="pass",
        )
        client = Mock()
        def api_side(endpoint, *a, **k):
            if "/issues?" in str(endpoint) and "labels=Question" in str(endpoint):
                return []
            return {"has_wiki": False}
        client.api.side_effect = api_side

        run_bootstrap("akasper/test-repo", apply_mode=True, client=client)

        # Find the PATCH call for has_wiki
        patch_calls = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo" in str(call.args[0])
            and call.kwargs.get("method") == "PATCH"
        ]
        self.assertTrue(patch_calls, "Expected a PATCH call for has_wiki")
        fields = patch_calls[0].kwargs.get("fields", {})
        self.assertIs(fields.get("has_wiki"), True, "has_wiki must be Python bool True, not a string")

        # Verify 3 starter Question POSTs were issued (new Feature #153 behavior)
        question_posts = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo/issues" in str(call.args[0])
            and call.kwargs.get("method") == "POST"
            and "Question" in str(call.kwargs.get("fields", {}).get("labels", []))
        ]
        self.assertEqual(len(question_posts), 3, "Expected exactly 3 POSTs to seed starter Questions on apply when none exist")


if __name__ == "__main__":
    unittest.main()

