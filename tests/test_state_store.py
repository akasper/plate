"""Tests for plate_core.state_store (#1368)."""

from __future__ import annotations

import json
import os
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plate_core.state_store import (
    CorruptStateError,
    IllegalTransition,
    Machine,
    _lock_is_stale,
    assert_terminal_states_have_no_outgoing,
    atomic_write_json,
    clear_save_refusal,
    load_strict,
    locked_json,
    save_refused,
)


class StateStoreFoundationTests(unittest.TestCase):
    def test_atomic_write_survives_simulated_crash(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.json"
            path.write_text('{"before": true}\n', encoding="utf-8")
            with patch("plate_core.pr_watch_guards.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"after": True})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"before": True})

    def test_torn_file_raises_not_empty(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            path.write_text('{"items": [1, 2', encoding="utf-8")
            with self.assertRaises(CorruptStateError):
                load_strict(path)
            self.assertTrue(save_refused(path))
            with self.assertRaises(CorruptStateError):
                with locked_json(path, missing_factory=lambda: {"items": []}):
                    pass

    def test_lock_serialises_two_writers(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            errors: list[BaseException] = []
            thread_count = 8
            appends_per_thread = 25

            def append_records(thread_id: int) -> None:
                try:
                    for i in range(appends_per_thread):
                        tag = f"t{thread_id}-{i}"
                        with locked_json(
                            path,
                            missing_factory=lambda: {"records": []},
                        ) as data:
                            rows = data.setdefault("records", [])
                            rows.append(tag)
                except BaseException as exc:
                    errors.append(exc)

            threads = [
                threading.Thread(target=append_records, args=(tid,))
                for tid in range(thread_count)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            loaded = json.loads(path.read_text(encoding="utf-8"))
            expected = {
                f"t{tid}-{i}"
                for tid in range(thread_count)
                for i in range(appends_per_thread)
            }
            self.assertEqual(set(loaded["records"]), expected)
            self.assertEqual(len(loaded["records"]), thread_count * appends_per_thread)

    def test_empty_fresh_lockfile_is_not_stale(self):
        with TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "store.json.lock"
            lock_path.write_text("", encoding="utf-8")
            self.assertFalse(_lock_is_stale(lock_path))

    def test_old_empty_lockfile_is_reclaimed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            lock_path = path.with_suffix(path.suffix + ".lock")
            lock_path.write_text("", encoding="utf-8")
            old = time.time() - 10.0
            os.utime(lock_path, (old, old))
            self.assertTrue(_lock_is_stale(lock_path))
            with locked_json(path, missing_factory=lambda: {"ok": True}) as data:
                data["ok"] = True
            self.assertTrue(path.is_file())
            self.assertFalse(lock_path.exists())

    def test_stale_lock_is_reclaimed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            lock_path = path.with_suffix(path.suffix + ".lock")
            lock_path.write_text("999999\n", encoding="utf-8")
            with locked_json(path, missing_factory=lambda: {"ok": True}) as data:
                data["ok"] = True
            self.assertTrue(path.is_file())
            self.assertFalse(lock_path.exists())

    def test_machine_rejects_unknown_state_and_event(self):
        machine = Machine(
            "demo",
            states=["open", "closed"],
            initial="open",
            terminal=["closed"],
            table=[("open", "finish", "closed")],
        )
        with self.assertRaises(IllegalTransition):
            machine.next("bogus", "finish")
        with self.assertRaises(IllegalTransition):
            machine.next("closed", "finish")

    def test_machine_terminal_has_no_outgoing(self):
        good = Machine(
            "demo",
            states=["open", "closed"],
            initial="open",
            terminal=["closed"],
            table=[("open", "finish", "closed")],
        )
        assert_terminal_states_have_no_outgoing(good)
        bad = Machine(
            "demo",
            states=["open", "closed"],
            initial="open",
            terminal=["closed"],
            table=[("open", "finish", "closed"), ("closed", "reopen", "open")],
        )
        with self.assertRaises(ValueError):
            assert_terminal_states_have_no_outgoing(bad)


class PmQueueCorruptStoreTests(unittest.TestCase):
    def test_torn_pm_queue_raises_instead_of_wipe(self):
        from plate_core.pm import ProjectManager

        with TemporaryDirectory() as tmp:
            qdir = Path(tmp) / ".agentic" / "pm"
            qdir.mkdir(parents=True)
            qpath = qdir / "queue.json"
            qpath.write_text('{"assignments": [{"id": "x"', encoding="utf-8")
            with self.assertRaises(CorruptStateError):
                ProjectManager(state_dir=qdir)
            qpath.write_text(
                '{"updated_at": "t", "assignments": []}\n',
                encoding="utf-8",
            )
            pm = ProjectManager(state_dir=qdir)
            qpath.write_text('{"assignments": [{"id": "x"', encoding="utf-8")
            clear_save_refusal(qpath)
            pm._assignments = [{"id": "keep", "status": "proposed"}]
            with self.assertRaises(CorruptStateError):
                pm._save_queue()
            self.assertIn("[", qpath.read_text(encoding="utf-8"))


class FleetCorruptStoreTests(unittest.TestCase):
    def test_torn_fleet_handoffs_raises_instead_of_wipe(self):
        from plate_core import fleet

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / ".agentic" / "fleet"
            base.mkdir(parents=True)
            store = base / "handoffs.json"
            store.write_text('{"handoffs": [', encoding="utf-8")
            clear_save_refusal(store)
            with self.assertRaises(CorruptStateError):
                fleet._load(base=base)
            with self.assertRaises(CorruptStateError):
                fleet._save({"version": 1, "handoffs": []}, base=base)
            self.assertTrue(store.read_text(encoding="utf-8").startswith('{"handoffs": ['))


class ScheduledOpsCorruptStoreTests(unittest.TestCase):
    def test_torn_scheduled_ops_raises_instead_of_wipe(self):
        from plate_core import scheduled_ops

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / ".agentic" / "scheduled_ops"
            base.mkdir(parents=True)
            store = base / "runs.json"
            store.write_text('{"runs": [', encoding="utf-8")
            clear_save_refusal(store)
            with self.assertRaises(CorruptStateError):
                scheduled_ops._load(base=base)
            with self.assertRaises(CorruptStateError):
                scheduled_ops._save(
                    {"version": 1, "runs": [], "last_run_by_op": {}},
                    base=base,
                )
            self.assertTrue(store.read_text(encoding="utf-8").startswith('{"runs": ['))


if __name__ == "__main__":
    unittest.main()
