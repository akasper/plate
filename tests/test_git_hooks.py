"""Tests for pre-push hook template and runner (#1281)."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from plate_core.git_hooks import (
    collect_changed_files_for_push,
    get_pre_push_commands,
    install_pre_push_hook,
    parse_pre_push_stdin,
    pre_push_status,
    render_command_for_files,
    run_pre_push,
    validate_hooks_config,
)
from plate_core.plate_config import PlateConfigError, validate_plate_config


class TestPrePushHookConfig(unittest.TestCase):
    def test_validate_hooks_rejects_unknown_keys(self):
        with self.assertRaises(PlateConfigError):
            validate_hooks_config({"pre_push": {"format": "x"}, "other": {}})
        with self.assertRaises(PlateConfigError):
            validate_hooks_config({"pre_push": {"format": "x", "extra": "y"}})

    def test_strict_top_level_allows_hooks(self):
        validate_plate_config(
            {
                "version": "1.3",
                "hooks": {"pre_push": {"format": "", "lint": "", "typecheck": ""}},
            },
            strict=True,
        )

    def test_no_commands_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(json.dumps({"version": "1.3"}), encoding="utf-8")
            self.assertEqual(get_pre_push_commands(root), [])


class TestPrePushHookRunner(unittest.TestCase):
    def test_parse_stdin(self):
        data = "refs/heads/main abc refs/remotes/origin/main def\n"
        rows = parse_pre_push_stdin(io.StringIO(data))
        self.assertEqual(rows, [("refs/heads/main", "abc", "refs/remotes/origin/main", "def")])

    def test_render_files_placeholder(self):
        out = render_command_for_files("echo {files}", ["a b", "c"])
        self.assertIn("'a b'", out)
        self.assertTrue(out.endswith(" c") or out.endswith(" 'c'") or " c" in out or out.endswith("c"))

    def test_run_pre_push_silent_without_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".plate").write_text(json.dumps({"version": "1.3"}), encoding="utf-8")
            stdin = "refs/heads/main abc refs/remotes/origin/main def\n"
            self.assertEqual(run_pre_push(root, stdin=io.StringIO(stdin)), 0)

    def test_run_pre_push_invokes_configured_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            (root / "f.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "add", "f.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
            local_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            zero = "0" * 40
            (root / ".plate").write_text(
                json.dumps(
                    {
                        "version": "1.3",
                        "hooks": {"pre_push": {"lint": "test -f {files}"}},
                    }
                ),
                encoding="utf-8",
            )
            stdin = f"refs/heads/main {local_sha} refs/remotes/origin/main {zero}\n"
            self.assertEqual(run_pre_push(root, stdin=io.StringIO(stdin)), 0)

    def test_collect_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            (root / "a.txt").write_text("1", encoding="utf-8")
            subprocess.run(["git", "add", "a.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "c1"], cwd=root, check=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
            ).stdout.strip()
            zero = "0" * 40
            files = collect_changed_files_for_push(
                root,
                [("refs/heads/main", head, "refs/remotes/origin/main", zero)],
            )
            self.assertIn("a.txt", files)


class TestPrePushHookInstall(unittest.TestCase):
    def test_install_writes_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            report = install_pre_push_hook(root)
            hook_path = Path(report.installed_path)
            self.assertTrue(hook_path.is_file())
            self.assertIn("PLATE pre-push hook", hook_path.read_text(encoding="utf-8"))
            status = pre_push_status(root)
            self.assertTrue(status.hook_installed)
            self.assertTrue(status.hook_is_plate)


if __name__ == "__main__":
    unittest.main()
