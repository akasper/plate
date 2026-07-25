"""Tests for scheduled autonomous operations (#641)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.scheduled_ops import (
    get_op,
    list_ops,
    list_op_runs,
    plan_op,
    run_procedure_dispatch,
    run_scheduled_op,
    scheduled_ops_status,
)


class TestCatalog(unittest.TestCase):
    def test_ops_present(self):
        ids = {o["id"] for o in list_ops()}
        for need in (
            "scheduled-refactor",
            "release-cut-prep",
            "deploy-production",
            "marketplace-package",
            "implement-epic-slice",
        ):
            self.assertIn(need, ids)
        self.assertIsNotNone(get_op("scheduled-refactor"))


class TestRunGates(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_dry_run_refactor_ok(self):
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "dry-run")
        self.assertTrue(out["packet"]["steps"])

    def test_critical_blocked_without_approve(self):
        out = run_scheduled_op(
            "deploy-production",
            dry_run=True,
            risk_tolerance="high",
            approved=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertFalse(out["ok"])
        self.assertTrue(out["blocked"])

    def test_critical_ok_with_approve(self):
        out = run_scheduled_op(
            "deploy-production",
            dry_run=True,
            risk_tolerance="high",
            approved=True,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(out["ok"])

    def test_plan_and_status(self):
        p = plan_op("release-cut-prep")
        self.assertTrue(p["ok"])
        st = scheduled_ops_status(risk_tolerance="low", base_dir=self.base)
        self.assertGreater(st["n_ops"], 0)
        self.assertTrue(st["gated"])

    def test_dispatch_unknown(self):
        self.assertIsNone(run_procedure_dispatch("not-an-op", base_dir=self.base))
        d = run_procedure_dispatch(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
        )
        self.assertTrue(d["ok"])
        self.assertTrue(list_op_runs(base_dir=self.base))


if __name__ == "__main__":
    unittest.main()
