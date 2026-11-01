"""Regression tests for #1164 marketing.yml ai_discoverability block."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETING_PATHS = (
    REPO_ROOT / ".agentic" / "marketing.yml",
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".agentic" / "marketing.yml",
)


class MarketingYmlAiDiscoverability1164Tests(unittest.TestCase):
    def test_repo_and_template_payload_marketing_yml_match(self):
        texts = [p.read_text(encoding="utf-8") for p in MARKETING_PATHS]
        self.assertEqual(texts[0], texts[1])

    def test_claim_review_policy_uses_spec_as_product_truth(self):
        for path in MARKETING_PATHS:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy = data.get("claim_review_policy") or {}
            self.assertEqual(policy.get("source_of_product_truth"), "SPEC.md")

    def test_ai_discoverability_block_shape(self):
        for path in MARKETING_PATHS:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            block = data.get("ai_discoverability")
            self.assertIsInstance(block, dict)
            self.assertIn("enabled", block)
            self.assertIsInstance(block.get("engines"), list)
            self.assertTrue(block.get("prompt_set"))
            run_cap = block.get("run_cap")
            self.assertIsInstance(run_cap, dict)
            self.assertIn("max_runs_per_month", run_cap)
            self.assertIn("max_cost_usd", run_cap)


if __name__ == "__main__":
    unittest.main()
