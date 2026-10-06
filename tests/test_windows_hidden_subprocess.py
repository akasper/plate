"""Regression tests for hidden Windows subprocesses and babysit watch cleanup (#1073)."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plate_core.cli import build_parser
from plate_core.procutil import CREATE_NO_WINDOW, SW_HIDE, hidden_subprocess_kwargs, run_hidden
from plate_core.pr_babysit import (
    claim_babysit_watch,
    pid_is_alive,
    sleep_until_watch_interval,
    stop_babysit_watchers,
)


class HiddenSubprocessTests(unittest.TestCase):
    def test_windows_sets_creation_flags_and_utf8(self):
        with patch("plate_core.procutil.sys.platform", "win32"):
            kwargs = hidden_subprocess_kwargs({"text": True, "capture_output": True})
        self.assertTrue(kwargs["creationflags"] & CREATE_NO_WINDOW)
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertEqual(kwargs["env"]["GH_NO_UPDATE_NOTIFIER"], "1")
        self.assertEqual(kwargs["env"]["DO_NOT_TRACK"], "1")
        startup = kwargs.get("startupinfo")
        if startup is not None:
            self.assertEqual(startup.wShowWindow, SW_HIDE)

    def test_run_hidden_passes_windows_flags(self):
        with patch("plate_core.procutil.sys.platform", "win32"), patch(
            "plate_core.procutil.subprocess.run"
        ) as mock_run:
            run_hidden(["gh", "api", "user"], capture_output=True, text=True, check=False)
        passed = mock_run.call_args.kwargs
        self.assertTrue(passed["creationflags"] & CREATE_NO_WINDOW)
        self.assertEqual(passed["encoding"], "utf-8")
        self.assertFalse(passed.get("shell"))
        self.assertEqual(mock_run.call_args.args[0], ["gh", "api", "user"])

    def test_posix_omits_windows_flags(self):
        with patch("plate_core.procutil.sys.platform", "linux"):
            kwargs = hidden_subprocess_kwargs({"text": True})
        self.assertNotIn("creationflags", kwargs)
        self.assertNotIn("startupinfo", kwargs)
        self.assertEqual(kwargs["encoding"], "utf-8")

    def test_shell_true_is_rejected(self):
        with self.assertRaises(ValueError):
            hidden_subprocess_kwargs({"shell": True})

    def test_caller_quiet_env_is_preserved(self):
        kwargs = hidden_subprocess_kwargs(
            {"env": {"GH_NO_UPDATE_NOTIFIER": "0", "PATH": "x"}}
        )
        self.assertEqual(kwargs["env"]["GH_NO_UPDATE_NOTIFIER"], "0")
        self.assertEqual(kwargs["env"]["DO_NOT_TRACK"], "1")
        self.assertEqual(kwargs["env"]["PATH"], "x")
        self.assertNotIn("SystemRoot", kwargs["env"])

    def test_existing_creationflags_are_kept(self):
        with patch("plate_core.procutil.sys.platform", "win32"):
            kwargs = hidden_subprocess_kwargs({"creationflags": 0x10})
        self.assertEqual(kwargs["creationflags"] & 0x10, 0x10)
        self.assertTrue(kwargs["creationflags"] & CREATE_NO_WINDOW)


class BabysitWatchPidTests(unittest.TestCase):
    def test_second_claim_reports_the_live_watcher(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=True):
                first = claim_babysit_watch("akasper/plate", 63, root=root, pid=4242, ppid=100)
                second = claim_babysit_watch("akasper/plate", 63, root=root, pid=9999, ppid=100)
            self.assertTrue(first["claimed"])
            self.assertFalse(second["claimed"])
            self.assertEqual(second["existing"]["pid"], 4242)
            self.assertTrue(Path(first["pidfile"]).is_file())

    def test_stop_kills_the_recorded_pid_and_removes_the_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=True), patch(
                "plate_core.pr_babysit.terminate_pid"
            ) as mock_kill:
                claim = claim_babysit_watch("akasper/u.ai", 63, root=root, pid=4242, ppid=100)
                pidfile = Path(claim["pidfile"])
                stopped = stop_babysit_watchers(repo="akasper/u.ai", pr_number=63, root=root)
            mock_kill.assert_called_once_with(4242)
            self.assertEqual(len(stopped), 1)
            self.assertTrue(stopped[0]["stopped"])
            self.assertTrue(stopped[0]["was_alive"])
            self.assertFalse(pidfile.exists())

    def test_stale_pidfile_is_replaced_without_a_second_watcher(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=False):
                first = claim_babysit_watch("akasper/plate", 63, root=root, pid=1, ppid=2)
                second = claim_babysit_watch("akasper/plate", 63, root=root, pid=3, ppid=4)
            self.assertTrue(second["claimed"])
            self.assertEqual(first["pidfile"], second["pidfile"])
            data = json.loads(Path(second["pidfile"]).read_text(encoding="utf-8"))
            self.assertEqual(data["pid"], 3)
            self.assertEqual(data["repo"], "akasper/plate")
            self.assertEqual(data["pr_number"], 63)

    def test_stop_leaves_a_dead_pidfile_removed_and_skips_terminate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            claim = claim_babysit_watch("owner/repo", 7, root=root, pid=55, ppid=1)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=False), patch(
                "plate_core.pr_babysit.terminate_pid"
            ) as mock_kill:
                stopped = stop_babysit_watchers(root=root)
            mock_kill.assert_not_called()
            self.assertTrue(stopped[0]["stopped"])
            self.assertFalse(stopped[0]["was_alive"])
            self.assertFalse(Path(claim["pidfile"]).exists())

    def test_stop_refuses_to_kill_the_current_process(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            claim = claim_babysit_watch("owner/repo", 1, root=root, pid=os.getpid(), ppid=1)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=True), patch(
                "plate_core.pr_babysit.terminate_pid"
            ) as mock_kill:
                stopped = stop_babysit_watchers(root=root)
            mock_kill.assert_not_called()
            self.assertFalse(stopped[0]["stopped"])
            self.assertIn("current process", stopped[0]["error"])
            self.assertTrue(Path(claim["pidfile"]).exists())

    def test_stop_can_target_one_pr(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("plate_core.pr_babysit.pid_is_alive", return_value=True), patch(
                "plate_core.pr_babysit.terminate_pid"
            ):
                keep = claim_babysit_watch("akasper/plate", 1, root=root, pid=11, ppid=1)
                drop = claim_babysit_watch("akasper/plate", 2, root=root, pid=22, ppid=1)
                stopped = stop_babysit_watchers(pr_number=2, root=root)
            self.assertEqual([item["pr_number"] for item in stopped], [2])
            self.assertTrue(Path(keep["pidfile"]).is_file())
            self.assertFalse(Path(drop["pidfile"]).exists())

    def test_sleep_returns_immediately_when_the_parent_is_gone(self):
        calls: list[float] = []
        with patch("plate_core.pr_babysit.pid_is_alive", return_value=False):
            keep = sleep_until_watch_interval(30, 50, sleeper=calls.append)
        self.assertFalse(keep)
        self.assertEqual(calls, [])

    def test_sleep_polls_until_the_interval_when_the_parent_stays(self):
        calls: list[float] = []
        with patch("plate_core.pr_babysit.pid_is_alive", return_value=True):
            keep = sleep_until_watch_interval(2, 50, sleeper=calls.append)
        self.assertTrue(keep)
        self.assertEqual(calls, [1, 1])

    def test_pid_is_alive_rejects_non_positive_and_accepts_self(self):
        self.assertFalse(pid_is_alive(0))
        self.assertFalse(pid_is_alive(-1))
        self.assertTrue(pid_is_alive(os.getpid()))

    def test_cli_stop_does_not_require_a_pr_number(self):
        args = build_parser().parse_args(["pr", "babysit", "--stop"])
        self.assertTrue(args.stop)
        self.assertIsNone(args.pr_number)
        watched = build_parser().parse_args(["pr", "babysit", "63", "--watch"])
        self.assertEqual(watched.pr_number, 63)
        self.assertTrue(watched.watch)
        self.assertFalse(watched.stop)


if __name__ == "__main__":
    unittest.main()
