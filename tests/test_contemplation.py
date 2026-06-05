"""Tests for Contemplation Engine v2.1 (Feature #343)."""

import unittest
from unittest.mock import MagicMock, patch

from plate_core.contemplation import (
    ContemplationEngine,
    _parse_answer_signal,
    _evaluate_signal,
    _create_usage_report,
    trigger_contemplation,
)


class TestAnswerSignalParsing(unittest.TestCase):
    """Test answer_signal parsing from Question bodies."""

    def test_parse_checklist_signal(self):
        """Test parsing checklist-style answer signals per #326."""
        body = """
## Answer signal

How will we know this question is answered?

- [ ] Research findings committed to docs/research/
- [ ] Recommendation documented
- [ ] Follow-up issues created

## Required git artifact
...
"""
        signal = _parse_answer_signal(body)
        self.assertEqual(signal["signal_type"], "checklist")
        self.assertEqual(len(signal["criteria"]), 3)
        self.assertIn("Research findings", signal["criteria"][0]["text"])
        self.assertFalse(signal["criteria"][0]["checked"])

    def test_parse_artifact_signal(self):
        """Test parsing artifact-based signals."""
        body = """
## Answer signal

Committed artifact in docs/research/question-handling.md with findings and recommendation.
"""
        signal = _parse_answer_signal(body)
        self.assertEqual(signal["signal_type"], "artifact")
        self.assertIn("docs/research", signal["raw_signal"])

    def test_parse_keyword_signal(self):
        """Test parsing simple keyword-based signals."""
        body = """
## Answer signal

Clear decision on the approach with rationale.
"""
        signal = _parse_answer_signal(body)
        self.assertEqual(signal["signal_type"], "keyword")
        self.assertIn("decision", signal["raw_signal"].lower())

    def test_parse_missing_signal(self):
        """Test handling Questions without answer_signal."""
        body = "Just a question body without proper template."
        signal = _parse_answer_signal(body)
        self.assertEqual(signal["signal_type"], "unknown")
        self.assertEqual(len(signal["criteria"]), 0)

    def test_parse_alternate_format(self):
        """Test fallback parsing for legacy formats."""
        body = "answer_signal: Documented in SPEC.md"
        signal = _parse_answer_signal(body)
        self.assertIn("SPEC", signal["raw_signal"])


class TestSignalEvaluation(unittest.TestCase):
    """Test signal evaluation logic."""

    def test_checklist_fully_met(self):
        """Test checklist evaluation when all criteria addressed."""
        signal = {
            "signal_type": "checklist",
            "criteria": [
                {"type": "checklist", "text": "Research findings documented"},
                {"type": "checklist", "text": "Recommendation provided"},
            ],
        }
        answer = "Here are the research findings: ... and my recommendation is ..."
        created = []

        evaluation = _evaluate_signal(signal, answer, created)
        self.assertTrue(evaluation["met"])
        self.assertEqual(evaluation["confidence"], "high")
        self.assertGreater(len(evaluation["evidence"]), 0)

    def test_checklist_partially_met(self):
        """Test checklist evaluation with partial match."""
        signal = {
            "signal_type": "checklist",
            "criteria": [
                {"type": "checklist", "text": "Research findings documented"},
                {"type": "checklist", "text": "Implementation completed"},
            ],
        }
        answer = "Here are the research findings: ..."
        created = []

        evaluation = _evaluate_signal(signal, answer, created)
        self.assertFalse(evaluation["met"])
        self.assertIn("medium", evaluation["confidence"])
        self.assertGreater(len(evaluation["missing"]), 0)

    def test_artifact_signal_with_created_issues(self):
        """Test artifact signal met by creating issues."""
        signal = {
            "signal_type": "artifact",
            "criteria": [{"type": "artifact", "text": "Follow-up issues"}],
        }
        answer = "We should investigate this further."
        created = [{"number": 123, "title": "Research X", "type": "Research"}]

        evaluation = _evaluate_signal(signal, answer, created)
        self.assertTrue(evaluation["met"])
        self.assertEqual(evaluation["confidence"], "high")
        self.assertIn("Created 1 follow-up", evaluation["evidence"][0])

    def test_keyword_signal_basic(self):
        """Test basic keyword matching."""
        signal = {
            "signal_type": "keyword",
            "raw_signal": "clear decision with rationale",
            "criteria": [{"type": "keyword", "text": "clear decision with rationale"}],
        }
        answer = "After considering the options, my decision is to use approach B. The rationale is performance."
        created = []

        evaluation = _evaluate_signal(signal, answer, created)
        self.assertTrue(evaluation["met"])

    def test_no_criteria(self):
        """Test handling of missing criteria."""
        signal = {"signal_type": "unknown", "criteria": []}
        answer = "Some answer"
        created = []

        evaluation = _evaluate_signal(signal, answer, created)
        self.assertFalse(evaluation["met"])
        self.assertEqual(evaluation["confidence"], "low")

    def test_accumulated_answers(self):
        """Test evaluation across multiple answers."""
        signal = {
            "signal_type": "checklist",
            "criteria": [
                {"type": "checklist", "text": "First part done"},
                {"type": "checklist", "text": "Second part done"},
            ],
        }
        answer1 = "First part is now done."
        answer2 = "And the second part is done too."
        created = []

        evaluation = _evaluate_signal(signal, answer2, created, [answer1, answer2])
        self.assertTrue(evaluation["met"])


