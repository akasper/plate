"""Tests for costs harvester (Epic #265) and cost+risk dashboard (#653/#634)."""

import unittest
from unittest.mock import Mock, patch

from plate_core.costs import (
    get_cost_dashboard,
    get_cost_report,
    harvest_usage_reports,
    _parse_usage_block,
)


class CostsTests(unittest.TestCase):
    def test_parse_usage_block(self):
        block = """
        tokens: 1234
        cost: $0.45
        duration: 00:12:34
        """
        p = _parse_usage_block(block)
        self.assertEqual(p["tokens"], 1234)
        self.assertEqual(p["cost"], "$0.45")
        self.assertEqual(p["duration"], "00:12:34")

    def test_harvest_mocked(self):
        client = Mock()
        # search returns one issue
        client.api.side_effect = [
            {"items": [{"number": 123, "title": "Test Feature", "labels": [{"name": "Feature"}], "closed_at": "2026-06-01T00:00:00Z"}]},
            [  # comments
                {"body": "=== USAGE REPORT ===\ntokens: 100\ncost: $0.10\nduration: 00:01:00\n=== END USAGE REPORT ===", "html_url": "https://ex.com/c1"},
            ],
        ]
        reps = harvest_usage_reports(repo="akasper/plate", client=client, limit=1)
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0].tokens, 100)
        self.assertEqual(reps[0].issue_number, 123)

    def test_get_cost_report_aggregates(self):
        client = Mock()
        client.api.side_effect = [
            {"items": [
                {"number": 1, "title": "F1", "labels": [{"name": "Feature"}], "closed_at": "2026-06-01"},
                {"number": 2, "title": "F2", "labels": [{"name": "Feature"}], "closed_at": "2026-06-02"},
            ]},
            [  # comments for issue 1
                {"body": "=== USAGE REPORT ===\ntokens: 50\ncost: $0.05\nduration: 00:00:30\n=== END ===", "html_url": "u1"},
            ],
            [  # comments for issue 2
                {"body": "=== USAGE REPORT ===\ntokens: 100\ncost: $0.10\nduration: 00:01:00\n=== END ===", "html_url": "u2"},
            ],
        ]
        rep = get_cost_report(repo="akasper/plate", client=client)
        self.assertEqual(rep.total_tokens, 150)
        self.assertIn("0.15", rep.total_cost)
        self.assertEqual(len(rep.reports), 2)


