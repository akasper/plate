"""Contemplation Engine runtime (Epic #257 evolution of Feature #149 + #148 resumption).

This driver turns recorded Question answers into durable forward progress:
- Appends a structured contemplation log to the Question
- Evaluates checklist-style `Answer signal` criteria against cited answer evidence
- Signals PR-ready closure only when all criteria are satisfied
- Preserves the blocking-question resumption path (#147/#148)

The engine intentionally does *not* close GitHub issues directly. PLATE Question
issues must close via a PR that commits the required artifact and includes
`Closes #N` in the PR body.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from .curiosity.answers import parse_plate_answer_blocks
from .github_client import GhClient, GhApiError
from .health import resolve_repo

_CHECKLIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\[(?: |x|X)\]\s+(.*\S)\s*$")
_ANSWER_SIGNAL_SECTION_RE = re.compile(
    r"(?ims)^##+\s*Answer signal\s*$\n?(.*?)(?=^##+\s|\Z)"
)
_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_PATH_RE = re.compile(
    r"(?:docs|src|tests|scripts|plugin|\.plugin|\.github|\.agentic)/[A-Za-z0-9._/\-]+"
)
_ISSUE_REF_RE = re.compile(r"(?<!\w)#\d+\b")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "must", "when",
    "then", "only", "will", "have", "has", "been", "are", "was", "were", "how",
    "what", "which", "should", "than", "via", "its", "their", "them", "your",
    "into", "each", "item", "cite", "cites", "cited", "criterion", "criteria",
}


def _get_gh(client: GhClient | None = None) -> GhClient:
    return client or GhClient()


def _resolve(repo: str | None) -> str:
    return resolve_repo(repo)


def _extract_answer_signal_section(body: str) -> str:
    match = _ANSWER_SIGNAL_SECTION_RE.search(body or "")
    return match.group(1).strip() if match else ""


def _parse_answer_signal_criteria(body: str) -> tuple[list[str], list[str]]:
    section = _extract_answer_signal_section(body)
    if not section:
        return [], ["Question body does not include an `Answer signal` section."]

    criteria = []
    for line in section.splitlines():
        match = _CHECKLIST_ITEM_RE.match(line)
        if match:
            criteria.append(match.group(1).strip())

    if not criteria:
        return [], [
            "Answer signal contains no parseable checklist criteria; manual closure remains required."
        ]
    return criteria, []


def _extract_citations(text: str) -> list[str]:
    citations = set(_URL_RE.findall(text or ""))
    citations.update(_PATH_RE.findall(text or ""))
    citations.update(_ISSUE_REF_RE.findall(text or ""))
    return sorted(citations)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _build_answer_records(
    question_number: int,
    comments: list[dict[str, Any]],
    answer_text: str,
    answered_by: str,
    source: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    for comment in comments:
        for block in parse_plate_answer_blocks(comment.get("body") or ""):
            answer_value = block.get("answer", "")
            answers.append(
                {
                    "id": str(comment.get("id") or block.get("id") or ""),
                    "question_number": question_number,
                    "answered_by": block.get("answered by", "unknown"),
                    "timestamp": block.get("timestamp", timestamp),
                    "source": block.get("source", "manual"),
                    "answer_text": answer_value,
                    "revision_of": block.get("revision of"),
                    "comment_url": comment.get("html_url"),
                    "citations": _extract_citations(answer_value),
                }
            )

    if answer_text.strip() and not any(
        existing["answer_text"].strip() == answer_text.strip() for existing in answers
    ):
        answers.append(
            {
                "id": f"ephemeral-{question_number}-{timestamp}",
                "question_number": question_number,
                "answered_by": answered_by,
                "timestamp": timestamp,
                "source": source,
                "answer_text": answer_text,
                "revision_of": None,
                "comment_url": None,
                "citations": _extract_citations(answer_text),
            }
        )
    return answers


def _effective_answers(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {str(answer["revision_of"]) for answer in answers if answer.get("revision_of")}
    effective = [answer for answer in answers if str(answer["id"]) not in superseded]
    return sorted(effective, key=lambda answer: answer.get("timestamp", ""))


def _criterion_satisfied(
    criterion: str,
    answers: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    criterion_citations = _extract_citations(criterion)
    criterion_tokens = _tokenize(criterion)
    supporting_answers = []

    for answer in answers:
        if not answer["citations"]:
            continue

        answer_text = answer["answer_text"]
        answer_tokens = _tokenize(answer_text)
        tokens_overlap = criterion_tokens.intersection(answer_tokens)
        required_overlap = 1 if len(criterion_tokens) <= 4 else 2

        path_match = any(citation in answer_text for citation in criterion_citations)
        issue_ref_match = any(citation in answer["citations"] for citation in criterion_citations)
        token_match = len(tokens_overlap) >= required_overlap if criterion_tokens else False

        if path_match or issue_ref_match or token_match:
            supporting_answers.append(
                {
                    "answer_id": answer["id"],
                    "answered_by": answer["answered_by"],
                    "timestamp": answer["timestamp"],
                    "comment_url": answer["comment_url"],
                    "citations": answer["citations"],
                }
            )

    return bool(supporting_answers), supporting_answers


def _classify_followup_issue_type(answer_text: str) -> tuple[str, str]:
    """Heuristic typed child for incomplete contemplation progress (#921).

    Returns (type_label, title_prefix) for Feature | Research | Design.
    """
    lower = (answer_text or "").lower()
    if any(
        t in lower
        for t in (
            "docs/research/",
            "research:",
            "investigate",
            "[research]",
            "needs research",
        )
    ):
        return "Research", "[Research]"
    if any(
        t in lower
        for t in (
            "docs/design/",
            "design:",
            "architecture",
            "[design]",
            "needs design",
        )
    ):
        return "Design", "[Design]"
    return "Feature", "[Feature]"


def _git_head_sha() -> str:
    """Best-effort HEAD SHA for contemplation provenance (#923)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=2,
        )
        if proc.returncode == 0:
            sha = (proc.stdout or "").strip()
            if re.fullmatch(r"[0-9a-f]{7,40}", sha):
                return sha
    except Exception:
        pass
    return "unknown"


def _format_usage_report() -> str:
    return "\n".join(
        [
            "=== USAGE REPORT ===",
            "tokens: 0",
            "cost: $0.00",
            "duration: 00:00:00",
            "=== END USAGE REPORT ===",
        ]
    )


class ContemplationEngine:
    """Deterministic engine for Question answer evaluation and resumption."""

    def __init__(self, client: GhClient | None = None):
        self.gh = client or GhClient()

    def contemplate(
        self,
        question_number: int,
        answer_text: str,
        repo: str | None = None,
        session: str | None = None,
        source: str = "qanda",
        answered_by: str = "agent",
    ) -> dict[str, Any]:
        """Run contemplation on an answer and report closure readiness."""

        target = _resolve(repo)
        timestamp = datetime.now(timezone.utc).isoformat()
        answer_text = answer_text or ""
        actions: list[str] = []
        created_issues: list[dict[str, Any]] = []
        log_url = None
        close_ready_comment_url = None

        issue = self.gh.api(f"repos/{target}/issues/{question_number}")
        comments = self.gh.api(
            f"repos/{target}/issues/{question_number}/comments",
            fields={"per_page": 100},
        ) or []
        comments_list = comments if isinstance(comments, list) else []
        issue_body = (issue.get("body") or "") if isinstance(issue, dict) else ""
        issue_title = (issue.get("title") or "") if isinstance(issue, dict) else ""

        criteria, criterion_warnings = _parse_answer_signal_criteria(issue_body)
        answers = _build_answer_records(
            question_number=question_number,
            comments=comments_list,
            answer_text=answer_text,
            answered_by=answered_by,
            source=source,
            timestamp=timestamp,
        )
        effective_answers = _effective_answers(answers)

        answer_signal_evaluation = []
        close_signal_met = False
        if criteria:
            for criterion in criteria:
                satisfied, supporting_answers = _criterion_satisfied(criterion, effective_answers)
                answer_signal_evaluation.append(
                    {
                        "criterion": criterion,
                        "satisfied": satisfied,
                        "supporting_answers": supporting_answers,
                    }
                )
            close_signal_met = all(item["satisfied"] for item in answer_signal_evaluation)
        else:
            actions.extend(criterion_warnings)

        if (
            not close_signal_met
            and (
                any(keyword in answer_text.lower() for keyword in ["risk", "unknown", "create ", "implement ", "add "])
                or len(answer_text) > 80
            )
        ):
            try:
                type_label, title_prefix = _classify_followup_issue_type(answer_text)
                title = f"{title_prefix}: Follow-up from answer to Question #{question_number}"
                body = (
                    f"Contemplation-driven follow-up from answer to Question #{question_number}.\n\n"
                    f"**Parent Question:** #{question_number}\n\n"
                    f"**Original answer excerpt:**\n\n> {answer_text[:300]}\n\n"
                    "**Next steps (agent/human):** Refine scope, split if needed, and implement.\n\n"
                    f"<!-- plate-contemplation-ref: q{question_number} @{timestamp} -->"
                )
                new_issue = self.gh.api(
                    f"repos/{target}/issues",
                    method="POST",
                    fields={"title": title, "body": body, "labels": [type_label]},
                )
                created_issues.append(
                    {
                        "number": new_issue.get("number"),
                        "title": title,
                        "url": new_issue.get("html_url"),
                        "type": type_label,
                    }
                )
                actions.append(f"Created {type_label}: #{new_issue.get('number')}")
            except GhApiError as exc:
                actions.append(f"Create issue failed: {exc}")

        # Full non-destructive transcript: keep excerpt for scannability + full answer (#921)
        # Git commit + structured provenance fields for Design #142 gap (#923)
        git_commit = _git_head_sha()
        body_excerpt = " ".join((issue_body or "").split())[:200]
        log_lines = [
            "<!-- PLATE-CONTEMPLATION:BEGIN -->",
            f"Question: {question_number}",
            f"Question title: {issue_title or '(none)'}",
            f"Question body excerpt: {body_excerpt or '(empty)'}",
            f"Answered by: {answered_by}",
            f"Timestamp: {timestamp}",
            f"Source: {source}",
            f"Session: {session or 'none'}",
            f"Git commit: {git_commit}",
            "Provenance:",
            f"  question_id: {question_number}",
            f"  session_id: {session or 'none'}",
            f"  author: {answered_by}",
            f"  git_commit: {git_commit}",
            f"  source: {source}",
            f"Answer excerpt: {answer_text[:180]}{'...' if len(answer_text) > 180 else ''}",
            "Answer full:",
            answer_text if answer_text else "(empty)",
            f"Answer signal criteria: {len(criteria)}",
            f"Effective answers considered: {len(effective_answers)}",
        ]
        for warning in criterion_warnings:
            log_lines.append(f"Warning: {warning}")
        for index, evaluation in enumerate(answer_signal_evaluation, start=1):
            status = "satisfied" if evaluation["satisfied"] else "unsatisfied"
            citations = []
            for supporting in evaluation["supporting_answers"]:
                citations.extend(supporting["citations"])
            unique_citations = ", ".join(sorted(dict.fromkeys(citations))) if citations else "none"
            log_lines.append(f"Criterion {index}: {status} - {evaluation['criterion']}")
            log_lines.append(f"Criterion {index} citations: {unique_citations}")
        if close_signal_met:
            actions.append("Answer signal satisfied; Question is ready to close via a PR artifact")
        log_lines.append(f"Actions triggered: {'; '.join(actions) if actions else 'none'}")
        log_lines.append(f"Close signal met: {str(close_signal_met).lower()}")
        log_lines.append("<!-- PLATE-CONTEMPLATION:END -->")
        contemplation_comment = "\n".join(log_lines)

        try:
            log_comment = self.gh.api(
                f"repos/{target}/issues/{question_number}/comments",
                method="POST",
                fields={"body": contemplation_comment},
            )
            log_url = log_comment.get("html_url")
            actions.append(f"Logged contemplation: {log_url}")
        except GhApiError as exc:
            actions.append(f"Log failed: {exc}")

        if close_signal_met:
            closure_lines = [
                "**Answer signal satisfied.**",
                "",
                "This Question is ready to close via a PR that commits the required artifact and includes "
                f"`Closes #{question_number}` in the PR body.",
                "",
                "### Verified criteria",
            ]
            for evaluation in answer_signal_evaluation:
                citations = []
                for supporting in evaluation["supporting_answers"]:
                    citations.extend(supporting["citations"])
                closure_lines.append(
                    f"- [x] {evaluation['criterion']} "
                    f"(citations: {', '.join(sorted(dict.fromkeys(citations))) or 'none'})"
                )
            closure_lines.extend(["", _format_usage_report()])
            try:
                close_comment = self.gh.api(
                    f"repos/{target}/issues/{question_number}/comments",
                    method="POST",
                    fields={"body": "\n".join(closure_lines)},
                )
                close_ready_comment_url = close_comment.get("html_url")
                actions.append("Posted PR-ready closure report with usage block")
            except GhApiError as exc:
                actions.append(f"Closure report failed: {exc}")

        try:
            if (
                "PLATE-BLOCKING-DUMP" in issue_body
                or "last-resort" in issue_body.lower()
                or "blocking info needed" in issue_body.lower()
            ):
                match = re.search(r'original(?:_issue)?["=: ]+(\d+)', issue_body)
                if match:
                    original_issue = int(match.group(1))
                    excerpt = answer_text[:250]
                    unblock_body = (
                        f"**Unblocked by answer to Question #{question_number} (blocking resumption)**\n\n"
                        "Human answer to the blocking Question has been recorded. Key information merged into context.\n\n"
                        f"**Answer excerpt:**\n\n> {excerpt}{'...' if len(answer_text) > 250 else ''}\n\n"
                        "**Next steps:** Resume or hand off work on this Issue using the new information. "
                        "Full provenance and dump live in the Question.\n\n"
                        f"**Blocking Question:** #{question_number}\n"
                        f"<!-- plate-unblock: q{question_number} orig={original_issue} @{timestamp} -->"
                    )
                    self.gh.api(
                        f"repos/{target}/issues/{original_issue}/comments",
                        method="POST",
                        fields={"body": unblock_body},
                    )
                    actions.append(f"Unblock report posted on original #{original_issue} (resumption from blocking Question)")
        except Exception as exc:  # noqa: BLE001 - resumption remains non-fatal
            actions.append(f"Blocking resumption/merge check failed (non-fatal): {exc}")

        return {
            "status": "contemplated",
            "question_number": question_number,
            "timestamp": timestamp,
            "actions": actions,
            "created_issues": created_issues,
            "close_signal_met": close_signal_met,
            "contemplation_log_url": log_url,
            "close_ready_comment_url": close_ready_comment_url,
            "answer_signal_evaluation": answer_signal_evaluation,
            "git_commit": git_commit,
            "note": "Strict checklist-based contemplation engine. Questions become PR-close-ready only when every answer-signal checklist item is backed by cited evidence from effective answers.",
        }


def trigger_contemplation(
    question_number: int,
    answer_text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience entrypoint used by RecordAnswerTool and MCP plate_contemplate."""

    engine = ContemplationEngine(kwargs.pop("client", None))
    return engine.contemplate(question_number, answer_text, **kwargs)