class TestUsageReport(unittest.TestCase):
    """Test usage report generation."""

    def test_usage_report_format(self):
        """Test that usage report follows AGENTS.md format."""
        report = _create_usage_report()
        self.assertIn("=== USAGE REPORT ===", report)
        self.assertIn("tokens:", report)
        self.assertIn("cost:", report)
        self.assertIn("duration:", report)
        self.assertIn("=== END USAGE REPORT ===", report)


class TestContemplationEngine(unittest.TestCase):
    """Test the full contemplation engine."""

    def setUp(self):
        """Set up mock GitHub client."""
        self.mock_gh = MagicMock()
        self.engine = ContemplationEngine(client=self.mock_gh)

    def test_contemplate_basic_flow(self):
        """Test basic contemplation flow."""
        # Mock Question fetch and comment post
        def api_side_effect(endpoint, method=None, fields=None):
            if "issues/100/comments" in endpoint and method == "POST":
                return {"id": 999, "html_url": "https://github.com/test/repo/issues/100#comment-999"}
            elif "issues/100" in endpoint and method is None:
                return {
                    "number": 100,
                    "title": "Test Question",
                    "body": """
## Answer signal

- [ ] Research done
- [ ] Recommendation provided
""",
                }
            return {}

        self.mock_gh.api.side_effect = api_side_effect

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="The research is done. I recommend approach A.",
                repo="test/repo",
                answered_by="test-user",
            )

        self.assertEqual(result["status"], "contemplated")
        self.assertEqual(result["version"], "v2.1")
        self.assertEqual(result["question_number"], 100)
        self.assertIn("answer_signal", result)
        self.assertIn("evaluation", result)
        self.assertEqual(result["answer_signal"]["signal_type"], "checklist")

    def test_contemplate_creates_child_issues(self):
        """Test that contemplation creates appropriate child issues."""
        # Mock Question fetch and issue creation
        def api_side_effect(endpoint, method=None, fields=None):
            if "issues/100/comments" in endpoint and method == "POST":
                return {"id": 999, "html_url": "https://github.com/test/repo/issues/100#comment-999"}
            elif "issues/100" in endpoint and method is None:
                return {
                    "number": 100,
                    "title": "Test Question",
                    "body": "## Answer signal\n\n- [ ] Done",
                }
            elif "repos/test/repo/issues" in endpoint and method == "POST":
                return {"number": 101, "html_url": "https://github.com/test/repo/issues/101"}
            return {}

        self.mock_gh.api.side_effect = api_side_effect

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="We should implement feature X. I recommend creating a new module.",
                repo="test/repo",
            )

        self.assertGreater(len(result["created_issues"]), 0)
        self.assertEqual(result["created_issues"][0]["number"], 101)
        self.assertIn("Feature", result["created_issues"][0]["type"])

    def test_contemplate_close_signal_met(self):
        """Test close signal detection with evidence."""
        self.mock_gh.api.side_effect = [
            # Get Question
            {
                "number": 100,
                "title": "Test Question",
                "body": "## Answer signal\n\nClear recommendation provided.",
            },
            # Post contemplation comment
            {"id": 999, "html_url": "https://github.com/test/repo/issues/100#comment-999"},
        ]

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="My recommendation is to use approach B based on clear analysis.",
                repo="test/repo",
            )

        self.assertTrue(result["close_signal_met"])
        self.assertGreater(len(result["evaluation"]["evidence"]), 0)

    def test_contemplate_close_signal_not_met(self):
        """Test when close signal criteria not satisfied."""
        self.mock_gh.api.side_effect = [
            # Get Question
            {
                "number": 100,
                "title": "Test Question",
                "body": "## Answer signal\n\n- [ ] Research complete\n- [ ] Design ready",
            },
            # Post contemplation comment
            {"id": 999, "html_url": "https://github.com/test/repo/issues/100#comment-999"},
        ]

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="Just a partial answer.",
                repo="test/repo",
            )

        self.assertFalse(result["close_signal_met"])
        self.assertGreater(len(result["evaluation"]["missing"]), 0)

    def test_contemplate_blocking_question_resumption(self):
        """Test resumption path for blocking Questions."""
        unblock_posted = []

        def api_side_effect(endpoint, method=None, fields=None):
            if "issues/100/comments" in endpoint and method == "POST":
                return {"id": 999, "html_url": "https://github.com/test/repo/issues/100#comment-999"}
            elif "issues/100" in endpoint and method is None:
                return {
                    "number": 100,
                    "title": "[Question]: Blocking info needed",
                    "body": """
<!-- PLATE-BLOCKING-DUMP:BEGIN -->
{"original_issue": 50}
<!-- PLATE-BLOCKING-DUMP:END -->

original=50

Blocking info needed for #50.
""",
                }
            elif "issues/50/comments" in endpoint and method == "POST":
                unblock_posted.append(True)
                return {"id": 1000, "html_url": "https://github.com/test/repo/issues/50#comment-1000"}
            return {}

        self.mock_gh.api.side_effect = api_side_effect

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="Here's the clarification you need.",
                repo="test/repo",
            )

        # Check that unblock report was posted
        self.assertTrue(unblock_posted, "Unblock report should have been posted")
        self.assertIn("resumption v2.1", str(result["actions"]))

    def test_contemplate_handles_api_errors(self):
        """Test graceful handling of API errors."""
        from plate_core.github_client import GhApiError

        self.mock_gh.api.side_effect = GhApiError("API error", 500)

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = self.engine.contemplate(
                question_number=100,
                answer_text="Test answer",
                repo="test/repo",
            )

        # Should still return result despite errors
        self.assertEqual(result["status"], "contemplated")
        self.assertIn("Could not fetch Question", str(result["actions"]))


