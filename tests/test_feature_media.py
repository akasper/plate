"""Tests for per-Feature media capture + approval (#636)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plate_core.feature_media import (
    attach_to_fragment_file,
    decide_feature_media,
    estimate_feature_media_cost,
    feature_media_feed_items,
    list_feature_media,
    plan_feature_media,
    register_capture,
    skip_feature_media,
    slugify_test_name,
    to_fragment_media_entry,
)


class TestSlug(unittest.TestCase):
    def test_slugify(self):
        s = slugify_test_name("Cool Feature!", 12)
        self.assertTrue(s.replace("-", "").replace("_", "").isalnum())
        self.assertIn("12", s)


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)
        self.repo = Path(self._td.name) / "repo"
        self.repo.mkdir()
        (self.repo / "tests" / "e2e" / "fixtures" / "gifs").mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_plan_register_approve_attach(self):
        p = plan_feature_media(
            feature_number=42,
            feature_title="AI coach pathway",
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(p["ok"])
        rid = p["record"]["id"]
        tname = p["record"]["test_name"]
        gif = self.repo / "tests" / "e2e" / "fixtures" / "gifs" / f"{tname}.gif"
        gif.write_bytes(b"GIF89a-fake")
        reg = register_capture(
            rid,
            gif_path=str(gif),
            size_bytes=gif.stat().st_size,
            base_dir=self.base,
            repo_root=self.repo,
        )
        self.assertTrue(reg["ok"])
        self.assertEqual(reg["record"]["status"], "pending_approval")
        self.assertTrue(reg["file_exists"])

        feed = feature_media_feed_items(base_dir=self.base)
        self.assertTrue(any(x["id"] == rid for x in feed))

        dec = decide_feature_media(rid, "approve", base_dir=self.base)
        self.assertEqual(dec["record"]["status"], "approved")
        entry = to_fragment_media_entry(dec["record"])
        self.assertEqual(entry["approval_status"], "approved")

        frag = self.repo / "frag.json"
        frag.write_text(
            json.dumps(
                {
                    "slug": "ai-coach",
                    "change_type": "feature",
                    "surface": "x",
                    "migration_impact": "m",
                    "agent_notes": "n",
                }
            ),
            encoding="utf-8",
        )
        att = attach_to_fragment_file(rid, frag, base_dir=self.base)
        self.assertTrue(att["ok"])
        data = json.loads(frag.read_text(encoding="utf-8"))
        self.assertTrue(data.get("media"))
        self.assertEqual(list_feature_media(status="attached", base_dir=self.base)[0]["id"], rid)

    def test_skip(self):
        p = plan_feature_media(
            feature_title="X", base_dir=self.base, use_live_budget=False
        )
        rid = p["record"]["id"]
        s = skip_feature_media(rid, base_dir=self.base)
        self.assertEqual(s["record"]["status"], "skipped")


class TestFeatureMediaBudgetGate(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_estimate_cost(self):
        est = estimate_feature_media_cost(phase="plan", quality="medium")
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        high = estimate_feature_media_cost(phase="plan", quality="high")
        self.assertGreater(high["estimated_tokens"], est["estimated_tokens"])
        reg = estimate_feature_media_cost(phase="register")
        self.assertLess(reg["estimated_tokens"], est["estimated_tokens"])

    def test_budget_gate_blocks_plan(self):
        blocked = plan_feature_media(
            feature_title="Blocked media",
            base_dir=self.base,
            budget_remaining=0,
            use_live_budget=False,
        )
        self.assertFalse(blocked.get("ok"))
        self.assertTrue(blocked.get("blocked"))
        self.assertIn("budget", blocked.get("error") or "")
        self.assertEqual(list_feature_media(base_dir=self.base), [])

    def test_budget_gate_allows_when_enough(self):
        ok = plan_feature_media(
            feature_title="Allowed media",
            base_dir=self.base,
            budget_remaining=50_000,
            use_live_budget=False,
        )
        self.assertTrue(ok.get("ok"))
        self.assertIn("cost_estimate_tokens", ok)
        self.assertEqual(ok.get("budget_remaining"), 50_000)
        self.assertNotIn("budget_charge", ok)

    def test_live_plan_charges_durable_spend(self):
        from plate_core.autonomy import load_budget_spend, save_budget_spend
        from unittest.mock import patch

        bdir = self.base / "budget"
        save_budget_spend(
            {
                "date": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .date()
                .isoformat(),
                "spent_today": 0,
                "spent_this_cycle": 0,
                "spent_usd_today": 0.0,
            },
            base_dir=bdir,
        )

        class _Cfg:
            autonomy = {
                "enabled": True,
                "risk_tolerance": "medium",
                "token_budget": {"daily": 100_000, "per_cycle": 50_000, "action": "pause"},
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            ok = plan_feature_media(
                feature_title="Charge me",
                base_dir=self.base,
                use_live_budget=True,
                budget_base_dir=bdir,
            )
        self.assertTrue(ok.get("ok"), ok)
        charge = ok.get("budget_charge") or {}
        self.assertTrue(charge.get("ok"), charge)
        est = int(ok.get("cost_estimate_tokens") or 0)
        self.assertGreater(est, 0)
        data = load_budget_spend(base_dir=bdir)
        self.assertEqual(data.get("spent_today"), est)
        self.assertEqual(data.get("last_action_kind"), "feature_media_plan")

    def test_live_plan_isolates_budget_under_base_dir(self):
        """base_dir alone must hydrate/charge under base_dir/budget (#634)."""
        from plate_core.autonomy import load_budget_spend
        from unittest.mock import patch

        class _Cfg:
            autonomy = {
                "enabled": True,
                "risk_tolerance": "medium",
                "token_budget": {
                    "daily": 100_000,
                    "per_cycle": 50_000,
                    "action": "pause",
                },
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            ok = plan_feature_media(
                feature_title="Isolated media charge",
                base_dir=self.base,
                use_live_budget=True,
                budget_remaining=100_000,
            )
        self.assertTrue(ok.get("ok"), ok)
        charge = ok.get("budget_charge") or {}
        self.assertTrue(charge.get("ok"), charge)
        est = int(ok.get("cost_estimate_tokens") or 0)
        self.assertGreater(est, 0)
        data = load_budget_spend(base_dir=self.base / "budget")
        self.assertEqual(data.get("spent_today"), est)
        self.assertEqual(data.get("last_action_kind"), "feature_media_plan")
        # path should not be the operator default when base_dir is set
        path = str(charge.get("path") or "")
        self.assertIn(str(self.base), path)


if __name__ == "__main__":
    unittest.main()
