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
            goals_page_present=True,
            repo="akasper/plate_core",
            label_coverage_ok=True,
            missing_labels=[],
            binary_artifacts_tracked=0,
            branch_protection_enabled=True,
            open_epic_count=2,
            status="pass",
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

    def test_config_show_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "show", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertFalse(payload["present"])
            self.assertEqual(payload["source"], "defaults")
            self.assertEqual(payload["resolved_version"], "1.1")

    def test_config_init_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["config", "init", "--repo-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload["present"])
            self.assertTrue((Path(tmp) / ".plate").exists())
            self.assertEqual(payload["resolved_version"], "1.1")

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
            self.assertEqual(payload["current_version"], "1.1")

    def test_agents_json_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["agents", "list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(len(payload["agents"]), 15)
        self.assertEqual(payload["agents"][0]["id"], "project-manager")

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

    @patch("plate_core.mcp.curiosity_tools.BackfillAnswersTool.execute")
    def test_qanda_backfill_json_output(self, mock_backfill):
        mock_backfill.return_value = {
            "repo": "akasper/plate",
            "processed_questions": [
                {
                    "question_number": 275,
                    "status": "backfilled",
                    "answers_written": 1,
                    "committed_file": "docs/curiosity/answers/host-agent.md",
                }
            ],
            "question_count": 1,
            "answers_written": 1,
        }
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["qanda", "--backfill", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertEqual(payload["question_count"], 1)
        self.assertEqual(payload["answers_written"], 1)

    @patch("plate_core.mcp.curiosity_tools.RecordAnswerTool.execute")
    def test_qanda_record_passes_revision_of(self, mock_record):
        mock_record.return_value = {
            "status": "recorded",
            "question_number": 275,
            "comment_url": "https://example.invalid/comment",
            "committed_storage": "docs/curiosity/answers/host-agent.md",
        }
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "qanda",
                    "--record",
                    "275",
                    "--answer",
                    "Revised answer",
                    "--revision-of",
                    "12345",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(mock_record.call_args.kwargs["revision_of"], "12345")
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


if __name__ == "__main__":
    unittest.main()
