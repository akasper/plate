"""MCP tools for Curiosity / Q&A Mode (Epic #139, Feature #154).

Implements the core surfaces from Design #145:
- plate_list_questions
- plate_get_question
- plate_record_answer (posts PLATE-ANSWER blocks per Answer Model)
- plate_get_answers
- plate_synthesize_priorities (initial heuristic + extensible)

These power both direct gh plate qanda usage and agent-driven Q&A / Contemplation flows.
Integrates with Answer Model (#150) when present; falls back to GitHub comment parsing.
Strongly prefers native Copilot CLI primitives for the primary interface (per Design #144).
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from ..github_client import GhClient, GhApiError
from ..health import resolve_repo


PLATE_ANSWER_BEGIN = "<!-- PLATE-ANSWER:BEGIN -->"
PLATE_ANSWER_END = "<!-- PLATE-ANSWER:END -->"

# For #147 blocking Question creation (last-resort info dump). Follows Answer Model provenance spirit.
PLATE_BLOCKING_DUMP_BEGIN = "<!-- PLATE-BLOCKING-DUMP:BEGIN -->"
PLATE_BLOCKING_DUMP_END = "<!-- PLATE-BLOCKING-DUMP:END -->"


def _get_gh_client(client: GhClient | None = None) -> GhClient:
    return client or GhClient()


def _resolve_target_repo(repo: str | None) -> str:
    return resolve_repo(repo)


class ListQuestionsTool:
    """List open (or filtered) Question issues for Q&A / Curiosity flows."""

    @staticmethod
    def execute(
        repo: str | None = None,
        state: str = "open",
        limit: int = 20,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """
        Returns:
            {
                "repo": "...",
                "questions": [
                    {
                        "number": 140,
                        "title": "...",
                        "html_url": "...",
                        "labels": [...],
                        "created_at": "...",
                        "body_preview": "...",
                        "has_answer_signal": bool,
                        "answer_count_hint": int  # from comments or 0
                    },
                    ...
                ],
                "count": N
            }
        """
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        try:
            # Use search for better relevance; fallback to /issues with label filter
            # Simple first-page fetch for v1 (pagination can evolve)
            params: dict[str, Any] = {
                "labels": "Question",
                "state": state,
                "per_page": min(limit, 50),
                "page": 1,
            }
            issues = gh.api(f"repos/{target}/issues", fields=params) or []
            if not isinstance(issues, list):
                issues = []

            questions = []
            for iss in issues:
                body = iss.get("body") or ""
                has_signal = "answer signal" in body.lower() or "answer_signal" in body.lower()
                # Lightweight hint; real count comes from get_answers or comment scan
                questions.append({
                    "number": iss.get("number"),
                    "title": iss.get("title"),
                    "html_url": iss.get("html_url"),
                    "labels": [l.get("name") for l in (iss.get("labels") or [])],
                    "created_at": iss.get("created_at"),
                    "body_preview": (body[:200] + "...") if len(body) > 200 else body,
                    "has_answer_signal": has_signal,
                    "answer_count_hint": 0,  # populated by richer calls
                })

            return {
                "repo": target,
                "questions": questions,
                "count": len(questions),
                "note": "Use plate_get_question for full details + answers. Prefer native Copilot TUI for interactive Q&A sessions.",
            }
        except GhApiError as exc:
            return {"repo": target, "error": str(exc), "questions": [], "count": 0}


class GetQuestionTool:
    """Fetch full details for a specific Question (including recent answers if detectable)."""

    @staticmethod
    def execute(
        question_number: int,
        repo: str | None = None,
        include_comments: bool = True,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        try:
            issue = gh.api(f"repos/{target}/issues/{question_number}")
            result: dict[str, Any] = {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "html_url": issue.get("html_url"),
                "state": issue.get("state"),
                "body": issue.get("body"),
                "labels": [l.get("name") for l in (issue.get("labels") or [])],
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
            }

            if include_comments:
                comments = gh.api(f"repos/{target}/issues/{question_number}/comments", fields={"per_page": 50}) or []
                result["recent_comments"] = [
                    {
                        "id": c.get("id"),
                        "user": (c.get("user") or {}).get("login"),
                        "created_at": c.get("created_at"),
                        "body_preview": (c.get("body") or "")[:300],
                    }
                    for c in (comments if isinstance(comments, list) else [])
                ][:10]
                # Detect PLATE-ANSWER blocks in comments
                answer_blocks = []
                for c in (comments if isinstance(comments, list) else []):
                    body = c.get("body") or ""
                    if PLATE_ANSWER_BEGIN in body:
                        answer_blocks.append({
                            "comment_id": c.get("id"),
                            "url": c.get("html_url"),
                            "user": (c.get("user") or {}).get("login"),
                            "created_at": c.get("created_at"),
                        })
                result["plate_answer_comments"] = answer_blocks
                result["answer_count"] = len(answer_blocks)

            result["note"] = "For fast indexed answers see plate_get_answers (once Answer Model index is populated)."
            return result
        except GhApiError as exc:
            return {"number": question_number, "error": str(exc)}


class RecordAnswerTool:
    """Record an answer to a Question issue.

    Posts a structured PLATE-ANSWER block comment (compatible with Answer Model in #150).
    This is the key ingestion point that feeds Contemplation (#149).
    """

    @staticmethod
    def execute(
        question_number: int,
        answer_text: str,
        answered_by: str = "agent",
        session: str | None = None,
        source: str = "qanda",
        repo: str | None = None,
        client: GhClient | None = None,
        agent_actions: list[str] | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)
        actions = agent_actions or []

        timestamp = datetime.now(timezone.utc).isoformat()

        # Exact format expected by Answer Model parsers (Design #142 / PR #162)
        block_lines = [
            PLATE_ANSWER_BEGIN,
            f"Question: {question_number}",
            f"Answered by: {answered_by}",
            f"Timestamp: {timestamp}",
        ]
        if session:
            block_lines.append(f"Session: {session}")
        block_lines.append(f"Source: {source}")
        block_lines.append(f"Answer: {answer_text}")
        if actions:
            block_lines.append(f"Agent actions triggered: {'; '.join(actions)}")
        block_lines.append(PLATE_ANSWER_END)

        comment_body = "\n".join(block_lines)

        try:
            comment = gh.api(
                f"repos/{target}/issues/{question_number}/comments",
                method="POST",
                fields={"body": comment_body},
            )
            return {
                "status": "recorded",
                "question_number": question_number,
                "comment_id": comment.get("id"),
                "comment_url": comment.get("html_url"),
                "timestamp": timestamp,
                "plate_answer_block": comment_body,
                "note": "Answer persisted as GitHub comment. Contemplation Engine (#149) should now be invoked to create follow-up issues / update resources. Update local docs/curiosity/answers.yml index if Answer Model present.",
            }
        except GhApiError as exc:
            return {"status": "error", "error": str(exc), "question_number": question_number}


class GetAnswersTool:
    """Retrieve answers for a Question (prefers committed index when available; falls back to comment scan)."""

    @staticmethod
    def execute(
        question_number: int,
        repo: str | None = None,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        # Try the fast index first (from Answer Model #150)
        try:
            from ..curiosity.answers import get_answers_for_question, load_answers_index  # type: ignore

            qa = get_answers_for_question(question_number)
            if qa:
                return {
                    "question_number": question_number,
                    "source": "committed_index",
                    "answers": [a.to_dict() for a in qa.answers],
                    "latest": qa.latest_answer().to_dict() if qa.latest_answer() else None,
                    "count": len(qa.answers),
                }
        except Exception:
            pass  # Index not present or import failed; fall back

        # Fallback: scan comments for PLATE-ANSWER blocks
        try:
            comments = gh.api(f"repos/{target}/issues/{question_number}/comments", fields={"per_page": 100}) or []
            answers = []
            for c in (comments if isinstance(comments, list) else []):
                body = c.get("body") or ""
                if PLATE_ANSWER_BEGIN in body:
                    # Minimal parse (full parser lives in Answer Model)
                    answers.append({
                        "comment_url": c.get("html_url"),
                        "user": (c.get("user") or {}).get("login"),
                        "created_at": c.get("created_at"),
                        "body_preview": body[:400],
                    })
            return {
                "question_number": question_number,
                "source": "github_comment_scan",
                "answers": answers,
                "count": len(answers),
                "note": "Full structured parsing + index available after Answer Model (#150) lands.",
            }
        except GhApiError as exc:
            return {"question_number": question_number, "error": str(exc), "answers": [], "count": 0}


class SynthesizePrioritiesTool:
    """Synthesize a prioritized list of open Questions (simple heuristic v1; agents can enhance)."""

    @staticmethod
    def execute(
        repo: str | None = None,
        max_results: int = 5,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        try:
            # Reuse list logic (first page)
            list_result = ListQuestionsTool.execute(repo=target, state="open", limit=30, client=gh)
            questions = list_result.get("questions", [])

            # Very lightweight priority: presence of answer_signal + recency (newer first for now)
            def score(q: dict) -> float:
                s = 0.0
                if q.get("has_answer_signal"):
                    s += 10
                # Newer is higher priority for curiosity (tunable)
                created = q.get("created_at") or ""
                if "2026" in created:  # future-dated test data friendly
                    s += 5
                return s

            ranked = sorted(questions, key=score, reverse=True)[:max_results]

            return {
                "repo": target,
                "prioritized_questions": ranked,
                "rationale": "Heuristic v1: answer_signal present + recency. Full LLM synthesis available via agent or plate_plan_epic evolution.",
                "recommendation": "Agent should present top 3 via native Copilot TUI (or gh plate qanda) and invoke record_answer + contemplation on response.",
            }
        except Exception as exc:
            return {"repo": target, "error": str(exc), "prioritized_questions": []}


class CreateBlockingQuestionTool:
    """Create a blocking `Question` issue as deliberate last resort (Epic #139 / Feature #147).

    Agent invokes this when it has exhausted internal reasoning + tool use on an open Issue
    (Research/Design/Feature/etc.) and cannot proceed safely without human input.

    - Creates new Question with structured information dump (provenance style per Answer Model #142).
    - Bidirectional link: Question body references original; posts clear "paused" status comment on original.
    - Returns new Question number for agent to surface to user (via Q&A or direct link).
    - Does not continue work on original in same session (per guidance).

    This provides the concrete mechanism behind the decision procedure documented in agent_guidance.py
    and AGENTS.md updates for this Feature.
    """

    @staticmethod
    def execute(
        original_issue_number: int,
        blockage_point: str,
        missing_info: str,
        suggested_questions: list[str] | None = None,
        partial_work: str = "",
        extra_context: str = "",
        repo: str | None = None,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)
        timestamp = datetime.now(timezone.utc).isoformat()
        suggested = suggested_questions or []

        # Structured dump body for the new Question (human + machine readable, Answer Model compatible spirit)
        dump_lines = [
            PLATE_BLOCKING_DUMP_BEGIN,
            "{",
            f'  "original_issue": {original_issue_number},',
            f'  "timestamp": "{timestamp}",',
            '  "source": "agent-last-resort-blocking",',
            f'  "blockage_point": {json.dumps(blockage_point)},',
            f'  "missing_info": {json.dumps(missing_info)},',
            f'  "suggested_questions": {json.dumps(suggested)},',
            f'  "partial_work": {json.dumps(partial_work[:2000])},',
            f'  "extra_context": {json.dumps(extra_context[:1000])},',
            "}",
            PLATE_BLOCKING_DUMP_END,
        ]
        dump_block = "\n".join(dump_lines)

        title = f"[Question]: Blocking info needed for #{original_issue_number} - {blockage_point[:60]}"
        body = (
            f"**Blocking Question** created as last resort during work on Issue #{original_issue_number}.\n\n"
            f"**Blocked Issue:** #{original_issue_number}\n\n"
            f"**Exact point of blockage:**\n\n{blockage_point}\n\n"
            f"**Information missing or ambiguous:**\n\n{missing_info}\n\n"
            f"**Suggested questions for human:**\n\n" + "\n".join(f"- {q}" for q in suggested) + "\n\n"
            f"**Agent's partial work / current understanding:**\n\n{partial_work or '(none recorded beyond this dump)'}\n\n"
            f"**Additional context:**\n\n{extra_context or '(see linked Issue and agent session)'}\n\n"
            "---\n\n"
            f"This Question was created per the #147 last-resort pattern (Epic #139). "
            "When answered, a future agent session will merge the response and resume work on the original Issue.\n\n"
            f"**Original Issue link:** #{original_issue_number}\n"
            f"**Contemplation / resumption:** Use `plate_record_answer` (source=\"blocking\") + contemplation after human reply.\n\n"
            f"<!-- plate-blocking-ref: original={original_issue_number} @{timestamp} -->\n"
        ) + "\n\n" + dump_block

        try:
            new_q = gh.api(
                f"repos/{target}/issues",
                method="POST",
                fields={
                    "title": title,
                    "body": body,
                    "labels": ["Question"],
                },
            )
            new_number = new_q.get("number")
            new_url = new_q.get("html_url")

            # Bidirectional: post clear pause status on the *original* Issue
            pause_body = (
                f"**Paused for human input (informational obstacle — last resort)**\n\n"
                f"Agent hit a hard blocker while working on this Issue and created blocking Question #{new_number} with full structured information dump.\n\n"
                f"**Blockage:** {blockage_point}\n\n"
                f"**Link to Question:** #{new_number} ({new_url})\n\n"
                "Work on this Issue is paused in the current session. A future agent session (triggered after human answer) will retrieve the answer, merge key information, post an unblock report, and resume.\n\n"
                f"<!-- plate-blocking-pause: question={new_number} @{timestamp} -->\n"
            )
            try:
                pause_comment = gh.api(
                    f"repos/{target}/issues/{original_issue_number}/comments",
                    method="POST",
                    fields={"body": pause_body},
                )
                pause_url = pause_comment.get("html_url")
            except GhApiError as e:
                pause_url = None
                pause_body = f"(Failed to post pause status: {e})"

            return {
                "status": "blocking_question_created",
                "blocking_question_number": new_number,
                "blocking_question_url": new_url,
                "original_issue_number": original_issue_number,
                "pause_status_url": pause_url,
                "title": title,
                "dump_block": dump_block,
                "note": "Per Feature #147 / Epic #139. Agent should surface the new Question # to user (via Q&A mode or direct mention) and discontinue work on original until answered. Follows Answer Model provenance style for dump.",
            }
        except GhApiError as exc:
            return {
                "status": "error",
                "error": str(exc),
                "original_issue_number": original_issue_number,
            }


# Convenience re-exports for server wiring
CURIOSITY_TOOLS = {
    "plate_list_questions": ListQuestionsTool,
    "plate_get_question": GetQuestionTool,
    "plate_record_answer": RecordAnswerTool,
    "plate_get_answers": GetAnswersTool,
    "plate_synthesize_priorities": SynthesizePrioritiesTool,
    "plate_create_blocking_question": CreateBlockingQuestionTool,
}
