"""Tests for gh plate evidence / plate_pr_evidence (#1051)."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plate_core.plate_evidence import (
    COPILOT_ROUTE_MESSAGE,
    USER_ATTACHMENTS_PREFIX,
    prepare_body_with_images,
    run_plate_evidence,
    parse_gh_version,
    gh_version_ok,
)
class PlateEvidenceUnitTests(unittest.TestCase):
    def test_parse_gh_version(self):
        self.assertEqual(parse_gh_version("gh version 2.99.0 (2025-01-01)"), (2, 99, 0))
        self.assertIsNone(parse_gh_version("git version 2.43"))

    def test_gh_version_ok(self):
        self.assertTrue(gh_version_ok((2, 99, 0)))
        self.assertFalse(gh_version_ok((2, 98, 9)))

    def test_prepare_body_adds_reference_and_alt(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "desktop-after.png"
            img.write_bytes(b"png")
            body = "## Visual evidence\n"
            prepared, err = prepare_body_with_images(body, [img])
            self.assertIsNone(err)
            self.assertIn("![desktop after](./desktop-after.png)", prepared)

    def test_prepare_body_fixes_empty_alt(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "mobile-320.png"
            img.write_bytes(b"png")
            body = "![](mobile-320.png)"
            prepared, err = prepare_body_with_images(body, [img])
            self.assertIsNone(err)
            self.assertIn("![mobile 320](mobile-320.png)", prepared)


class FakeGhPlateEvidenceTests(unittest.TestCase):
    def _write_fake_gh(self, gh_path: Path, script: str) -> None:
        gh_path.write_text(script, encoding="utf-8")
        gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    def test_fails_on_old_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gh = tmp_path / "gh"
            self._write_fake_gh(
                gh,
                '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "gh version 2.98.0"; exit 0; fi\nexit 1\n',
            )
            body = tmp_path / "body.md"
            body.write_text("body", encoding="utf-8")
            img = tmp_path / "a.png"
            img.write_bytes(b"x")

            def runner(argv, **kwargs):
                return mock.Mock(
                    returncode=0 if argv[1:2] == ["--version"] else 1,
                    stdout="gh version 2.98.0\n" if argv[1:2] == ["--version"] else "",
                    stderr="",
                )

            result = run_plate_evidence(1, body, [img], gh=str(gh), runner=runner)
            self.assertFalse(result.ok)
            self.assertIn("2.99", result.error or "")

    def test_success_confirms_user_attachments(self):
        asset = f"{USER_ATTACHMENTS_PREFIX}abc123"
        calls: list[list[str]] = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if len(argv) >= 2 and argv[1] == "--version":
                return mock.Mock(returncode=0, stdout="gh version 2.99.0\n", stderr="")
            if len(argv) >= 3 and argv[0:3] == [calls[0][0], "pr", "edit"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if len(argv) >= 3 and argv[0:3] == [calls[0][0], "pr", "view"]:
                body = json.dumps({"body": f"![after]({asset})"})
                return mock.Mock(returncode=0, stdout=body, stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="unexpected")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gh = tmp_path / "gh"
            gh.write_text("#!/bin/sh\n", encoding="utf-8")
            body = tmp_path / "body.md"
            body.write_text("## Evidence\n", encoding="utf-8")
            img = tmp_path / "after.png"
            img.write_bytes(b"png")

            result = run_plate_evidence(42, body, [img], gh=str(gh), runner=runner)
            self.assertTrue(result.ok, result.error)
            self.assertIn(asset, result.user_attachment_urls)
            edit_calls = [c for c in calls if len(c) >= 3 and c[1:3] == ["pr", "edit"]]
            self.assertEqual(len(edit_calls), 1)
            self.assertIn("--attach", edit_calls[0])
            self.assertIn(str(img), edit_calls[0])

    def test_refused_upload_prints_copilot_route(self):
        def runner(argv, **kwargs):
            if len(argv) >= 2 and argv[1] == "--version":
                return mock.Mock(returncode=0, stdout="gh version 2.99.0\n", stderr="")
            if len(argv) >= 3 and argv[2] == "edit":
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="HTTP 404: upload attachment requires write access",
                )
            return mock.Mock(returncode=1, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gh = tmp_path / "gh"
            body = tmp_path / "body.md"
            body.write_text("x", encoding="utf-8")
            img = tmp_path / "shot.png"
            img.write_bytes(b"x")

            result = run_plate_evidence(7, body, [img], gh=str(gh), runner=runner)
            self.assertFalse(result.ok)
            self.assertTrue(result.refused_upload)
            self.assertEqual(result.error, COPILOT_ROUTE_MESSAGE)


class PlateEvidenceMcpTests(unittest.TestCase):
    def test_mcp_tool_delegates_to_runner(self):
        from plate_core.mcp_server import _execute_mcp_tool
        from plate_core.plate_evidence import PlateEvidenceResult

        expected = PlateEvidenceResult(
            ok=True,
            pr_number=99,
            body_file="/tmp/body.md",
            images=("/tmp/a.png",),
            user_attachment_urls=(f"{USER_ATTACHMENTS_PREFIX}abc",),
        )
        with mock.patch.dict(os.environ, {"PLATE_MCP_TOOL_PROFILES": "all"}, clear=False):
            with mock.patch("plate_core.plate_evidence.run_plate_evidence", return_value=expected) as mocked:
                payload = _execute_mcp_tool(
                    "plate_pr_evidence",
                    {
                        "pr_number": 99,
                        "body_file": "body.md",
                        "images": ["a.png"],
                    },
                )
        self.assertTrue(payload["ok"])
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], 99)