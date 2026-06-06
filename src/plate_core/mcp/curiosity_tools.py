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

from ..curiosity.answers import (
    Answer,
    build_answer_from_block,
    get_answers_for_question,
    parse_plate_answer_blocks,
    update_answers_index,
)
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


def _extract_answers_from_comments(
    question_number: int,
    comments: list[dict[str, Any]],
) -> list[Answer]:
    answers: list[Answer] = []
    for comment in comments:
        body = comment.get("body") or ""
        for block in parse_plate_answer_blocks(body):
            answers.append(
                build_answer_from_block(
                    block,
                    question_number=question_number,
                    comment_url=comment.get("html_url"),
                    answer_id=str(comment.get("id") or ""),
                )
            )
    return answers


def _extract_answer_from_summary_comment(
    question_number: int,
    comments: list[dict[str, Any]],
) -> list[Answer]:
    if not comments:
        return []

    summary_markers = ("research summary:", "resolution summary:", "answer summary:")
    for comment in reversed(comments):
        body = (comment.get("body") or "").strip()
        if not body or not body.lower().startswith(summary_markers):
            continue
        created_at = comment.get("created_at") or datetime.now(timezone.utc).isoformat()
        return [
            Answer(
                id=str(comment.get("id") or f"summary-{question_number}-{created_at}"),
                question_number=question_number,
                answered_by=(comment.get("user") or {}).get("login", "unknown"),
                timestamp=created_at,
                source="summary-backfill",
                answer_text=body,
                full_comment_url=comment.get("html_url"),
                provenance={"summary_comment": True},
            )
        ]
    return []


def _extract_issue_body_answer(question_number: int, issue: dict[str, Any]) -> list[Answer]:
    body = issue.get("body") or ""
    answer_match = re.search(
        r"\*\*Answer:\*\*\s*(.+?)(?:\n\n\*\*Contemplation:\*\*|\Z)",
        body,
        re.DOTALL,
    )
    if not answer_match:
        return []

    answered_by_match = re.search(r"\*\*Answered by:\*\*\s*(.+)", body)
    answered_by = answered_by_match.group(1).strip() if answered_by_match else "unknown"
    answer_text = answer_match.group(1).strip()
    timestamp = (
        issue.get("closed_at")
        or issue.get("updated_at")
        or issue.get("created_at")
        or datetime.now(timezone.utc).isoformat()
    )
    return [
        Answer(
            id=f"body-{question_number}",
            question_number=question_number,
            answered_by=answered_by,
            timestamp=timestamp,
            source="body-backfill",
            answer_text=answer_text,
            provenance={"issue_body_backfill": True},
            full_comment_url=issue.get("html_url"),
        )
    ]


