import unittest
from pathlib import Path

from plate_core.label_check_tier import (
    ALLOWED_TIER_LABELS,
    tier_label_validation_error,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TierLabelValidationTests(unittest.TestCase):
    def test_none_tier_labels_passes(self):
        labels = ["Feature", "area:agent", "risk:low"]
        self.assertIsNone(tier_label_validation_error(labels))

    def test_one_tier_label_passes(self):
        labels = ["Bug", "tier:T2", "risk:medium"]
        self.assertIsNone(tier_label_validation_error(labels))

    def test_two_tier_labels_fails(self):
        labels = ["Feature", "tier:T0", "tier:T3"]
        error = tier_label_validation_error(labels)
        self.assertIsNotNone(error)
        self.assertIn("At most one", error)
        self.assertIn("tier:T0", error)
        self.assertIn("tier:T3", error)

    def test_unknown_tier_prefix_fails(self):
        error = tier_label_validation_error(["Question", "tier:T9"])
        self.assertIsNotNone(error)
        self.assertIn("Unsupported tier labels", error)


class TierLabelWorkflowParityTests(unittest.TestCase):
    def test_issue_label_check_repo_matches_payload_and_declares_tiers(self):
        repo_workflow = read_text(".github/workflows/label-check.yml")
        payload_workflow = read_text(
            "src/plate_core/template_payload/.github/workflows/label-check.yml"
        )
        self.assertEqual(repo_workflow, payload_workflow)
        for workflow in (repo_workflow, payload_workflow):
            self.assertIn("allowedTierLabels", workflow)
            for tier in ALLOWED_TIER_LABELS:
                self.assertIn(f"'{tier}'", workflow)

    def test_pr_label_gates_declare_tier_rules(self):
        repo_labels = read_text(".github/workflows/labels.yml")
        payload_ci = read_text(
            "src/plate_core/template_payload/.github/workflows/ci.yml"
        )
        for workflow in (repo_labels, payload_ci):
            self.assertIn("allowedTierLabels", workflow)
            self.assertIn("At most one optional tier label", workflow)


if __name__ == "__main__":
    unittest.main()
