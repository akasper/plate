"""Tests for gh plate evidence / plate_pr_evidence (#1051)."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plate_core.mcp.path_confinement import PathConfinementError, session_repo_root
from plate_core.plate_evidence import (
    COPILOT_ROUTE_MESSAGE,
    USER_ATTACHMENTS_PREFIX,
    confine_evidence_paths,
    gh_subprocess_env,
    prepare_body_with_images,
    resolve_gh_executable,
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

    def test_gh_subprocess_env_omits_tokens(self):
        with mock.patch.dict(
            os.environ,
            {"PATH": "/bin", "GH_TOKEN": "secret", "GITHUB_TOKEN": "secret2", "HOME": "/home/x"},
            clear=True,
        ):
            env = gh_subprocess_env()
        self.assertIn("PATH", env)
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env.get("HOME"), "/home/x")


class PlateEvidenceConfinementTests(unittest.TestCase):
    def test_traversal_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "body.md").write_text("x", encoding="utf-8")
            (root / "shot.png").write_bytes(b"x")
            outside = str(Path(tmp).parent / "outside-evidence.png")
            _, _, err = confine_evidence_paths("body.md", [outside], root)
            self.assertEqual(err, "Path escapes the repository root")

    def test_absolute_path_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            err_path = confine_evidence_paths("/etc/passwd", ["shot.png"], root)[2]
            self.assertEqual(err_path, "Path escapes the repository root")

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = Path(tmp).parent / "evidence-secret-out"
            secret.mkdir(exist_ok=True)
            (secret / "leak.png").write_bytes(b"x")
            link = root / "link.png"
            try:
                link.symlink_to(secret / "leak.png")
            except OSError as exc:
                self.skipTest(f"symlink not permitted: {exc}")
            _, _, err = confine_evidence_paths("body.md", [link], root)
            self.assertEqual(err, "Path escapes the repository root")

    def test_resolve_gh_confined_under_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gh = root / "fake-gh"
            gh.write_text("#!/bin/sh\n", encoding="utf-8")
            got, err = resolve_gh_executable(str(gh), root)
            self.assertIsNone(err)
            self.assertEqual(got, str(gh.resolve()))

    def test_resolve_gh_outside_repo_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "evil-gh"
            outside.write_text("#!/bin/sh\n", encoding="utf-8")
            got, err = resolve_gh_executable(str(outside), root, mcp_mode=True)
            self.assertIsNone(got)
            self.assertEqual(err, "Path escapes the repository root")

    def test_to_client_dict_redacts_paths(self):
        from plate_core.plate_evidence import PlateEvidenceResult

        root = session_repo_root()
        secret = str(root / "docs" / "body.md")
        result = PlateEvidenceResult(
            ok=False,
            pr_number=1,
            body_file=secret,
            images=(str(root / "shot.png"),),
            user_attachment_urls=(),
            error=f"failed at {secret}",
        )
        client = result.to_client_dict(root)
        self.assertNotIn(str(root), client["body_file"])
        self.assertNotIn(str(root), client["images"][0])
        self.assertNotIn(str(root), client["error"])


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

            result = run_plate_evidence(
                1, body, [img], gh=str(gh), repo_root=tmp_path, runner=runner
            )
            self.assertFalse(result.ok)
            self.assertIn("2.99", result.error or "")

    def test_success_confirms_user_attachments(self):
        asset = f"{USER_ATTACHMENTS_PREFIX}abc123"
        calls: list[list[str]] = []

        def runner(argv, **kwargs):
            env = kwargs.get("env") or {}
            self.assertNotIn("GH_TOKEN", env)
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

            result = run_plate_evidence(
                42, body, [img], gh=str(gh), repo_root=tmp_path, runner=runner
            )
            self.assertTrue(result.ok, result.error)
            self.assertIn(asset, result.user_attachment_urls)
            edit_calls = [c for c in calls if len(c) >= 3 and c[1:3] == ["pr", "edit"]]
            self.assertEqual(len(edit_calls), 1)
            self.assertIn("--attach", edit_calls[0])
            self.assertIn(str(img.resolve()), edit_calls[0])

    def test_refused_upload_prints_copilot_route(self):
        def runner(argv, **kwargs):
            if len(argv) >= 2 and argv[1] == "--version":
                return mock.Mock(returncode=0, stdout="gh version 2.99.0\n", stderr="")
            if len(argv) >= 3 and argv[2] == "edit":
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="HTTP 404: unsupported authentication type",
                )
            return mock.Mock(returncode=1, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gh = tmp_path / "gh"
            gh.write_text("#!/bin/sh\n", encoding="utf-8")
            body = tmp_path / "body.md"
            body.write_text("x", encoding="utf-8")
            img = tmp_path / "shot.png"
            img.write_bytes(b"x")

            result = run_plate_evidence(
                7, body, [img], gh=str(gh), repo_root=tmp_path, runner=runner
            )
            self.assertFalse(result.ok)
            self.assertTrue(result.refused_upload)
            self.assertEqual(result.error, COPILOT_ROUTE_MESSAGE)


class PlateEvidenceMcpTests(unittest.TestCase):
    def test_mcp_tool_delegates_with_repo_root_and_redaction(self):
        from plate_core.mcp_server import _execute_mcp_tool
        from plate_core.plate_evidence import PlateEvidenceResult

        root = session_repo_root()
        expected = PlateEvidenceResult(
            ok=True,
            pr_number=99,
            body_file=str(root / "body.md"),
            images=(str(root / "a.png"),),
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
        kwargs = mocked.call_args.kwargs
        self.assertTrue(kwargs.get("mcp_mode"))
        self.assertIn("repo_root", kwargs)
        self.assertNotIn(str(root), payload["body_file"])


class PlateEvidenceLibraryConfinementIntegration(unittest.TestCase):
    def test_run_without_repo_root_uses_session_root_for_attach_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prev = os.getcwd()
            try:
                os.chdir(root)
                outside = Path(tmp).parent / "mcp-evidence-outside"
                outside.mkdir(exist_ok=True)
                result = run_plate_evidence(
                    1,
                    str(outside / "body.md"),
                    [str(outside / "x.png")],
                    gh="gh",
                    repo_root=root,
                )
            finally:
                os.chdir(prev)
            self.assertFalse(result.ok)
            self.assertEqual(result.error, "Path escapes the repository root")


if __name__ == "__main__":
    unittest.main()