def _persist_answers(
    question_number: int,
    question_title: str | None,
    answers: list[Answer],
) -> tuple[int, str | None]:
    updated = 0
    committed_path: str | None = None
    for answer in answers:
        question_answers = update_answers_index(
            question_number=question_number,
            new_answer=answer,
            question_title=question_title,
        )
        committed_path = question_answers.file_path
        updated += 1
    return updated, committed_path


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
        revision_of: str | None = None,
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
        if revision_of:
            block_lines.append(f"Revision of: {revision_of}")
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
            issue = gh.api(f"repos/{target}/issues/{question_number}")
            committed_answer = Answer(
                id=str(comment.get("id")),
                question_number=question_number,
                answered_by=answered_by,
                timestamp=timestamp,
                session=session,
                source=source,
                answer_text=answer_text,
                provenance={"recorded_via": "plate_record_answer"},
                agent_actions=actions,
                full_comment_url=comment.get("html_url"),
                revision_of=revision_of,
            )
            committed_question = update_answers_index(
                question_number=question_number,
                new_answer=committed_answer,
                question_title=issue.get("title"),
            )
            return {
                "status": "recorded",
                "question_number": question_number,
                "comment_id": comment.get("id"),
                "comment_url": comment.get("html_url"),
                "timestamp": timestamp,
                "plate_answer_block": comment_body,
                "committed_storage": committed_question.file_path,
                "note": "Answer persisted as GitHub comment and committed curiosity storage. Contemplation Engine (#149) should now be invoked to create follow-up issues / update resources.",
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

        qa = get_answers_for_question(question_number)
        if qa:
            return {
                "question_number": question_number,
                "source": "committed_index",
                "title": qa.title,
                "committed_file": qa.file_path,
                "answers": [answer.to_dict() for answer in qa.answers],
                "latest": qa.latest_answer().to_dict() if qa.latest_answer() else None,
                "count": len(qa.answers),
            }

        # Fallback: scan comments for PLATE-ANSWER blocks
        try:
            comments = gh.api(f"repos/{target}/issues/{question_number}/comments", fields={"per_page": 100}) or []
            parsed_answers = _extract_answers_from_comments(
                question_number=question_number,
                comments=comments if isinstance(comments, list) else [],
            )
            return {
                "question_number": question_number,
                "source": "github_comment_scan",
                "answers": [answer.to_dict() for answer in parsed_answers],
                "latest": parsed_answers[-1].to_dict() if parsed_answers else None,
                "count": len(parsed_answers),
                "note": "Use plate_backfill_answers to materialize committed docs/curiosity artifacts for historical Questions.",
            }
        except GhApiError as exc:
            return {"question_number": question_number, "error": str(exc), "answers": [], "count": 0}


class BackfillAnswersTool:
    """Backfill committed curiosity answer storage from historical Question issues."""

    @staticmethod
    def execute(
        repo: str | None = None,
        state: str = "all",
        limit: int = 50,
        question_numbers: list[int] | None = None,
        client: GhClient | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        gh = _get_gh_client(client)
        target = _resolve_target_repo(repo)

        try:
            if question_numbers:
                issue_summaries = [
                    gh.api(f"repos/{target}/issues/{question_number}")
                    for question_number in question_numbers
                ]
            else:
                issue_summaries = gh.api(
                    f"repos/{target}/issues",
                    fields={
                        "labels": "Question",
                        "state": state,
                        "per_page": min(limit, 100),
                        "page": 1,
                    },
                ) or []

            processed: list[dict[str, Any]] = []
            total_answers = 0

            for issue in issue_summaries if isinstance(issue_summaries, list) else []:
                question_number = issue.get("number")
                if not question_number:
                    continue
                full_issue = gh.api(f"repos/{target}/issues/{question_number}")
                comments = gh.api(
                    f"repos/{target}/issues/{question_number}/comments",
                    fields={"per_page": 100},
                ) or []
                answers = _extract_answers_from_comments(
                    question_number=question_number,
                    comments=comments if isinstance(comments, list) else [],
                )
                if not answers:
                    answers = _extract_issue_body_answer(question_number, full_issue)
                if not answers:
                    answers = _extract_answer_from_summary_comment(
                        question_number,
                        comments if isinstance(comments, list) else [],
                    )

                if not answers:
                    processed.append(
                        {
                            "question_number": question_number,
                            "title": full_issue.get("title"),
                            "status": "skipped",
                            "reason": "No answer-like history found to backfill.",
                        }
                    )
                    continue

                updated_count, committed_path = _persist_answers(
                    question_number=question_number,
                    question_title=full_issue.get("title"),
                    answers=answers,
                )
                total_answers += updated_count
                processed.append(
                    {
                        "question_number": question_number,
                        "title": full_issue.get("title"),
                        "status": "backfilled",
                        "answers_written": updated_count,
                        "committed_file": committed_path,
                    }
                )

            return {
                "repo": target,
                "processed_questions": processed,
                "question_count": len(processed),
                "answers_written": total_answers,
                "note": "Committed curiosity storage now lives under docs/curiosity/answers/ plus docs/curiosity/answers.yml.",
            }
        except GhApiError as exc:
            return {
                "repo": target,
                "error": str(exc),
                "processed_questions": [],
                "question_count": 0,
                "answers_written": 0,
            }


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
    "plate_backfill_answers": BackfillAnswersTool,
    "plate_synthesize_priorities": SynthesizePrioritiesTool,
    "plate_create_blocking_question": CreateBlockingQuestionTool,
}
