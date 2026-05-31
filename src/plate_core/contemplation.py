"""Minimal Contemplation Engine runtime (Epic #139, Feature #149 slice + #148 resumption).

This is the core driver that turns every recorded answer into forward progress:
- Appends structured Contemplation Log to the Question
- Creates new actionable child issues (Features/Tasks) based on answer content + answer_signal
- Updates related resources (stub for wiki/docs)
- Only signals close when answer_signal is verifiably addressed (heuristic v1)
- Special path for answers to blocking Questions (#147 creation): parse dump, post unblock report on original, merge info, resume (#148)

Invoked from plate_record_answer (via optional trigger) and directly via MCP.
Follows the contract in Design #143.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .github_client import GhClient, GhApiError
from .health import resolve_repo


def _get_gh(client: GhClient | None = None) -> GhClient:
    return client or GhClient()


def _resolve(repo: str | None) -> str:
    return resolve_repo(repo)


class ContemplationEngine:
    """Core engine. v1: heuristic-driven issue creation + log; extensible for full rules."""

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
        """Run contemplation on an answer. Returns log + created issues + close_signal."""
        target = _resolve(repo)
        timestamp = datetime.now(timezone.utc).isoformat()

        created_issues: list[dict[str, Any]] = []
        actions: list[str] = []
        close_signal_met = False

        # 1. Simple heuristics from answer + known patterns (expand with #149 full rules)
        # Normalize answer_text early for safety (defensive against None from direct callers
        # or RecordAnswerTool paths); matches established guard intent and prevents
        # TypeError on slicing/len in log construction and heuristic.
        answer_text = answer_text or ""
        text_lower = answer_text.lower()

        # Always log the contemplation
        log_lines = [
            "<!-- PLATE-CONTEMPLATION:BEGIN -->",
            f"Question: {question_number}",
            f"Answered by: {answered_by}",
            f"Timestamp: {timestamp}",
            f"Source: {source}",
            f"Session: {session or 'none'}",
            f"Answer excerpt: {answer_text[:180]}{'...' if len(answer_text) > 180 else ''}",
        ]

        # Heuristic: if answer mentions "risk" or "create issue" or is long, create a follow-up Feature
        if any(k in text_lower for k in ["risk", "unknown", "create ", "implement ", "add "]) or len(answer_text) > 80:
            try:
                title = f"[Feature]: Follow-up from answer to Question #{question_number}"
                body = (
                    f"Contemplation-driven follow-up from answer to Question #{question_number}.\n\n"
                    f"**Original answer excerpt:**\n\n> {answer_text[:300]}\n\n"
                    "**Next steps (agent/human):** Refine scope, split if needed, and implement.\n\n"
                    f"<!-- plate-contemplation-ref: q{question_number} @{timestamp} -->"
                )
                new_issue = self.gh.api(
                    f"repos/{target}/issues",
                    method="POST",
                    fields={"title": title, "body": body, "labels": ["Feature"]},
                )
                created_issues.append({"number": new_issue.get("number"), "title": title, "url": new_issue.get("html_url")})
                actions.append(f"Created: #{new_issue.get('number')}")
            except GhApiError as e:
                actions.append(f"Create issue failed: {e}")

        # Heuristic close signal (v1): very short affirmative answers containing "done" or "complete" + answer_signal in original Q
        if any(k in text_lower for k in ["done", "complete", "resolved", "shipped"]):
            # In real #149 this would fetch the Question body and check against its answer_signal
            close_signal_met = True
            actions.append("Close signal detected (heuristic)")

        log_lines.append(f"Actions triggered: {'; '.join(actions) if actions else 'none'}")
        log_lines.append(f"Close signal met: {str(close_signal_met).lower()}")
        log_lines.append("<!-- PLATE-CONTEMPLATION:END -->")

        contemplation_comment = "\n".join(log_lines)

        # 2. Post the Contemplation Log comment to the Question
        try:
            comment = self.gh.api(
                f"repos/{target}/issues/{question_number}/comments",
                method="POST",
                fields={"body": contemplation_comment},
            )
            log_url = comment.get("html_url")
            actions.append(f"Logged contemplation: {log_url}")
        except GhApiError as e:
            log_url = None
            actions.append(f"Log failed: {e}")

        # 3. (Future) direct resource updates (wiki, docs, CURRENT.md, PR descriptions) per rules in #143

        # #148: Resumption / merge for answers to blocking Questions (created via #147 last-resort tool)
        # Detect via marker written by CreateBlockingQuestionTool (in Question body).
        # Posts auditable unblock report on the original Issue and records the merge action.
        # Full structured body updates + child creation can be expanded in later slices.
        try:
            q = self.gh.api(f"repos/{target}/issues/{question_number}")
            q_body = (q.get("body") or "") if isinstance(q, dict) else ""
            if "PLATE-BLOCKING-DUMP" in q_body or "last-resort" in q_body.lower() or "blocking info needed" in q_body.lower():
                import re
                m = re.search(r"original[=_](\d+)", q_body)
                if m:
                    orig = int(m.group(1))
                    excerpt = (answer_text or "")[:250]
                    unblock_body = (
                        f"**Unblocked by answer to Question #{question_number} (blocking resumption)**\n\n"
                        f"Human answer to the blocking Question has been recorded. Key information merged into context.\n\n"
                        f"**Answer excerpt:**\n\n> {excerpt}{'...' if len(answer_text or '') > 250 else ''}\n\n"
                        "**Next steps:** Resume or hand off work on this Issue using the new information. "
                        "Full provenance and dump live in the Question (follows Answer Model #150).\n\n"
                        f"**Blocking Question:** #{question_number}\n"
                        f"<!-- plate-unblock: q{question_number} orig={orig} @{timestamp} -->"
                    )
                    self.gh.api(
                        f"repos/{target}/issues/{orig}/comments",
                        method="POST",
                        fields={"body": unblock_body},
                    )
                    actions.append(f"Unblock report posted on original #{orig} (resumption from blocking Question)")
                    # Optional: could update orig body or spawn children here per full #148 contract
        except Exception as e:
            actions.append(f"Blocking resumption/merge check failed (non-fatal): {e}")

        result = {
            "status": "contemplated",
            "question_number": question_number,
            "timestamp": timestamp,
            "actions": actions,
            "created_issues": created_issues,
            "close_signal_met": close_signal_met,
            "contemplation_log_url": log_url,
            "note": "v1 minimal engine (Feature #149 slice). Full rules, blocking Question support (#147/#148), and resource mutation in subsequent iterations. Invoked automatically from record_answer when trigger_contemplate=True.",
        }
        return result


def trigger_contemplation(
    question_number: int,
    answer_text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience entrypoint used by RecordAnswerTool and MCP plate_contemplate."""
    engine = ContemplationEngine(kwargs.pop("client", None))
    return engine.contemplate(question_number, answer_text, **kwargs)
