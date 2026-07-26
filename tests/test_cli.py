import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plate_core.cli import main
from plate_core.pr_babysit import BabysitReport
from plate_core.bootstrap import BootstrapAction, BootstrapReport
from plate_core.epics import EpicStatusReport, EpicSummary
from plate_core.features import FeatureFlag, FeatureReport
from plate_core.health import HealthReport
from plate_core.migration import generate_migration_plan, apply_migration_plan


class CliTests(unittest.TestCase):
    @patch("plate_core.cli.get_health")
    def test_health_json_output(self, mock_get_health):
        mock_get_health.return_value = HealthReport(
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=2,
            status="pass",
            goals_page_present=True,
            open_question_count=1,
            plate_config_present=False,
            plate_config_valid=False,
            curiosity_answers_present=False,
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

    @patch("plate_core.cli.run_bootstrap")
    def test_bootstrap_json_error_output(self, mock_run_bootstrap):
        mock_run_bootstrap.side_effect = RuntimeError("boom")
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["bootstrap", "--repo", "akasper/plate_core", "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["error"], "boom")

    def test_config_show_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "show", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertFalse(payload["present"])
            self.assertEqual(payload["source"], "defaults")
            self.assertEqual(payload["resolved_version"], "1.2")

    def test_config_init_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "init", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload["present"])
            self.assertTrue((Path(tmp) / ".plate").exists())
            self.assertEqual(payload["resolved_version"], "1.2")

    def test_config_validate_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".plate").write_text("{not-json", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "validate", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 1)
            payload = json.loads(out.getvalue().strip())
            self.assertFalse(payload["valid"])

    def test_config_upgrade_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "methodology": {"marker_prefix": "PLATES-CORE"},
                        "extensions": {"enabled": True, "installed": {"release-track-management": True}},
                        "overrides": {},
                    }
                ),
                encoding="utf-8",
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "upgrade", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload["changed"])
            self.assertFalse(payload["applied"])
            self.assertEqual(payload["current_version"], "1.2")

    def test_agents_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(len(payload["agents"]), 15)
        self.assertEqual(payload["agents"][0]["id"], "project-manager")

    def test_context_list_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["context", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertGreaterEqual(len(payload["contexts"]), 6)
        self.assertEqual(payload["contexts"][0]["id"], "process")

    def test_context_show_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["context", "show", "release-targeting", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["id"], "release-targeting")
        self.assertIn("gh plate release status", payload["machine_surfaces"])

    def test_agent_show_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "show", "research-agent", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["id"], "research-agent")
        self.assertIn("research-synthesis", payload["primary_skill_ids"])

    def test_skills_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["skills", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertGreaterEqual(len(payload["skills"]), 18)
        self.assertEqual(payload["skills"][0]["id"], "crud-projects")

    @patch("plate_core.cli.babysit_pr")
    def test_pr_babysit_json_output(self, mock_babysit):
        mock_babysit.return_value = BabysitReport(
            repo="akasper/plate",
            pr_number=112,
            detected_threads=2,
            actionable_threads=1,
            trigger_comment_posted=True,
            trigger_comment_url="https://github.com/akasper/plate/pull/112#issuecomment-1",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["pr", "babysit", "112", "--repo", "akasper/plate", "--json", "--act"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["pr_number"], 112)
        self.assertTrue(payload["trigger_comment_posted"])

    @patch("plate_core.cli.core_cut_release")
    def test_release_cut_json_output(self, mock_core_cut):
        """First-class release cut using core (for #261)."""
        mock_core_cut.return_value = 0
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["release", "cut", "v0.1.5", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_core_cut.called)
        # Note: full output from core in real run; here stub verifies wiring.

    @patch("plate_core.cli.cleanup_dead_branches")
    def test_release_cleanup_branches_json_output(self, mock_cleanup):
        mock_cleanup.return_value = type(
            "CleanupReport",
            (),
            {
                "to_dict": lambda self: {
                    "repo": "owner/repo",
                    "base_branch": "main",
                    "apply": False,
                    "scanned_branches": 5,
                    "candidates": ["feature-merged"],
                    "deleted": [],
                    "failed": [],
                    "skipped_open_pr": [],
                    "skipped_not_merged": [],
                    "warnings": [],
                }
            },
        )()
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["release", "cleanup-branches", "--repo", "owner/repo", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["repo"], "owner/repo")
        self.assertEqual(payload["candidates"], ["feature-merged"])


    @patch("plate_core.release.create_github_release")
    @patch("plate_core.release.perform_guarded_hard_reset")
    @patch("plate_core.release.ensure_next_release_issue")
    def test_release_finalize_dry_run_and_apply(self, mock_ensure, mock_reset, mock_create):
        """#592: finalize now calls core automation (create always, reset only on --apply)."""
        mock_create.return_value = {"tag": "v0.7.1", "exists": True, "created": False}
        mock_reset.return_value = {"would_reset": True, "command": "git ..."}
        mock_ensure.return_value = {"exists": True}
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["release", "finalize", "v0.7.1", "--dry-run"])
        self.assertEqual(code, 0)
        mock_create.assert_called()
        args, kwargs = mock_reset.call_args
        self.assertFalse(kwargs.get("apply", False))

    @patch("plate_core.cli.get_autonomy_status")
    def test_autonomy_status_prints_pressure_and_pause(self, mock_status):
        """#634/#653: human-readable status surfaces pressure + next-cycle gate."""
        mock_status.return_value = {
            "enabled": False,
            "risk_tolerance": "off",
            "autopilot_score": 65,
            "burn_rate": 86.0,
            "budget_remaining_tokens": 7000,
            "daily_limit": 50000,
            "budget_pressure": "critical",
            "would_pause_next_cycle": True,
            "would_throttle_next_cycle": False,
            "spent_today_durable": 43000,
            "due_procedures": [],
            "throttled_actions": 0,
            "open_human_checkpoints": ["cp-1: Approve deploy"],
            "last_cycle": "2026-07-26T00:00:00+00:00",
        }
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["autonomy", "--status"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("Budget pressure: critical", text)
        self.assertIn("would_pause=True", text)
        self.assertIn("Budget remaining tokens: 7000/50000", text)
        self.assertIn("Open checkpoints: 1", text)


if __name__ == "__main__":
    unittest.main()
