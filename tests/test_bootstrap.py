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
            goals_page_present=False,
            open_question_count=0,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
        )
        client = Mock()
        # api side effect: repo_obj dict for /repos/* (no ?), [] for questions list endpoint
        def api_side(endpoint, *a, **k):
            if "/issues?" in str(endpoint) and "labels=Question" in str(endpoint):
                return []
            if "contents/docs/wiki/Goals.md" in str(endpoint):
                raise Exception("not found")  # simulate missing Goals for #266 test
            return {"has_wiki": False}
        client.api.side_effect = api_side
        report = run_bootstrap("akasper/plate_core", apply_mode=False, client=client)
        states = {a.name: a.state for a in report.actions}
        self.assertEqual(states["enable-wiki"], "planned")
        self.assertEqual(states["branch-protection"], "manual-required")
        seed_action = next((a for a in report.actions if a.name == "seed-initial-questions"), None)
        self.assertIsNotNone(seed_action, "seed-initial-questions action must be present")
        self.assertEqual(seed_action.state, "planned")
        self.assertIn("Seed", seed_action.detail)
        goals_action = next((a for a in report.actions if a.name == "init-goals-page"), None)
        self.assertIsNotNone(goals_action, "init-goals-page action must be present for #266")
        self.assertEqual(goals_action.state, "planned")
        self.assertIn("Initialize docs/wiki/Goals.md", goals_action.detail)

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
            goals_page_present=True,
            open_question_count=0,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
        )
        client = Mock()
        def api_side(endpoint, *a, **k):
            if "/issues?" in str(endpoint) and "labels=Question" in str(endpoint):
                return []
            if "contents/docs/wiki/Goals.md" in str(endpoint):
                raise Exception("not found")  # simulate missing Goals for #266 test
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

        # #266 / #229: Goals page init on apply when missing (PUT to contents)
        goals_puts = [
            call for call in client.api.call_args_list
            if call.args and "contents/docs%2Fwiki%2FGoals.md" in str(call.args[0])
            and call.kwargs.get("method") == "PUT"
        ]
        self.assertTrue(goals_puts, "Expected PUT to create docs/wiki/Goals.md on apply when missing")


if __name__ == "__main__":
    unittest.main()
