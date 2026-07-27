import unittest
from unittest.mock import patch

from plate_core.contemplation import (
    ContemplationEngine,
    _detect_artifact_mutation_intents,
    _format_mutation_pr_draft,
    _git_head_sha,
)


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
        logs = [
            b
            for endpoint, b, _ in client.posted
            if endpoint.endswith("/issues/326/comments") and "PLATE-CONTEMPLATION:BEGIN" in b
        ]
        self.assertEqual(len(logs), 1)
        self.assertIn("no parseable checklist criteria", logs[0])

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

    def test_transcript_includes_full_answer_and_question_title(self):
        """Proves: non-destructive transcript keeps full answer + question title (#921)."""
        long_answer = (
            "FULL_ANSWER_MARKER " + ("word " * 80) + " docs/research/example.md #42 end."
        )
        body = """
## Question
Should we document X?

## Answer signal
Document a recommendation without a checklist so follow-up may spawn.
"""
        client = _FakeGhClient(body, comments=[])
        ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text=long_answer,
            repo="owner/repo",
            answered_by="user",
        )
        logs = [
            body
            for endpoint, body, _ in client.posted
            if endpoint.endswith("/issues/326/comments") and "PLATE-CONTEMPLATION:BEGIN" in body
        ]
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertIn("Question title: Question 326", log)
        self.assertIn("Answer full:", log)
        self.assertIn("FULL_ANSWER_MARKER", log)
        self.assertIn(long_answer[-20:], log)
        # Excerpt may truncate; full block must not
        self.assertIn("Answer excerpt:", log)

    def test_typed_research_followup_from_answer_heuristic(self):
        """Proves: incomplete contemplation creates typed Research follow-up (#921)."""
        body = """
## Question
What should we research?

## Answer signal
Document a recommendation without a checklist so follow-up may spawn.
"""
        # Avoid explicit docs/research/ path so #925 mutation intents do not override.
        answer = (
            "We need research into covering risk and unknown tradeoffs before implement. "
            "This answer is long enough to trigger follow-up and says investigate carefully."
        )
        client = _FakeGhClient(body, comments=[])
        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text=answer,
            repo="owner/repo",
            answered_by="user",
        )
        self.assertFalse(result["close_signal_met"])
        self.assertEqual(result.get("mutation_intents") or [], [])
        self.assertEqual(len(result["created_issues"]), 1)
        self.assertEqual(result["created_issues"][0]["type"], "Research")
        create_posts = [
            (endpoint, fields)
            for endpoint, _body, fields in client.posted
            if endpoint.endswith("/issues") and fields
        ]
        self.assertEqual(len(create_posts), 1)
        fields = create_posts[0][1]
        self.assertEqual(fields.get("labels"), ["Research"])
        self.assertIn("[Research]", fields.get("title") or "")
        self.assertIn("**Parent Question:** #326", fields.get("body") or "")

    def test_transcript_includes_git_provenance(self):
        """Proves: contemplation log carries git commit provenance (#923)."""
        body = """
## Question
Example

## Answer signal
- [ ] Cite docs/design/contemplation-engine-contract.md as the closure contract.
"""
        answer = "The contract lives in docs/design/contemplation-engine-contract.md."
        comments = [
            {
                "id": 41,
                "html_url": "https://example.invalid/comments/41",
                "body": _answer_block(answer),
            }
        ]
        client = _FakeGhClient(body, comments)
        with patch("plate_core.contemplation._git_head_sha", return_value="abc1234deadbeef"):
            result = ContemplationEngine(client).contemplate(
                question_number=326,
                answer_text=answer,
                repo="owner/repo",
                session="sess-1",
                answered_by="user",
            )
        self.assertEqual(result.get("git_commit"), "abc1234deadbeef")
        logs = [
            b
            for endpoint, b, _ in client.posted
            if endpoint.endswith("/issues/326/comments") and "PLATE-CONTEMPLATION:BEGIN" in b
        ]
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertIn("Git commit: abc1234deadbeef", log)
        self.assertIn("git_commit: abc1234deadbeef", log)
        self.assertIn("question_id: 326", log)
        self.assertIn("session_id: sess-1", log)

    def test_git_head_sha_unknown_on_failure(self):
        with patch("plate_core.contemplation.subprocess.run", side_effect=OSError("no git")):
            self.assertEqual(_git_head_sha(), "unknown")

    def test_detect_artifact_mutation_intents_high_risk_agents(self):
        """Proves: process-impacting answers yield PR-only mutation intents (#925)."""
        intents = _detect_artifact_mutation_intents(
            "We should update AGENTS.md Question loop and add a skill in .agentic/skills.yml."
        )
        paths = {i["path"] for i in intents}
        self.assertIn("AGENTS.md", paths)
        self.assertIn(".agentic/skills.yml", paths)
        agents = next(i for i in intents if i["path"] == "AGENTS.md")
        self.assertEqual(agents["risk"], "high")
        self.assertTrue(agents["need_human_review"])
        self.assertEqual(agents["mode"], "pr_only")
        skills = next(i for i in intents if i["path"] == ".agentic/skills.yml")
        self.assertEqual(skills["risk"], "low")
        self.assertFalse(skills["need_human_review"])

    def test_mutation_pr_draft_forbids_main_push(self):
        """Proves: mutation plan is PR-only with release base (#925)."""
        draft = _format_mutation_pr_draft(
            question_number=326,
            answer_text="Update AGENTS.md process rules.",
            intents=[
                {
                    "path": "AGENTS.md",
                    "rationale": "Process",
                    "risk": "high",
                    "need_human_review": True,
                    "mode": "pr_only",
                }
            ],
            git_commit="deadbeef",
        )
        self.assertIn("Base:** `release`", draft)
        self.assertIn("Do **not** push directly to `main`", draft)
        self.assertIn("Closes #326", draft)
        self.assertIn("AGENTS.md", draft)
        self.assertIn("need:human-review", draft)
        self.assertIn("deadbeef", draft)

    def test_contemplate_logs_mutation_intents_and_creates_plan_issue(self):
        """Proves: incomplete process answers create mutation plan Feature (#925)."""
        body = """
## Question
How should agents handle process answers?

## Answer signal
Document a recommendation without a checklist so follow-up may spawn.
"""
        answer = (
            "Please update AGENTS.md Question loop and change process for "
            "contemplation so process updates only land via PR. "
            "Also document in docs/research/example.md."
        )
        client = _FakeGhClient(body, comments=[])
        with patch("plate_core.contemplation._git_head_sha", return_value="abc1234"):
            result = ContemplationEngine(client).contemplate(
                question_number=326,
                answer_text=answer,
                repo="owner/repo",
                answered_by="user",
            )
        self.assertFalse(result["close_signal_met"])
        self.assertTrue(result["mutation_intents"])
        self.assertIsNotNone(result.get("mutation_pr_draft"))
        self.assertIn("AGENTS.md", {i["path"] for i in result["mutation_intents"]})
        self.assertEqual(len(result["created_issues"]), 1)
        self.assertTrue(result["created_issues"][0].get("mutation_plan"))
        self.assertEqual(result["created_issues"][0]["type"], "Feature")
        create_posts = [
            fields
            for endpoint, _body, fields in client.posted
            if endpoint.endswith("/issues") and fields
        ]
        self.assertEqual(len(create_posts), 1)
        fields = create_posts[0]
        self.assertIn("Feature", fields.get("labels") or [])
        self.assertIn("need:human-review", fields.get("labels") or [])
        self.assertIn("plate-contemplation-mutation", fields.get("body") or "")
        self.assertIn("Base:** `release`", fields.get("body") or "")
        logs = [
            b
            for endpoint, b, _ in client.posted
            if endpoint.endswith("/issues/326/comments") and "PLATE-CONTEMPLATION:BEGIN" in b
        ]
        self.assertEqual(len(logs), 1)
        self.assertIn("Mutation intent: AGENTS.md", logs[0])
        self.assertIn("Artifact mutation intents:", logs[0])

    def test_typed_followup_when_no_mutation_intents(self):
        """Proves: non-process answers still use typed Research/Feature follow-up (#921/#925)."""
        body = """
## Question
What next?

## Answer signal
No checklist here.
"""
        # Avoid docs/research/ and process keywords so mutation intents stay empty.
        answer = (
            "We should investigate the unknown risk before we implement create add "
            "the feature; this needs research into the tradeoffs carefully now."
        )
        client = _FakeGhClient(body, comments=[])
        result = ContemplationEngine(client).contemplate(
            question_number=326,
            answer_text=answer,
            repo="owner/repo",
            answered_by="user",
        )
        self.assertEqual(result.get("mutation_intents") or [], [])
        self.assertEqual(len(result["created_issues"]), 1)
        self.assertEqual(result["created_issues"][0]["type"], "Research")


if __name__ == "__main__":
    unittest.main()
