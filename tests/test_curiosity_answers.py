"""Tests for the Answer Model (Feature #150)."""

import unittest

from plate_core.curiosity.answers import (
    Answer,
    QuestionAnswers,
    parse_plate_answer_blocks,
    build_answer_from_block,
)


class TestCuriosityAnswers(unittest.TestCase):
    def test_parse_plate_answer_block(self):
        body = '''
Some human text here.

<!-- PLATE-ANSWER:BEGIN -->
Question: What is the purpose?
Answered by: @akasper
Timestamp: 2026-05-30T14:30:00Z
Session: qanda-turn-3
Source: /qanda
Answer: Build a better agentic workflow engine.
Agent actions triggered: Created: #147
<!-- PLATE-ANSWER:END -->
'''
        blocks = parse_plate_answer_blocks(body)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["answered by"], "@akasper")

    def test_build_answer(self):
        block = {
            "question": "What is the purpose?",
            "answered by": "@akasper",
            "timestamp": "2026-05-30T14:30:00Z",
            "answer": "Build a better agentic workflow engine.",
        }
        ans = build_answer_from_block(block, question_number=140)
        self.assertEqual(ans.question_number, 140)
        self.assertEqual(ans.answered_by, "@akasper")
        self.assertIn("better agentic", ans.answer_text)

    def test_question_answers_latest(self):
        qa = QuestionAnswers(question_number=140)
        qa.answers.append(Answer(id="1", question_number=140, answered_by="a", timestamp="2026-01-01"))
        qa.answers.append(Answer(id="2", question_number=140, answered_by="b", timestamp="2026-02-01"))
        latest = qa.latest_answer()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.answered_by, "b")


if __name__ == "__main__":
    unittest.main()
