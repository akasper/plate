"""Tests for pre-push hook template and runner (#1281)."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plate_core.cli import main as cli_main
from plate_core.git_hooks import (
    GitHookError,
    _parse_name_only_z_output,
    build_command_argv,
    collect_changed_files_by_commit,
    collect_changed_files_for_push,
    get_pre_push_commands,
    install_pre_push_hook,
    parse_pre_push_stdin,
    pre_push_status,
    run_pre_push,
    validate_hooks_config,
)
from plate_core.plate_config import (
    PlateConfig,
    PlateConfigError,
    load_plate_config,
    save_plate_config,
    validate_plate_config,
)


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

    def test_plate_config_preserves_hooks_on_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hooks = {"pre_push": {"format": "fmt {files}", "lint": "", "typecheck": "tpy {files}"}}
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "hooks": hooks}),
                encoding="utf-8",
            )
            loaded = load_plate_config(root)
            self.assertEqual(loaded.hooks["pre_push"]["format"], "fmt {files}")
            save_plate_config(loaded, root, overwrite=True)
            saved = json.loads((root / ".plate").read_text(encoding="utf-8"))
            self.assertEqual(saved["hooks"], hooks)

    def test_plate_config_from_dict_includes_hooks(self):
        cfg = PlateConfig.from_dict(
            {"version": "1.3", "hooks": {"pre_push": {"lint": "ruff check {files}"}}}
        )
        self.assertEqual(cfg.to_dict()["hooks"]["pre_push"]["lint"], "ruff check {files}")


class TestPrePushHookRunner(unittest.TestCase):
    def test_parse_stdin(self):
        data = "refs/heads/main abc refs/remotes/origin/main def\n"
        rows = parse_pre_push_stdin(io.StringIO(data))
        self.assertEqual(rows, [("refs/heads/main", "abc", "refs/remotes/origin/main", "def")])

    def test_build_command_argv_preserves_paths_with_spaces(self):
        argv = build_command_argv("echo {files}", ["a b", "c"])
        self.assertEqual(argv, ["echo", "a b", "c"])

    def test_parse_name_only_z_output(self):
        raw = b"a b.txt\0c.txt\0"
        self.assertEqual(_parse_name_only_z_output(raw), ["a b.txt", "c.txt"])

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

    def test_diff_failure_blocks_push(self):
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
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "hooks": {"pre_push": {"lint": "true"}}}),
                encoding="utf-8",
            )
            missing = "f" * 40
            stdin = f"refs/heads/main {head} refs/remotes/origin/main {missing}\n"
            with self.assertRaises(GitHookError):
                collect_changed_files_by_commit(
                    root,
                    [("refs/heads/main", head, "refs/remotes/origin/main", missing)],
                )
            self.assertEqual(run_pre_push(root, stdin=io.StringIO(stdin)), 1)

    def test_checks_use_committed_snapshot_not_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            (root / "f.txt").write_text("committed", encoding="utf-8")
            subprocess.run(["git", "add", "f.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "c1"], cwd=root, check=True)
            local_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (root / "f.txt").write_text("working-tree-only", encoding="utf-8")
            zero = "0" * 40
            check_cmd = (
                "python3 -c "
                "\"import sys; sys.exit(0 if open(sys.argv[1], encoding='utf-8').read()=='committed' else 1)\" "
                "{files}"
            )
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "hooks": {"pre_push": {"lint": check_cmd}}}),
                encoding="utf-8",
            )
            stdin = f"refs/heads/main {local_sha} refs/remotes/origin/main {zero}\n"
            self.assertEqual(run_pre_push(root, stdin=io.StringIO(stdin)), 0)

    def test_modified_snapshot_blocks_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            (root / "f.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "add", "f.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "c1"], cwd=root, check=True)
            local_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            zero = "0" * 40
            mut_cmd = (
                "python3 -c "
                "\"import sys; open(sys.argv[1], 'a', encoding='utf-8').write('y')\" {files}"
            )
            (root / ".plate").write_text(
                json.dumps({"version": "1.3", "hooks": {"pre_push": {"format": mut_cmd}}}),
                encoding="utf-8",
            )
            stdin = f"refs/heads/main {local_sha} refs/remotes/origin/main {zero}\n"
            self.assertEqual(run_pre_push(root, stdin=io.StringIO(stdin)), 1)


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


class TestPrePushHookCli(unittest.TestCase):
    def test_hooks_status_json_after_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = cli_main(["hooks", "status", "--repo-root", str(root), "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertIn("hook_installed", payload)


if __name__ == "__main__":
    unittest.main()
