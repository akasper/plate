"""Tests for costs harvester (Epic #265)."""

import unittest
from unittest.mock import Mock

from plate_core.costs import get_cost_report, harvest_usage_reports, _parse_usage_block


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


if __name__ == "__main__":
    unittest.main()
