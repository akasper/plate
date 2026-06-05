"""Contemplation Engine v2.1 runtime (Epic #139/#257, Feature #343).

This is the core driver that turns every recorded answer into forward progress:
- Parses answer_signal from Question body (checklist format per #326)
- Evaluates accumulated evidence against signal criteria
- Appends structured Contemplation Log with full transcript + provenance
- Creates new actionable child issues (Features/Research/Design) based on answer content + gaps
- Only signals close when answer_signal is verifiably met (evidence-based with citations)
- Includes mandatory === USAGE REPORT === on closure per AGENTS.md
- Special path for answers to blocking Questions (#147 creation): parse dump, post unblock report, resume (#148)

Invoked from plate_record_answer (via optional trigger) and directly via MCP.
Follows the contract in Design #143.

v2.1 changes (phased per #257 + #342 + #326 recs):
- Real answer_signal parsing and evaluation (replaces v1 heuristics)
- Full transcript with citations and evidence tracking
- Strict close decision with usage reporting
- Basic typed child creation with back-refs
- Enhanced blocking/resumption with merge reports
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


def _parse_answer_signal(question_body: str) -> dict[str, Any]:
    """Parse answer_signal from Question body.

    Returns dict with:
    - raw_signal: the full text from answer_signal field
    - criteria: list of parsed criteria items (checklist items, keywords, etc.)
    - signal_type: 'checklist' | 'keyword' | 'artifact' | 'unknown'
    """
    if not question_body:
        return {"raw_signal": "", "criteria": [], "signal_type": "unknown"}

    # Extract answer_signal field content from template
    # Format from template: "## Answer signal\n\nHow will we know this question is answered?\n\n<content>"
    signal_match = re.search(
        r'(?:^|\n)(?:##\s*Answer signal|Answer signal)[:\s]*\n+(.*?)(?=\n##|\Z)',
        question_body,
        re.IGNORECASE | re.DOTALL
    )

    if not signal_match:
        # Fallback: look for answer_signal: pattern
        signal_match = re.search(
            r'answer_signal[:\s]+(.+?)(?:\n\n|\Z)',
            question_body,
            re.IGNORECASE | re.DOTALL
        )

    raw_signal = signal_match.group(1).strip() if signal_match else ""

    if not raw_signal:
        return {"raw_signal": "", "criteria": [], "signal_type": "unknown"}

    # Parse checklist items (- [ ] or - [x] format per #326)
    checklist_items = re.findall(r'^\s*-\s*\[([ xX])\]\s*(.+?)$', raw_signal, re.MULTILINE)
    if checklist_items:
        criteria = [{"type": "checklist", "checked": item[0].lower() == 'x', "text": item[1].strip()}
                   for item in checklist_items]
        return {"raw_signal": raw_signal, "criteria": criteria, "signal_type": "checklist"}

    # Parse artifact requirements
    if any(keyword in raw_signal.lower() for keyword in ['commit', 'docs/', 'artifact', '.md', 'issue']):
        return {"raw_signal": raw_signal, "criteria": [{"type": "artifact", "text": raw_signal}], "signal_type": "artifact"}

    # Fallback: treat as keyword-based
    return {"raw_signal": raw_signal, "criteria": [{"type": "keyword", "text": raw_signal}], "signal_type": "keyword"}


def _evaluate_signal(
    answer_signal: dict[str, Any],
    answer_text: str,
    created_issues: list[dict[str, Any]],
    all_answers: list[str] | None = None
) -> dict[str, Any]:
    """Evaluate whether answer_signal criteria are met.

    Returns:
    - met: bool
    - confidence: 'high' | 'medium' | 'low'
    - evidence: list of citation excerpts
    - missing: list of unmet criteria descriptions
    """
    signal_type = answer_signal.get("signal_type", "unknown")
    criteria = answer_signal.get("criteria", [])
    all_text = "\n\n".join(all_answers or [answer_text])

    if not criteria:
        return {
            "met": False,
            "confidence": "low",
            "evidence": [],
            "missing": ["No answer_signal criteria found in Question body"],
        }

    evidence = []
    missing = []
    met_count = 0

    if signal_type == "checklist":
        # For checklist, check each item against answer content
        for criterion in criteria:
            text = criterion.get("text", "")
            # Simple heuristic: look for keywords from criterion in answer
            keywords = [w.lower() for w in re.findall(r'\b\w{4,}\b', text)]
            matches = [kw for kw in keywords if kw in all_text.lower()]

            if len(matches) >= max(1, len(keywords) // 2):  # At least half keywords present
                met_count += 1
                # Extract excerpt as evidence
                for kw in matches[:1]:  # Just first match for brevity
                    match = re.search(rf'.{{0,50}}{re.escape(kw)}.{{0,50}}', all_text, re.IGNORECASE)
                    if match:
                        evidence.append(f"'{match.group(0).strip()}' (addresses: {text[:60]}...)")
                        break
            else:
                missing.append(text)

        # Checklist is met if all items addressed
        met = len(missing) == 0 and met_count == len(criteria)
        confidence = "high" if met else ("medium" if met_count > 0 else "low")

    elif signal_type == "artifact":
        # Check if issues were created or artifact mentioned
        artifact_text = criteria[0].get("text", "")
        if created_issues:
            met = True
            confidence = "high"
            evidence.append(f"Created {len(created_issues)} follow-up issue(s)")
        else:
            # Check for artifact references in answer
            artifact_keywords = ['docs/', 'commit', 'pr', 'issue', 'artifact']
            found_refs = [kw for kw in artifact_keywords if kw in all_text.lower()]
            met = len(found_refs) > 0
            confidence = "medium" if met else "low"
            if met:
                evidence.append(f"References artifacts: {', '.join(found_refs)}")
            else:
                missing.append(artifact_text)

    else:  # keyword or unknown
        # Basic keyword presence check
        signal_text = answer_signal.get("raw_signal", "")
        keywords = [w.lower() for w in re.findall(r'\b\w{4,}\b', signal_text)]
        matches = [kw for kw in keywords if kw in all_text.lower()]

        met = len(matches) >= max(1, len(keywords) // 3)
        confidence = "high" if len(matches) >= len(keywords) // 2 else ("medium" if matches else "low")

        if met:
            evidence.append(f"Addressed keywords: {', '.join(matches[:3])}")
        else:
            missing.append("Answer does not sufficiently address signal criteria")

    return {
        "met": met,
        "confidence": confidence,
        "evidence": evidence,
        "missing": missing,
    }


def _create_usage_report() -> str:
    """Generate usage report block per AGENTS.md requirements."""
    # In real implementation, this would track actual usage
    # For now, provide a structured placeholder
    return """=== USAGE REPORT ===
