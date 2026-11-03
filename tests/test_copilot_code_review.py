"""Tests for Copilot code review effort policy (#1095)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from plate_core.copilot_code_review import (
    PLATE_PREFERRED_REVIEW_EFFORT,
    adoption_check_for_review_effort,
    normalize_review_effort,
    probe_repository_review_effort,
    summarize_copilot_review_effort,
)
from plate_core.github_client import GhApiError


class NormalizeReviewEffortTests(unittest.TestCase):
    def test_lite_aliases(self):
        self.assertEqual(normalize_review_effort("Lite"), "lite")
        self.assertEqual(normalize_review_effort("LOW"), "lite")

    def test_balanced_aliases(self):
        self.assertEqual(normalize_review_effort("Balanced"), "balanced")
        self.assertEqual(normalize_review_effort("Default (Balanced)"), "balanced")

    def test_max_aliases(self):
        self.assertEqual(normalize_review_effort("Max"), "max")


class ProbeRepositoryReviewEffortTests(unittest.TestCase):
    def test_reads_effort_from_first_matching_endpoint(self):
        client = MagicMock()
        client.api.side_effect = [
            GhApiError("404 Not Found"),
            {"review_effort_level": "Lite"},
        ]
        probe = probe_repository_review_effort(client, "owner/repo")
        self.assertEqual(probe["probe_status"], "ok")
        self.assertEqual(probe["effort"], "lite")
        self.assertTrue(probe["preferred_ok"])

    def test_warn_when_not_lite(self):
        client = MagicMock()
        client.api.return_value = {"default_review_effort_level": "balanced"}
        probe = probe_repository_review_effort(client, "owner/repo")
        self.assertEqual(probe["probe_status"], "ok")
        self.assertFalse(probe["preferred_ok"])

    def test_unavailable_when_all_endpoints_missing(self):
        client = MagicMock()
        client.api.side_effect = GhApiError("404 Not Found")
        probe = probe_repository_review_effort(client, "owner/repo")
        self.assertEqual(probe["probe_status"], "unavailable")


class SummarizeCopilotReviewEffortTests(unittest.TestCase):
    def test_manual_when_api_unavailable(self):
        client = MagicMock()
        client.api.side_effect = GhApiError("404 Not Found")
        summary = summarize_copilot_review_effort(client, "owner/repo")
        self.assertEqual(summary["status"], "manual")
        self.assertIn("human verify", summary["next_step"].lower())

    def test_ok_when_lite(self):
        client = MagicMock()
        client.api.return_value = {"review_effort_level": "lite"}
        summary = summarize_copilot_review_effort(client, "owner/repo")
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["effort"], PLATE_PREFERRED_REVIEW_EFFORT)

    def test_warn_when_balanced(self):
        client = MagicMock()
        client.api.return_value = {"review_effort_level": "balanced"}
        summary = summarize_copilot_review_effort(client, "owner/repo")
        self.assertEqual(summary["status"], "warn")
        self.assertIn("Lite", summary["next_step"] or "")

    def test_adoption_check_ok_for_lite(self):
        row = adoption_check_for_review_effort(
            {"status": "ok", "effort": "lite", "next_step": None}
        )
        self.assertTrue(row["ok"])
        self.assertEqual(row["id"], "copilot_review_effort_lite")

    def test_adoption_check_manual_not_ok(self):
        row = adoption_check_for_review_effort(
            {
                "status": "manual",
                "effort": None,
                "next_step": "verify manually",
            }
        )
        self.assertFalse(row["ok"])
        self.assertIn("manual", row["detail"])


class HealthIntegrationTests(unittest.TestCase):
    def test_health_includes_copilot_review_effort_fields(self):
        from plate_core.health import get_health

        fake = {
            "status": "manual",
            "effort": None,
            "next_step": "verify Lite in settings",
        }
        client = MagicMock()

        class FakeClient:
            def api(self, endpoint, method="GET", fields=None):
                return client.api(endpoint, method=method, fields=fields)

        with unittest.mock.patch(
            "plate_core.copilot_code_review.summarize_copilot_review_effort",
            return_value=fake,
        ):
            report = get_health(
                repo="akasper/plate",
                client=FakeClient(),
                include_spec_audit=False,
            )
        self.assertEqual(report.copilot_review_effort_status, "manual")
        self.assertEqual(report.copilot_review_effort_next_step, "verify Lite in settings")
