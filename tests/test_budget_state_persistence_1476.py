"""Regression tests for #1476 budget/state persistence and delegation honesty."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plate_core.autonomy import (
    AutonomyEngine,
    get_budget_snapshot,
    load_budget_spend,
    record_budget_spend,
    save_budget_spend,
    tokens_to_usd,
    usd_per_1k_tokens,
)
from plate_core.checkpoint import autonomy_is_paused_by_checkpoints, list_checkpoints
from plate_core.state_store import CorruptStateError, atomic_write_json, mutate_json


class BudgetPersistence1476Tests(unittest.TestCase):
    def test_corrupt_spend_fail_closed_snapshot(self):
        with TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            bdir.mkdir(parents=True)
            path = bdir / "spend.json"
            path.write_text('{"spent_today": 1', encoding="utf-8")
            with self.assertRaises(CorruptStateError):
                load_budget_spend(base_dir=bdir)
            snap = get_budget_snapshot(base_dir=bdir)
            self.assertTrue(snap.get("corrupt_spend"))
            self.assertTrue(snap.get("would_pause_next_cycle"))
            self.assertEqual(snap.get("budget_pressure"), "critical")

    def test_dry_run_does_not_persist_spend(self):
        with TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            engine = AutonomyEngine(repo=None)
            engine.budget_base_dir = bdir
            engine.risk_tolerance = "medium"
            engine.enabled = True
            engine.autonomy_config = {
                "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "warn"}
            }
            engine.run_cycle(dry_run=True, max_steps=2)
            spend_path = bdir / "spend.json"
            self.assertFalse(spend_path.is_file())

    def test_explicit_zero_daily_cap_honored(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.enabled = True
        engine.autonomy_config = {
            "token_budget": {"daily": 0, "per_cycle": 0, "action": "pause"}
        }
        dec = engine.enforce_budget(100, "probe", commit=False)
        self.assertEqual(dec.value, "pause")

    def test_unknown_policy_fails_closed(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.enabled = True
        engine.autonomy_config = {
            "token_budget": {
                "daily": 100,
                "per_cycle": 100,
                "action": "mystery-policy",
            }
        }
        dec = engine.enforce_budget(200, "probe", commit=False)
        self.assertEqual(dec.value, "pause")

    def test_configurable_usd_rate(self):
        rate = usd_per_1k_tokens({"usd_per_1k_tokens": 0.01})
        self.assertAlmostEqual(rate, 0.01)
        self.assertAlmostEqual(tokens_to_usd(1000, rate_per_1k=0.01), 0.01)

    def test_locked_concurrent_budget_spend(self):
        with TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            errors: list[BaseException] = []

            def worker(n: int) -> None:
                try:
                    record_budget_spend(10, base_dir=bdir, reason=f"t{n}")
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            spend = load_budget_spend(base_dir=bdir)
            self.assertEqual(int(spend.get("spent_today") or 0), 120)

    def test_run_cycle_no_synthetic_usage_report(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.enabled = True
        engine.autonomy_config = {
            "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "warn"}
        }
        report = engine.run_cycle(dry_run=False, max_steps=1)
        joined = "\n".join(report.actions_taken)
        self.assertNotIn("=== USAGE REPORT ===", joined)
        self.assertNotIn("cost: $0.00", joined)

    def test_run_cycle_delegation_failure_is_planned(self):
        with TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            today = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).date().isoformat()
            save_budget_spend(
                {
                    "date": today,
                    "spent_today": 0,
                    "spent_this_cycle": 0,
                    "spent_usd_today": 0.0,
                },
                base_dir=bdir,
            )
            engine = AutonomyEngine(repo=None)
            engine.budget_base_dir = bdir
            engine.risk_tolerance = "medium"
            engine.enabled = True
            engine.autonomy_config = {
                "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "warn"}
            }
            with patch(
                "plate_core.baseline_catalog.delegate_to_agent",
                side_effect=TypeError("bad call"),
            ):
                report = engine.run_cycle(dry_run=False, max_steps=1)
        joined = " ".join(report.actions_taken)
        self.assertIn("planned:", joined)
        self.assertNotIn("executed:", joined)


class StateStoreMutateTests(unittest.TestCase):
    def test_mutate_json_serialises_appends(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"

            def add_row(data: dict) -> None:
                data.setdefault("rows", []).append("x")

            mutate_json(path, add_row, missing_factory=lambda: {"rows": []})
            mutate_json(path, add_row)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["rows"], ["x", "x"])


class FleetScheduledOpsConcurrencyTests(unittest.TestCase):
    def test_concurrent_fleet_handoff_appends(self):
        import threading

        from plate_core import fleet

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "fleet"
            errors: list[BaseException] = []
            n_threads = 10

            def worker(i: int) -> None:
                try:
                    fleet.create_handoff(
                        from_agent="orchestrator",
                        to_agent="implementer",
                        task=f"concurrent-handoff-{i}",
                        base_dir=base,
                        record_ledger=False,
                        use_live_budget=False,
                        open_checkpoint=False,
                    )
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            store = fleet._load(base)
            ids = {h.get("handoff_id") for h in store.get("handoffs") or []}
            self.assertEqual(len(ids), n_threads)

    def test_concurrent_scheduled_op_run_appends(self):
        import threading

        from plate_core.scheduled_ops import _load, run_scheduled_op

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "scheduled_ops"
            errors: list[BaseException] = []
            n_threads = 8

            def worker(i: int) -> None:
                try:
                    run_scheduled_op(
                        "scheduled-refactor",
                        dry_run=True,
                        base_dir=base,
                        record_ledger=False,
                        use_live_budget=False,
                    )
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            store = _load(base)
            run_ids = {r.get("id") for r in store.get("runs") or []}
            self.assertEqual(len(run_ids), n_threads)


class CheckpointUnreadableTests(unittest.TestCase):
    def test_unreadable_checkpoint_pauses_autonomy(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "checkpoints"
            base.mkdir(parents=True)
            (base / "cp-broken.json").write_text("{not json", encoding="utf-8")
            open_rows = list_checkpoints(status="pending", base_dir=base)
            self.assertTrue(any(r.get("corrupt") for r in open_rows))
            pause = autonomy_is_paused_by_checkpoints(base_dir=base)
            self.assertTrue(pause.get("paused"))


if __name__ == "__main__":
    unittest.main()