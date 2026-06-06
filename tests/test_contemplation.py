import unittest

from plate_core.contemplation import ContemplationEngine


def _answer_block(answer_text: str, revision_of: str | None = None) -> str:
    lines = [
        "<!-- PLATE-ANSWER:BEGIN -->",
        "Question: 326",
        "Answered by: user",
        "Timestamp: 2026-06-05T12:00:00+00:00",
        "Source: qanda",
    ]
    if revision_of:
        lines.append(f"Revision of: {revision_of}")
    lines.append(f"Answer: {answer_text}")
    lines.append("<!-- PLATE-ANSWER:END -->")
    return "\n".join(lines)


class _FakeGhClient:
    def __init__(self, issue_body: str, comments: list[dict] | None = None):
        self.issue_body = issue_body
        self.comments = comments or []
        self.posted: list[tuple[str, str, dict | None]] = []

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
        if method == "GET" and endpoint.endswith("/issues/326"):
            return {"number": 326, "body": self.issue_body, "title": "Question 326"}
        if method == "GET" and endpoint.endswith("/issues/400"):
            return {"number": 400, "body": self.issue_body, "title": "Question 400"}
        if method == "GET" and endpoint.endswith("/issues/326/comments"):
            return self.comments
        if method == "GET" and endpoint.endswith("/issues/400/comments"):
            return self.comments
        if method == "POST":
            self.posted.append((endpoint, (fields or {}).get("body", ""), fields))
            if endpoint.endswith("/issues"):
                return {"number": 901, "html_url": "https://example.invalid/issues/901"}
            return {"html_url": f"https://example.invalid/comments/{len(self.posted)}"}
        raise AssertionError(f"unexpected API call: {method} {endpoint}")


class ContemplationEngineTests(unittest.TestCase):
    def test_close_signal_requires_checklist_criteria_with_citations(self):
        body = """
## Question
Example

## Answer signal
- [ ] Cite docs/design/contemplation-engine-contract.md as the closure contract.
- [ ] Cite #257 as the parent epic.
"""
        comments = [
            {
                "id": 11,
                "html_url": "https://example.invalid/comments/11",
                "body": _answer_block(
                    "The contract lives in docs/design/contemplation-engine-contract.md and the parent epic is #257."
                ),
            }
        ]
        client = _FakeGhClient(body, comments)

        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text="The contract lives in docs/design/contemplation-engine-contract.md and the parent epic is #257.",
            repo="owner/repo",
            answered_by="user",
        )

        self.assertTrue(result["close_signal_met"])
        self.assertEqual(len(result["answer_signal_evaluation"]), 2)
        self.assertEqual(result["created_issues"], [])
        closure_comments = [body for endpoint, body, _ in client.posted if endpoint.endswith("/issues/326/comments")]
        self.assertEqual(len(closure_comments), 2)
        self.assertIn("=== USAGE REPORT ===", closure_comments[1])
        self.assertIn("ready to close via a PR", closure_comments[1])

    def test_prose_answer_signal_does_not_close_question(self):
        body = """
## Question
Example

## Answer signal
Document a recommendation in docs/research/example.md and link follow-up implementation issues.
"""
        comments = [
            {
                "id": 12,
                "html_url": "https://example.invalid/comments/12",
                "body": _answer_block(
                    "See docs/research/example.md and #123 for the follow-up implementation issue."
                ),
            }
        ]
        client = _FakeGhClient(body, comments)

        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text="See docs/research/example.md and #123 for the follow-up implementation issue.",
            repo="owner/repo",
            answered_by="user",
        )

        self.assertFalse(result["close_signal_met"])
        self.assertEqual(result["answer_signal_evaluation"], [])
        contemplation_log = client.posted[0][1]
        self.assertIn("no parseable checklist criteria", contemplation_log)

    def test_revision_invalidates_previous_citations(self):
        body = """
## Question
Example

## Answer signal
- [ ] Cite docs/research/example.md as the final recommendation artifact.
"""
        comments = [
            {
                "id": 21,
                "html_url": "https://example.invalid/comments/21",
                "body": _answer_block("Recommendation is documented in docs/research/example.md."),
            },
            {
                "id": 22,
                "html_url": "https://example.invalid/comments/22",
                "body": _answer_block(
                    "Revision: the previous citation is obsolete and a replacement artifact is still pending.",
                    revision_of="21",
                ),
            },
        ]
        client = _FakeGhClient(body, comments)

        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text="Revision: the previous citation is obsolete and a replacement artifact is still pending.",
            repo="owner/repo",
            answered_by="user",
        )

        self.assertFalse(result["close_signal_met"])
        self.assertFalse(result["answer_signal_evaluation"][0]["satisfied"])

    def test_blocking_resumption_comment_still_posts(self):
        body = """
## Question
Blocking example

## Answer signal
- [ ] Cite #999 as the original issue to resume.

<!-- PLATE-BLOCKING-DUMP:BEGIN -->
{"original_issue":999}
<!-- PLATE-BLOCKING-DUMP:END -->
"""
        comments = [
            {
                "id": 31,
                "html_url": "https://example.invalid/comments/31",
                "body": _answer_block("Resume work on #999 with the clarified scope."),
            }
        ]
        client = _FakeGhClient(body, comments)

        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text="Resume work on #999 with the clarified scope.",
            repo="owner/repo",
            answered_by="user",
        )

        self.assertTrue(result["close_signal_met"])
        unblock_posts = [endpoint for endpoint, _body, _ in client.posted if endpoint.endswith("/issues/999/comments")]
        self.assertEqual(len(unblock_posts), 1)


if __name__ == "__main__":
    unittest.main()