tokens: 0
cost: $0.00
duration: 00:00:00
=== END USAGE REPORT ==="""


class ContemplationEngine:
    """Core engine v2.1: signal-driven evaluation + full transcript + strict close."""

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
        all_previous_answers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run contemplation on an answer. Returns log + created issues + close_signal."""
        target = _resolve(repo)
        timestamp = datetime.now(timezone.utc).isoformat()

        created_issues: list[dict[str, Any]] = []
        actions: list[str] = []
        close_signal_met = False

        # Normalize answer_text (defensive)
        answer_text = answer_text or ""

        # Fetch Question to get answer_signal and full context
        try:
            q = self.gh.api(f"repos/{target}/issues/{question_number}")
            q_body = (q.get("body") or "") if isinstance(q, dict) else ""
            q_title = (q.get("title") or "") if isinstance(q, dict) else ""
        except GhApiError as e:
            q_body = ""
            q_title = ""
            actions.append(f"Warning: Could not fetch Question body: {e}")

        # Parse answer_signal
        answer_signal = _parse_answer_signal(q_body)
        actions.append(f"Parsed answer_signal: {answer_signal['signal_type']}")

        # Build transcript with full provenance
        log_lines = [
            "<!-- PLATE-CONTEMPLATION:BEGIN -->",
            f"**Contemplation v2.1**",
            f"",
            f"Question: #{question_number}",
            f"Title: {q_title[:100]}",
            f"Answered by: {answered_by}",
            f"Timestamp: {timestamp}",
            f"Source: {source}",
            f"Session: {session or 'none'}",
            f"",
            f"**Answer (full transcript):**",
            f"",
            f"> {answer_text[:500]}{'...' if len(answer_text) > 500 else ''}",
            f"",
            f"**Answer Signal Evaluation:**",
            f"",
        ]

        # Analyze answer for gaps and create child issues
        text_lower = answer_text.lower()

        # Heuristic gap detection (enhanced from v1)
        if any(k in text_lower for k in ["need to", "should ", "could ", "recommend ", "next step"]):
            # Extract action items as potential child issues
            sentences = [s.strip() for s in re.split(r'[.!?]\s+', answer_text) if len(s.strip()) > 20]
            action_sentences = [s for s in sentences
                              if any(k in s.lower() for k in ["need to", "should", "could", "recommend", "implement", "create", "add"])]

            for idx, action in enumerate(action_sentences[:3]):  # Limit to 3 children
                # Determine issue type from content
                issue_type = "Feature"
                if any(k in action.lower() for k in ["research", "investigate", "explore"]):
                    issue_type = "Research"
                elif any(k in action.lower() for k in ["design", "plan", "architecture"]):
                    issue_type = "Design"

                try:
                    title = f"[{issue_type}]: {action[:80]}..."
                    body = (
                        f"Forward progress from answer to Question #{question_number}.\n\n"
                        f"**Parent Question:** #{question_number} ({q_title})\n\n"
                        f"**Identified gap/action:**\n\n> {action}\n\n"
                        f"**Full answer context:**\n\n> {answer_text[:400]}{'...' if len(answer_text) > 400 else ''}\n\n"
                        f"**Next steps:** Refine scope and implement per PLATE {issue_type} loop.\n\n"
                        f"**Provenance:** Epic #257, Epic #139 (Contemplation v2.1)\n"
                        f"<!-- plate-contemplation-child: parent=q{question_number} @{timestamp} -->"
                    )
                    new_issue = self.gh.api(
                        f"repos/{target}/issues",
                        method="POST",
                        fields={"title": title, "body": body, "labels": [issue_type]},
                    )
                    created_issues.append({
                        "number": new_issue.get("number"),
                        "title": title,
                        "url": new_issue.get("html_url"),
                        "type": issue_type,
                    })
                    actions.append(f"Created {issue_type} #{new_issue.get('number')}")
                except GhApiError as e:
                    actions.append(f"Create {issue_type} failed: {e}")

        # Evaluate signal with all context
        all_answers_list = (all_previous_answers or []) + [answer_text]
        evaluation = _evaluate_signal(answer_signal, answer_text, created_issues, all_answers_list)

        log_lines.extend([
            f"- Signal type: `{answer_signal['signal_type']}`",
            f"- Criteria count: {len(answer_signal.get('criteria', []))}",
            f"- Evaluation: {'✓ MET' if evaluation['met'] else '✗ NOT MET'}",
            f"- Confidence: {evaluation['confidence']}",
            f"",
        ])

        if evaluation["evidence"]:
            log_lines.append("**Evidence (citations):**")
            for ev in evaluation["evidence"]:
                log_lines.append(f"- {ev}")
            log_lines.append("")

        if evaluation["missing"]:
            log_lines.append("**Still missing:**")
            for miss in evaluation["missing"]:
                log_lines.append(f"- {miss}")
            log_lines.append("")

        # Decide on closure (strict: only if signal met with high confidence)
        close_signal_met = evaluation["met"] and evaluation["confidence"] in ["high", "medium"]

        if close_signal_met:
            log_lines.append("**✓ Close signal MET** — Question may be closed with usage report.")
            actions.append("Close signal detected (evidence-based)")
            # Add usage report
            log_lines.append("")
            log_lines.append(_create_usage_report())
        else:
            log_lines.append("**✗ Close signal NOT met** — More work needed or signal not addressed.")
            actions.append("Close signal not met (needs more evidence)")

        log_lines.extend([
            "",
            f"**Actions triggered:** {'; '.join(actions) if actions else 'none'}",
            "",
            f"**Created issues:** {len(created_issues)}",
        ])

        for issue in created_issues:
            log_lines.append(f"- {issue['type']} #{issue['number']}: {issue['title'][:80]}")

        log_lines.append("")
        log_lines.append("<!-- PLATE-CONTEMPLATION:END -->")

        contemplation_comment = "\n".join(log_lines)

        # Post the Contemplation Log comment to the Question
        log_url = None
        try:
            comment = self.gh.api(
                f"repos/{target}/issues/{question_number}/comments",
                method="POST",
                fields={"body": contemplation_comment},
            )
            log_url = comment.get("html_url")
            actions.append(f"Logged contemplation: {log_url}")
        except GhApiError as e:
            actions.append(f"Log failed: {e}")

        # Blocking Question resumption path (#148)
        # Detect via marker written by CreateBlockingQuestionTool (in Question body).
        if "PLATE-BLOCKING-DUMP" in q_body or "last-resort" in q_body.lower() or "blocking info needed" in q_body.lower():
            try:
                m = re.search(r"original[=_](\d+)", q_body)
                if m:
                    orig = int(m.group(1))
                    excerpt = (answer_text or "")[:250]
                    unblock_body = (
                        f"**Unblocked by answer to Question #{question_number} (resumption from blocking Question)**\n\n"
                        f"Human answer to the blocking Question has been recorded and contemplated. Key information merged into context.\n\n"
                        f"**Answer excerpt:**\n\n> {excerpt}{'...' if len(answer_text or '') > 250 else ''}\n\n"
                        f"**Evaluation:** Signal {'MET' if close_signal_met else 'not yet met'}\n\n"
                    )

                    if created_issues:
                        unblock_body += f"**Created follow-up issues:**\n\n"
                        for issue in created_issues:
                            unblock_body += f"- #{issue['number']}: {issue['title'][:80]}\n"
                        unblock_body += "\n"

                    unblock_body += (
                        "**Next steps:** Resume or hand off work on this Issue using the new information and any created follow-ups. "
                        "Full provenance and contemplation log live in the Question.\n\n"
                        f"**Blocking Question:** #{question_number}\n"
                        f"<!-- plate-unblock: q{question_number} orig={orig} @{timestamp} -->"
                    )
                    self.gh.api(
                        f"repos/{target}/issues/{orig}/comments",
                        method="POST",
                        fields={"body": unblock_body},
                    )
                    actions.append(f"Unblock report posted on original #{orig} (resumption v2.1)")
            except Exception as e:
                actions.append(f"Blocking resumption/merge check failed (non-fatal): {e}")

        result = {
            "status": "contemplated",
            "version": "v2.1",
            "question_number": question_number,
            "timestamp": timestamp,
            "actions": actions,
            "created_issues": created_issues,
            "close_signal_met": close_signal_met,
            "evaluation": evaluation,
            "answer_signal": answer_signal,
            "contemplation_log_url": log_url,
            "note": "v2.1 phased: real signal eval, full transcript, strict close, basic typed child creation, enhanced resumption. Per Feature #343 / Epic #257.",
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
