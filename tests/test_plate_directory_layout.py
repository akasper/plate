import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plate_core.cli import main
from plate_core.github_client import GhApiError
from plate_core.health import get_health
from plate_core.plate_config import (
    PlateConfigError,
    _read_local_plate_config,
    get_plate_config_report,
    plate_directory_layout_error_message,
)


class PlateDirectoryLayoutTests(unittest.TestCase):
    def test_error_message_names_json_file_and_migration(self):
        msg = plate_directory_layout_error_message()
        self.assertIn("single JSON file", msg)
        self.assertIn("gh plate config validate", msg)
        self.assertIn("gh plate bootstrap --adopt --apply", msg)
        self.assertIn("docs/migration/adoption-guide.md", msg)

    def test_read_local_plate_config_raises_for_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            with self.assertRaises(PlateConfigError) as caught:
                _read_local_plate_config(root)
            self.assertEqual(str(caught.exception), plate_directory_layout_error_message())

    def test_get_plate_config_report_invalid_for_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            report = get_plate_config_report(root)
            self.assertTrue(report.present)
            self.assertFalse(report.valid)
            self.assertEqual(report.errors, [plate_directory_layout_error_message()])

    def test_config_validate_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["config", "validate", "--repo-root", str(root)])
            self.assertEqual(code, 1)
            combined = out.getvalue() + err.getvalue()
            self.assertIn(plate_directory_layout_error_message(), combined)
            self.assertNotIn("Traceback", combined)

    def test_config_show_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["config", "show", "--repo-root", str(root)])
            self.assertEqual(code, 1)
            combined = out.getvalue() + err.getvalue()
            self.assertIn(plate_directory_layout_error_message(), combined)
            self.assertNotIn("Traceback", combined)

    def test_config_show_json_exits_nonzero_for_directory_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["config", "show", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 1)
            payload = json.loads(out.getvalue().strip())
            self.assertFalse(payload.get("valid"))
            self.assertEqual(payload.get("errors"), [plate_directory_layout_error_message()])
            self.assertNotIn("Traceback", out.getvalue() + err.getvalue())

    def test_health_cli_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            out = io.StringIO()
            err = io.StringIO()
            with patch("plate_core.cli.get_health") as mock_health:
                from plate_core.health import HealthReport

                mock_health.return_value = HealthReport(
                    repo="owner/repo",
                    label_coverage_ok=True,
                    missing_labels=[],
                    branch_protection_enabled=True,
                    open_epic_count=0,
                    binary_artifacts_tracked=0,
                    status="pass",
                    goals_page_present=False,
                    plate_config_layout_error=plate_directory_layout_error_message(),
                )
                with redirect_stdout(out), redirect_stderr(err):
                    code = main(
                        [
                            "health",
                            "--repo",
                            "owner/repo",
                            "--repo-root",
                            str(root),
                        ]
                    )
            self.assertEqual(code, 1)
            text = out.getvalue()
            self.assertIn("UNRECOGNIZED", text)
            self.assertIn(plate_directory_layout_error_message(), text)
            self.assertNotIn(".plate/config: MISSING", text)
            self.assertNotIn("Traceback", text + err.getvalue())

    def test_health_json_exits_nonzero_for_directory_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            out = io.StringIO()
            with patch("plate_core.cli.get_health") as mock_health:
                from plate_core.health import HealthReport

                mock_health.return_value = HealthReport(
                    repo="owner/repo",
                    label_coverage_ok=True,
                    missing_labels=[],
                    branch_protection_enabled=True,
                    open_epic_count=0,
                    binary_artifacts_tracked=0,
                    status="pass",
                    goals_page_present=False,
                    plate_config_layout_error=plate_directory_layout_error_message(),
                )
                with redirect_stdout(out):
                    code = main(
                        [
                            "health",
                            "--repo",
                            "owner/repo",
                            "--repo-root",
                            str(root),
                            "--json",
                        ]
                    )
            self.assertEqual(code, 1)
            payload = json.loads(out.getvalue().strip())
            self.assertEqual(
                payload.get("plate_config_layout_error"),
                plate_directory_layout_error_message(),
            )

    def test_get_health_local_directory_layout(self):
        class RemoteFilePlateClient:
            def api(self, endpoint, **kwargs):
                if endpoint.startswith("repos/owner/repo/labels"):
                    return [{"name": "Bug"}, {"name": "Feature"}, {"name": "Epic"}]
                if endpoint == "repos/owner/repo":
                    return {"default_branch": "main"}
                if endpoint == "repos/owner/repo/branches/main/protection":
                    raise GhApiError("404")
                if endpoint.startswith("search/issues"):
                    return {"total_count": 0}
                if "contents/.plate" in endpoint:
                    raise GhApiError("404")
                if "contents/docs/wiki/Goals.md" in endpoint:
                    raise GhApiError("404")
                if "contents/docs/plate/wiki/Goals.md" in endpoint:
                    raise GhApiError("404")
                if "contents/docs/curiosity" in endpoint:
                    raise GhApiError("404")
                if "contents/AGENTS.md" in endpoint:
                    raise GhApiError("404")
                if "contents/.agentic" in endpoint:
                    raise GhApiError("404")
                raise AssertionError(endpoint)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            report = get_health(
                repo="owner/repo",
                client=RemoteFilePlateClient(),
                repo_root=str(root),
                include_spec_audit=False,
            )
            self.assertEqual(report.plate_config_layout_error, plate_directory_layout_error_message())
            self.assertFalse(report.plate_config_present)
            self.assertIn(".plate/ directory (unrecognized layout)", report.plate_repo_signals)

    def test_get_health_remote_file_local_directory_preserves_remote_flags(self):
        import base64

        plate_json = json.dumps({"version": "1.3", "platform": "posix"})
        encoded = base64.b64encode(plate_json.encode("utf-8")).decode("ascii")

        class RemoteFilePlateClient:
            def api(self, endpoint, **kwargs):
                if endpoint.startswith("repos/owner/repo/labels"):
                    return [{"name": "Bug"}, {"name": "Feature"}, {"name": "Epic"}]
                if endpoint == "repos/owner/repo":
                    return {"default_branch": "main"}
                if endpoint == "repos/owner/repo/branches/main/protection":
                    raise GhApiError("404")
                if endpoint.startswith("search/issues"):
                    return {"total_count": 0}
                if endpoint.endswith("contents/.plate"):
                    return {
                        "type": "file",
                        "encoding": "base64",
                        "content": encoded,
                    }
                if "contents/docs/wiki/Goals.md" in endpoint:
                    raise GhApiError("404")
                if "contents/docs/plate/wiki/Goals.md" in endpoint:
                    raise GhApiError("404")
                if "contents/docs/curiosity" in endpoint:
                    raise GhApiError("404")
                if "contents/AGENTS.md" in endpoint:
                    raise GhApiError("404")
                if "contents/.agentic" in endpoint:
                    raise GhApiError("404")
                raise AssertionError(endpoint)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").mkdir()
            report = get_health(
                repo="owner/repo",
                client=RemoteFilePlateClient(),
                repo_root=str(root),
                include_spec_audit=False,
            )
            self.assertEqual(report.plate_config_layout_error, plate_directory_layout_error_message())
            self.assertTrue(report.plate_config_present)
            self.assertTrue(report.plate_config_valid)
            self.assertIn(".plate/ directory (unrecognized layout)", report.plate_repo_signals)


if __name__ == "__main__":
    unittest.main()
