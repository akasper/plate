"""Tests for the committed Curiosity Answer Model."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.curiosity.answers import (
    Answer,
    QuestionAnswers,
    build_answer_from_block,
    get_answers_for_question,
    parse_plate_answer_blocks,
    update_answers_index,
)
from plate_core.mcp.curiosity_tools import BackfillAnswersTool


class TestCuriosityAnswers(unittest.TestCase):
    def test_parse_plate_answer_block(self):
        body = """
Some human text here.

<!-- PLATE-ANSWER:BEGIN -->
Question: What is the purpose?
Answered by: @akasper
Timestamp: 2026-05-30T14:30:00Z
Session: qanda-turn-3
Source: /qanda
Revision of: 12345
Answer: Build a better agentic workflow engine.
Agent actions triggered: Created: #147
<!-- PLATE-ANSWER:END -->
"""
        blocks = parse_plate_answer_blocks(body)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["answered by"], "@akasper")
        self.assertEqual(blocks[0]["revision of"], "12345")

    def test_build_answer(self):
        block = {
            "question": "What is the purpose?",
            "answered by": "@akasper",
            "timestamp": "2026-05-30T14:30:00Z",
            "revision of": "99",
            "answer": "Build a better agentic workflow engine.",
        }
        answer = build_answer_from_block(
            block,
            question_number=140,
            comment_url="https://example.invalid/comment",
            answer_id="123",
        )
        self.assertEqual(answer.question_number, 140)
        self.assertEqual(answer.answered_by, "@akasper")
        self.assertEqual(answer.revision_of, "99")
        self.assertEqual(answer.id, "123")
        self.assertIn("better agentic", answer.answer_text)

    def test_question_answers_latest_ignores_superseded_answers(self):
        question_answers = QuestionAnswers(question_number=140)
        question_answers.answers.append(
            Answer(
                id="1",
                question_number=140,
                answered_by="a",
                timestamp="2026-01-01T00:00:00+00:00",
                answer_text="Initial answer",
            )
        )
        question_answers.answers.append(
            Answer(
                id="2",
                question_number=140,
                answered_by="b",
                timestamp="2026-02-01T00:00:00+00:00",
                answer_text="Revised answer",
                revision_of="1",
            )
        )
        latest = question_answers.latest_answer()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.id, "2")

    def test_update_answers_index_writes_index_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index_path = root / "docs" / "curiosity" / "answers.yml"
            answers_dir = root / "docs" / "curiosity" / "answers"

            first_answer = Answer(
                id="101",
                question_number=275,
                answered_by="user",
                timestamp="2026-06-03T01:50:06+00:00",
                source="cli-interactive",
                answer_text="Native host widgets are preferred if exposed.",
                full_comment_url="https://example.invalid/275/comments/101",
            )
            revised_answer = Answer(
                id="102",
                question_number=275,
                answered_by="user",
                timestamp="2026-06-03T02:10:00+00:00",
                source="cli-interactive",
                answer_text="Fallback may require a PLATE-owned TUI.",
                full_comment_url="https://example.invalid/275/comments/102",
                revision_of="101",
            )

            update_answers_index(
                question_number=275,
                new_answer=first_answer,
                question_title="Host-agent integration / UX surface",
                index_path=index_path,
                answers_dir=answers_dir,
            )
            question_answers = update_answers_index(
                question_number=275,
                new_answer=revised_answer,
                question_title="Host-agent integration / UX surface",
                index_path=index_path,
                answers_dir=answers_dir,
            )

            self.assertEqual(question_answers.file_path, "docs/curiosity/answers/host-agent-integration-ux-surface.md")
            reloaded = get_answers_for_question(275, index_path=index_path)
            self.assertIsNotNone(reloaded)
            self.assertEqual(len(reloaded.answers), 2)
            self.assertEqual(reloaded.latest_answer().id, "102")

            markdown_path = root / question_answers.file_path
            self.assertTrue(markdown_path.exists())
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Answers for Question #275", markdown)
            self.assertIn("Fallback may require a PLATE-owned TUI.", markdown)
            self.assertIn("Revision of:** 101", markdown)

    def test_update_answers_index_is_idempotent_for_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index_path = root / "docs" / "curiosity" / "answers.yml"
            answers_dir = root / "docs" / "curiosity" / "answers"

            answer = Answer(
                id="same-id",
                question_number=276,
                answered_by="user",
                timestamp="2026-06-03T01:42:40+00:00",
                answer_text="PLATE-only repos by default.",
            )

            update_answers_index(
                question_number=276,
                new_answer=answer,
                question_title="Repo scope policy",
                index_path=index_path,
                answers_dir=answers_dir,
            )
            reloaded = update_answers_index(
                question_number=276,
                new_answer=answer,
                question_title="Repo scope policy",
                index_path=index_path,
                answers_dir=answers_dir,
            )

            self.assertEqual(len(reloaded.answers), 1)

    @patch("plate_core.mcp.curiosity_tools.update_answers_index")
    def test_backfill_answers_uses_summary_comment_when_no_structured_answer_exists(self, mock_update):
        class FakeGhClient:
            def api(self, endpoint, method="GET", fields=None):
                if endpoint == "repos/akasper/plate/issues":
                    return [
                        {
                            "number": 319,
                            "title": "Standing release-track lifecycle",
                        }
                    ]
                if endpoint == "repos/akasper/plate/issues/319":
                    return {
                        "number": 319,
                        "title": "Standing release-track lifecycle",
                        "body": "## Information goal\nDetermine canonical release state.",
                        "html_url": "https://github.com/akasper/plate/issues/319",
                    }
                if endpoint == "repos/akasper/plate/issues/319/comments":
                    return [
                        {
                            "id": 9001,
                            "body": "Research summary:\n\n- One standing `Next Release` issue.",
                            "created_at": "2026-06-04T00:48:25Z",
                            "html_url": "https://github.com/akasper/plate/issues/319#issuecomment-1",
                            "user": {"login": "akasper"},
                        }
                    ]
                raise AssertionError(f"unexpected endpoint: {endpoint}")

        mock_update.return_value = QuestionAnswers(
            question_number=319,
            title="Standing release-track lifecycle",
            file_path="docs/curiosity/answers/standing-release-track-lifecycle.md",
            answers=[],
        )

        result = BackfillAnswersTool.execute(
            repo="akasper/plate",
            client=FakeGhClient(),
        )

        self.assertEqual(result["answers_written"], 1)
        self.assertEqual(result["processed_questions"][0]["status"], "backfilled")
        written_answer = mock_update.call_args.kwargs["new_answer"]
        self.assertEqual(written_answer.source, "summary-backfill")
        self.assertIn("Research summary", written_answer.answer_text)


if __name__ == "__main__":
    unittest.main()
