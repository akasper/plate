import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plate_core.bootstrap import run_bootstrap
from plate_core.github_client import GhApiError
from plate_core.health import HealthReport


def _write_template_file(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_template_root() -> tempfile.TemporaryDirectory:
    tempdir = tempfile.TemporaryDirectory()
    root = Path(tempdir.name)
    _write_template_file(root, "AGENTS.md", "# AGENTS\n")
    _write_template_file(root, "README.md", "# README\n")
    _write_template_file(root, "docs/wiki/Goals.md", "# Goals\n")
    return tempdir


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

        def api_side(endpoint, *a, **k):
            endpoint = str(endpoint)
            if endpoint == "repos/akasper/plate_core":
                return {"has_wiki": False, "default_branch": "main"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/plate_core/contents/"):
                return {"type": "file"}
            return {}

        client.api.side_effect = api_side
        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch("plate_core.bootstrap.resolve_template_source_root", return_value=template_root):
                report = run_bootstrap("akasper/plate_core", apply_mode=False, client=client)
        states = {a.name: a.state for a in report.actions}
        self.assertEqual(states["copy-template-payload"], "planned")
        self.assertEqual(states["enable-wiki"], "planned")
        self.assertEqual(states["branch-protection"], "manual-required")
        copy_action = next((a for a in report.actions if a.name == "copy-template-payload"), None)
        self.assertIsNotNone(copy_action, "copy-template-payload action must be present")
        self.assertIn("Copy 3 template payload files", copy_action.detail)
        plate_action = next((a for a in report.actions if a.name == "init-plate-config"), None)
        self.assertIsNotNone(plate_action, "init-plate-config action must be present for #259")
        self.assertEqual(plate_action.state, "planned")
        self.assertIn("root .plate", plate_action.detail)
        seed_action = next((a for a in report.actions if a.name == "seed-initial-questions"), None)
        self.assertIsNotNone(seed_action, "seed-initial-questions action must be present")
        self.assertEqual(seed_action.state, "planned")
        self.assertIn("Seed", seed_action.detail)

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
            endpoint = str(endpoint)
            method = k.get("method", "GET")
            if endpoint == "repos/akasper/test-repo":
                return {"has_wiki": False, "default_branch": "main"}
            if "/issues?" in endpoint and "labels=Question" in endpoint:
                return []
            if endpoint.startswith("repos/akasper/test-repo/contents/"):
                if "README.md" in endpoint and method == "GET":
                    return {"type": "file"}
                if method == "GET":
                    raise GhApiError("HTTP 404 Not Found")
                return {}
            if endpoint == "repos/akasper/test-repo/labels":
                return {}
            if endpoint == "repos/akasper/test-repo/issues":
                return {}
            if endpoint == "repos/akasper/test-repo/branches/main":
                return {"commit": {"sha": "abc123"}}
            if endpoint.startswith("repos/akasper/test-repo/branches/"):
                raise GhApiError("HTTP 404 Not Found")
            if endpoint == "repos/akasper/test-repo/git/refs":
                return {}
            return {}

        client.api.side_effect = api_side

        with _make_template_root() as tmpdir:
            template_root = Path(tmpdir)
            with patch("plate_core.bootstrap.resolve_template_source_root", return_value=template_root):
                report = run_bootstrap("akasper/test-repo", apply_mode=True, client=client)

        # Find the PATCH call for has_wiki
        patch_calls = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo" in str(call.args[0])
            and call.kwargs.get("method") == "PATCH"
        ]
        self.assertTrue(patch_calls, "Expected a PATCH call for has_wiki")
        fields = patch_calls[0].kwargs.get("fields", {})
        self.assertIs(fields.get("has_wiki"), True, "has_wiki must be Python bool True, not a string")

        copy_action = next((a for a in report.actions if a.name == "copy-template-payload"), None)
        self.assertIsNotNone(copy_action)
        self.assertEqual(copy_action.state, "applied")

        # Verify copied template files were uploaded, but existing files were preserved.
        template_puts = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo/contents/" in str(call.args[0])
            and call.kwargs.get("method") == "PUT"
        ]
        endpoints = [str(call.args[0]) for call in template_puts]
        self.assertTrue(any("AGENTS.md" in endpoint for endpoint in endpoints))
        self.assertTrue(any("docs%2Fwiki%2FGoals.md" in endpoint for endpoint in endpoints))
        self.assertFalse(any("README.md" in endpoint for endpoint in endpoints))

        # Verify 3 starter Question POSTs were issued (new Feature #153 behavior)
        question_posts = [
            call for call in client.api.call_args_list
            if call.args and "repos/akasper/test-repo/issues" in str(call.args[0])
            and call.kwargs.get("method") == "POST"
            and "Question" in str(call.kwargs.get("fields", {}).get("labels", []))
        ]
        self.assertEqual(len(question_posts), 3, "Expected exactly 3 POSTs to seed starter Questions on apply when none exist")

        plate_puts = [
            call for call in client.api.call_args_list
            if call.args and "contents/.plate" in str(call.args[0])
            and call.kwargs.get("method") == "PUT"
        ]
        self.assertTrue(plate_puts, "Expected PUT to create .plate on apply when missing")


if __name__ == "__main__":
    unittest.main()
