"""Tests for canonical ``status:*`` lifecycle (#1385 / #1440)."""

from __future__ import annotations

import unittest

from plate_core.issue_status_lifecycle import (
    ALLOWED_STATUS_LABELS,
    MultipleStatusLabelsError,
    forbidden_planning_labels,
    planning_labels_validation_error,
    promote_unblocked_feature_labels,
    should_apply_status_implemented,
    transition_label_deltas,
    validate_status_label_uniqueness,
)


class ForbiddenPlanningLabelsTests(unittest.TestCase):
    def test_rejects_priority_prefix(self):
        self.assertEqual(forbidden_planning_labels(["Feature", "priority:P1"]), ["priority:P1"])

    def test_rejects_unknown_status_prefix(self):
        self.assertEqual(
            forbidden_planning_labels(["Bug", "status:unknown"]),
            ["status:unknown"],
        )


class StatusUniquenessTests(unittest.TestCase):
    def test_multiple_allowed_status_raises(self):
        with self.assertRaises(MultipleStatusLabelsError):
            validate_status_label_uniqueness(["Feature", "status:stub", "status:blocked"])

    def test_planning_error_message_covers_multi_status(self):
        msg = planning_labels_validation_error(["Feature", "status:blocked", "status:ready-to-work"])
        self.assertIsNotNone(msg)
        self.assertIn("At most one PLATE status label", msg)


class TransitionTableTests(unittest.TestCase):
    def test_mark_ready_replaces_stub(self):
        r, a = transition_label_deltas(["Feature", "status:stub"], "mark_ready")
        self.assertEqual(r, {"status:stub"})
        self.assertEqual(a, {"status:ready-to-work"})

    def test_unblock_removes_all_status_then_ready(self):
        r, a = transition_label_deltas(["Feature", "status:blocked", "area:x"], "unblock")
        self.assertEqual(r, {"status:blocked"})
        self.assertEqual(a, {"status:ready-to-work"})

    def test_integrate_merge_strips_status_and_adds_implemented(self):
        r, a = transition_label_deltas(["Feature", "status:ready-to-work"], "integrate_merge")
        self.assertEqual(r, {"status:ready-to-work"})
        self.assertEqual(a, {"status:implemented"})

    def test_promote_unblocked_matches_unblock_event(self):
        n = promote_unblocked_feature_labels(["Feature", "status:blocked", "need:refinement"])
        self.assertNotIn("status:blocked", n)
        self.assertIn("status:ready-to-work", n)
        self.assertIn("need:refinement", n)


class ImplementationLabelPolicyTests(unittest.TestCase):
    def test_skip_epic_task_release(self):
        self.assertFalse(should_apply_status_implemented(["Epic", "area:x"]))
        self.assertFalse(should_apply_status_implemented(["Task"]))
        self.assertFalse(should_apply_status_implemented(["Release"]))

    def test_feature_gets_implemented(self):
        self.assertTrue(should_apply_status_implemented(["Feature"]))


class AllowedStatusParityTests(unittest.TestCase):
    """Keep workflow ``allowedStatusLabels`` in sync with Python (see label-check test file)."""

    def test_js_array_order_matches_python(self):
        from pathlib import Path

        workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "label-check.yml"
        ).read_text(encoding="utf-8")
        start = workflow.find("const allowedStatusLabels = [")
        self.assertGreater(start, 0)
        end = workflow.find("];", start)
        chunk = workflow[start:end]
        for s in sorted(ALLOWED_STATUS_LABELS):
            self.assertIn(f"'{s}'", chunk)


if __name__ == "__main__":
    unittest.main()