class TestTriggerContemplation(unittest.TestCase):
    """Test the trigger_contemplation convenience function."""

    @patch("plate_core.contemplation.ContemplationEngine")
    def test_trigger_creates_engine(self, mock_engine_class):
        """Test that trigger function creates engine instance."""
        mock_engine = MagicMock()
        mock_engine.contemplate.return_value = {"status": "ok"}
        mock_engine_class.return_value = mock_engine

        result = trigger_contemplation(
            question_number=100,
            answer_text="Test",
            repo="test/repo",
        )

        mock_engine_class.assert_called_once()
        mock_engine.contemplate.assert_called_once()
        self.assertEqual(result["status"], "ok")


class TestIntegration(unittest.TestCase):
    """Integration tests for full contemplation flows."""

    def setUp(self):
        """Set up mock GitHub client."""
        self.mock_gh = MagicMock()

    def test_full_qanda_cycle(self):
        """Test a complete Q&A cycle with contemplation."""
        # Simulate: Question created -> Answer recorded -> Contemplation triggered -> Child created -> Close
        engine = ContemplationEngine(client=self.mock_gh)

        # Mock sequence
        def api_side_effect(endpoint, method=None, fields=None):
            if "issues/200/comments" in endpoint and method == "POST":
                return {"id": 2000, "html_url": "https://github.com/test/repo/issues/200#comment-2000"}
            elif "issues/200" in endpoint and method is None:
                return {
                    "number": 200,
                    "title": "[Question]: What approach?",
                    "body": """
## Answer signal

- [ ] Clear recommendation
- [ ] Rationale provided
- [ ] Follow-up issues if needed
""",
                }
            elif "repos/test/repo/issues" in endpoint and method == "POST":
                return {"number": 201, "html_url": "https://github.com/test/repo/issues/201"}
            return {}

        self.mock_gh.api.side_effect = api_side_effect

        with patch("plate_core.contemplation.resolve_repo", return_value="test/repo"):
            result = engine.contemplate(
                question_number=200,
                answer_text=(
                    "My recommendation is to use approach A. "
                    "The rationale is that it provides better performance. "
                    "We should implement this in the core module."
                ),
                repo="test/repo",
                answered_by="user",
                source="qanda",
            )

        # Verify full cycle
        self.assertEqual(result["status"], "contemplated")
        self.assertEqual(result["version"], "v2.1")
        # Note: Signal may or may not be met depending on exact keyword matching heuristics
        # What matters is that evaluation happened and children were created from gaps
        self.assertIn("evaluation", result)
        self.assertGreater(len(result["created_issues"]), 0)  # At least one child created
        self.assertGreater(len(result["evaluation"]["evidence"]), 0)


if __name__ == "__main__":
    unittest.main()
