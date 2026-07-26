"""Tests for design validation contracts (#646)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.design_validation import (
    build_failing_test_scaffold,
    contract_feed_items,
    decide_contract,
    estimate_contract_cost,
    list_contracts,
    propose_contract,
    validate_contract_readiness,
)


class TestDesignContracts(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_propose_defaults_and_scaffold(self):
        r = propose_contract(
            feature_number=99,
            feature_title="Coach pathway UI",
            has_playwright=True,
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(r["ok"])
        self.assertIn("cost_estimate_tokens", r)
        c = r["contract"]
        self.assertEqual(c["status"], "pending_approval")
        self.assertTrue(c["interaction_criteria"])
        self.assertTrue(c["visual_specs"])
        self.assertTrue(c["a11y_criteria"])
        sc = r["test_scaffold"]
        self.assertIn("path_hint", sc)
        self.assertIn("fail", sc["content"].lower())

    def test_approve_and_validate(self):
        r = propose_contract(
            feature_number=1,
            feature_title="X",
            interaction_criteria=["Click save persists"],
            base_dir=self.base,
            use_live_budget=False,
        )
        cid = r["contract"]["id"]
        v0 = validate_contract_readiness(cid, base_dir=self.base)
        self.assertFalse(v0["ready"])
        d = decide_contract(cid, "approve", base_dir=self.base)
        self.assertEqual(d["contract"]["status"], "approved")
        v1 = validate_contract_readiness(cid, base_dir=self.base)
        self.assertTrue(v1["ready"])

    def test_reject_and_feed(self):
        r = propose_contract(
            feature_title="Y", base_dir=self.base, use_live_budget=False
        )
        cid = r["contract"]["id"]
        feed = contract_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        decide_contract(cid, "reject", base_dir=self.base)
        self.assertEqual(list_contracts(status="pending_approval", base_dir=self.base), [])

    def test_ts_scaffold(self):
        r = propose_contract(
            feature_title="UI",
            base_dir=self.base,
            submit_for_approval=False,
            use_live_budget=False,
        )
        sc = build_failing_test_scaffold(r["contract"], language="typescript")
        self.assertTrue(sc["path_hint"].endswith(".ts"))
        self.assertIn("playwright", sc["content"].lower())

    def test_budget_gate(self):
        est = estimate_contract_cost(has_playwright=False)
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        blocked = propose_contract(
            feature_title="Too expensive",
            base_dir=self.base,
            budget_remaining=10,
            use_live_budget=False,
        )
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked.get("blocked"))
        self.assertIn("budget", blocked.get("error") or "")
        ok = propose_contract(
            feature_title="Ok",
            base_dir=self.base,
            budget_remaining=est["estimated_tokens"] + 1000,
            use_live_budget=False,
        )
        self.assertTrue(ok["ok"])
        self.assertEqual(ok.get("budget_remaining"), est["estimated_tokens"] + 1000)

    def test_propose_live_budget_isolates_under_base_dir(self):
        from plate_core.autonomy import load_budget_spend

        root_before = int((load_budget_spend() or {}).get("spent_today") or 0)
        r = propose_contract(
            feature_title="Isolated charge",
            base_dir=self.base,
            use_live_budget=True,
        )
        self.assertTrue(r["ok"], r)
        self.assertIn("budget_charge", r)
        self.assertTrue((r.get("budget_charge") or {}).get("ok"))
        local = load_budget_spend(base_dir=self.base / "budget")
        self.assertGreater(int(local.get("spent_today") or 0), 0)
        self.assertEqual(
            int((load_budget_spend() or {}).get("spent_today") or 0), root_before
        )


if __name__ == "__main__":
    unittest.main()