class CostDashboard653Tests(unittest.TestCase):
    def _client_two_reports(self):
        client = Mock()
        client.api.side_effect = [
            {"items": [
                {"number": 10, "title": "Hot Feature", "labels": [{"name": "Feature"}], "closed_at": "2026-06-01"},
                {"number": 11, "title": "Cool Q", "labels": [{"name": "Question"}], "closed_at": "2026-06-02"},
            ]},
            [{"body": "=== USAGE REPORT ===\ntokens: 5000\ncost: $1.00\nduration: 00:10:00\n=== END ===", "html_url": "u1"}],
            [{"body": "=== USAGE REPORT ===\ntokens: 200\ncost: $0.05\nduration: 00:01:00\n=== END ===", "html_url": "u2"}],
        ]
        return client

    def test_dashboard_budget_risk_feed(self):
        client = self._client_two_reports()
        auto = {
            "enabled": True,
            "risk_tolerance": "medium",
            "budget_remaining_tokens": 25000,
            "budget_remaining_usd": 5.0,
            "burn_rate": 50.0,
            "autopilot_score": 70,
            "open_human_checkpoints": ["cp-1: Approve deploy"],
            "due_procedures": ["cost-rollup"],
            "throttled_actions": 1,
        }
        health = {
            "recommendations": ["Add Goals wiki page"],
            "errors": [],
        }
        dash = get_cost_dashboard(
            repo="akasper/plate",
            client=client,
            autonomy_status=auto,
            health=health,
        )
        self.assertEqual(dash["generated_for"], "cost_risk_dashboard")
        self.assertEqual(dash["cost"]["total_tokens_harvested"], 5200)
        self.assertIn("budget", dash)
        self.assertEqual(dash["budget"]["remaining_tokens"], 25000)
        self.assertTrue(dash["budget"]["enforcement_active"])
        self.assertEqual(dash["risk"]["risk_tolerance"], "medium")
        self.assertEqual(dash["risk"]["autopilot_score"], 70)
        self.assertEqual(dash["projections"]["burn_rate_pct"], 50.0)
        self.assertEqual(dash["projections"]["projected_days_remaining_at_burn"], 1.0)
        self.assertTrue(any(i["type"] == "checkpoint" for i in dash["feed_items"]))
        self.assertTrue(any(i["type"] == "procedure" for i in dash["feed_items"]))
        self.assertTrue(any(i["type"] == "cost_hotspot" for i in dash["feed_items"]))
        self.assertTrue(any(s["kind"] == "health_recommendation" for s in dash["drift_signals"]))
        self.assertIn("Cost + Risk Dashboard", dash["markdown"])
        # burn 50% → elevated budget gate with ask_user_question (#634/#653)
        self.assertEqual(dash["budget"]["budget_pressure"], "elevated")
        gates = [i for i in dash["feed_items"] if i.get("type") == "budget_gate"]
        self.assertTrue(gates)
        self.assertIn("ask_user_question", gates[0])
        self.assertTrue(gates[0]["ask_user_question"]["options"])
        hotspots = [i for i in dash["feed_items"] if i.get("type") == "cost_hotspot"]
        self.assertTrue(hotspots[0].get("ask_user_question"))

    def test_dashboard_autonomy_off_signal(self):
        client = self._client_two_reports()
        dash = get_cost_dashboard(
            repo="akasper/plate",
            client=client,
            autonomy_status={
                "enabled": False,
                "risk_tolerance": "off",
                "budget_remaining_tokens": 50000,
                "burn_rate": 0.0,
                "autopilot_score": 20,
                "open_human_checkpoints": [],
                "due_procedures": [],
            },
            health={},
        )
        self.assertFalse(dash["budget"]["enforcement_active"])
        self.assertTrue(any(s["kind"] == "autonomy_off" for s in dash["drift_signals"]))
        # No budget_gate when autonomy off
        self.assertFalse(any(i.get("type") == "budget_gate" for i in dash["feed_items"]))

    def test_dashboard_high_burn_signal(self):
        client = self._client_two_reports()
        dash = get_cost_dashboard(
            repo="akasper/plate",
            client=client,
            autonomy_status={
                "enabled": True,
                "risk_tolerance": "high",
                "budget_remaining_tokens": 5000,
                "burn_rate": 90.0,
                "autopilot_score": 40,
                "open_human_checkpoints": [],
                "due_procedures": [],
            },
            health={},
        )
        self.assertTrue(any(s["kind"] == "burn_high" for s in dash["drift_signals"]))
        self.assertLess(dash["projections"]["projected_days_remaining_at_burn"], 1.0)
        self.assertIn(dash["budget"]["budget_pressure"], ("critical", "exhausted"))
        self.assertTrue(any(i.get("type") == "budget_gate" for i in dash["feed_items"]))
        self.assertTrue(dash["budget"]["would_throttle_next_cycle"] or dash["budget"]["would_pause_next_cycle"]
                        or dash["budget"]["budget_pressure"] in ("critical", "exhausted"))

    def test_dashboard_durable_spend_and_gate(self):
        """#634: durable spend.json informs remaining when autonomy_status omits it."""
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        client = self._client_two_reports()
        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp)
            (bdir / "spend.json").write_text(
                json.dumps(
                    {
                        "date": "2099-01-01",  # stale day ignored by load? still returns file
                        "spent_today": 48000,
                        "spent_this_cycle": 100,
                        "spent_usd_today": 0.1,
                    }
                ),
                encoding="utf-8",
            )
            # load_budget_spend checks date match — patch it to return our counters
            with patch(
                "plate_core.autonomy.load_budget_spend",
                return_value={
                    "date": "today",
                    "spent_today": 48000,
                    "spent_usd_today": 0.1,
                },
            ):
                dash = get_cost_dashboard(
                    repo="akasper/plate",
                    client=client,
                    autonomy_status={
                        "enabled": True,
                        "risk_tolerance": "medium",
                        # omit remaining → durable fills in
                        "burn_rate": 0.0,
                        "autopilot_score": 50,
                        "open_human_checkpoints": [],
                        "due_procedures": [],
                    },
                    health={},
                )
        self.assertEqual(dash["budget"]["spent_today_durable"], 48000)
        daily = int(dash["budget"]["daily_tokens"])
        self.assertEqual(dash["budget"]["remaining_tokens"], max(0, daily - 48000))
        self.assertIn(dash["budget"]["budget_pressure"], ("critical", "exhausted", "elevated"))
        self.assertTrue(any(i.get("type") == "budget_gate" for i in dash["feed_items"]))


if __name__ == "__main__":
    unittest.main()
