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


# Process artifacts that must mutate only via PR (Design #143 §2 / research §3.3).
# High-risk paths require need:human-review before merge (#925).
_HIGH_RISK_ARTIFACT_PREFIXES = (
    "AGENTS.md",
    "SPEC.md",
    ".github/workflows/",
    ".plate",
)

_ARTIFACT_MUTATION_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("agents.md", "update agents", "agent rules", "question loop"),
        "AGENTS.md",
        "Process / agent operating rules",
    ),
    (
        ("spec.md", "update spec", "product intent", "spec update"),
        "SPEC.md",
        "Product intent / architecture",
    ),
    (
        ("skills.yml", ".agentic/skills", "add skill", "catalog skill"),
        ".agentic/skills.yml",
        "Agent catalog / skills",
    ),
    (
        ("current.md", "update current"),
        "CURRENT.md",
        "Current capability index",
    ),
    (
        ("docs/wiki/", "wiki source", "wiki page"),
        "docs/wiki/",
        "Wiki source material",
    ),
    (
        ("docs/research/", "research findings", "research note"),
        "docs/research/",
        "Research findings commit",
    ),
    (
        ("docs/design/", "design artifact", "design note"),
        "docs/design/",
        "Design artifact commit",
    ),
    (
        (
            ".agentic/releases/unreleased",
            "release fragment",
            "unreleased fragment",
            "fragment under",
        ),
        ".agentic/releases/unreleased/",
        "Release-note fragment",
    ),
    (
        (".github/workflows", "workflow file", "ci workflow"),
        ".github/workflows/",
        "CI / workflow definitions",
    ),
    (
        ("change process", "process update", "update process", "process rule"),
        "AGENTS.md",
        "Generic process change (default AGENTS.md)",
    ),
)


def _is_high_risk_artifact(path: str) -> bool:
    p = path or ""
    return any(p == pref or p.startswith(pref) for pref in _HIGH_RISK_ARTIFACT_PREFIXES)


def _detect_artifact_mutation_intents(answer_text: str) -> list[dict[str, Any]]:
    """Detect process-impacting answers that require PR-only artifact mutation (#925).

    Returns structured intents (no git push, no PR API). Full auto PR creation is
    deferred; agents execute the draft plan on a feature branch targeting release.
    """
    lower = (answer_text or "").lower()
    if not lower.strip():
        return []

    intents: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for keywords, path, rationale in _ARTIFACT_MUTATION_RULES:
        if not any(k in lower for k in keywords):
            continue
        if path in seen_paths:
            continue
        seen_paths.add(path)
        high_risk = _is_high_risk_artifact(path)
        intents.append(
            {
                "path": path,
                "rationale": rationale,
                "risk": "high" if high_risk else "low",
                "need_human_review": high_risk,
                "mode": "pr_only",
            }
        )
    return intents


def _format_mutation_pr_draft(
    question_number: int,
    answer_text: str,
    intents: list[dict[str, Any]],
    git_commit: str,
) -> str:
    """Human/agent-executable PR body for process artifact mutations (never main push)."""
    lines = [
        f"## Contemplation artifact mutation plan (from Question #{question_number})",
        "",
        "Process-impacting answer requires **PR-only** artifact updates "
        "(Design #143 §2). Do **not** push directly to `main`.",
        "",
        "### Suggested PR metadata",
        "- **Base:** `release` (legacy integration; confirm with `gh plate release status`)",
        "- **Branch:** `docs/contemplation-q{n}-artifact-mutation` "
        f"(replace with short slug; q={question_number})",
        "- **Labels:** `Documentation` (+ `Feature` only if process surface changes code)",
        f"- **Body must include:** `Closes #{question_number}` when this PR is the closure path",
        f"- **Provenance git commit at contemplate time:** `{git_commit}`",
        "",
        "### Mutation intents",
    ]
    for intent in intents:
        risk = intent.get("risk", "low")
        path = intent.get("path", "?")
        rationale = intent.get("rationale", "")
        human = " **need:human-review**" if intent.get("need_human_review") else ""
        lines.append(f"- `{path}` ({risk}){human} — {rationale}")
    lines.extend(
        [
            "",
            "### Original answer excerpt",
            "",
            f"> {(answer_text or '')[:500]}",
            "",
            "### Agent checklist",
            "1. Branch from latest `origin/release`.",
            "2. Apply minimal edits only to listed paths (plus fragment if process surface).",
            "3. Open PR to `release` with clean human title; put closing keywords in body only.",
            "4. Babysit to green; high-risk paths wait for human review.",
            "",
            f"<!-- plate-contemplation-mutation-plan: q{question_number} -->",
        ]
    )
    return "\n".join(lines)


def build_mutation_pr_plan(
    question_number: int,
    answer_text: str,
    intents: list[dict[str, Any]],
    git_commit: str,
    *,
    base: str = "release",
) -> dict[str, Any]:
    """Structured executable plan for PR-only process mutations (#929).

    Pure helper: no git, no network. Agents (or apply_mutation_pr_plan) execute later.
    Default base is legacy ``release`` (confirm with ``gh plate release status``).
    """
    if not intents:
        return {
            "ok": False,
            "error": "no_mutation_intents",
            "question_number": question_number,
        }

    paths = [str(i.get("path") or "") for i in intents if i.get("path")]
    high_risk = any(i.get("need_human_review") for i in intents)
    branch = f"docs/contemplation-q{question_number}-artifact-mutation"
    title = f"Apply contemplation process updates for Question #{question_number}"
    body = _format_mutation_pr_draft(
        question_number=question_number,
        answer_text=answer_text,
        intents=intents,
        git_commit=git_commit,
    )
    labels = ["Documentation"]
    if high_risk:
        labels.append("need:human-review")
    labels_csv = ",".join(labels)

    git_steps = [
        f"git fetch origin {base}",
        f"git checkout -b {branch} origin/{base}",
        "apply minimal edits to: " + ", ".join(paths),
        "git add -- " + " ".join(paths),
        f'git commit -m "Apply contemplation process updates for #{question_number}"',
        f"git push -u origin {branch}",
    ]
    # gh argv as discrete tokens for spawn/tests (body via --body-file in real runs).
    gh_argv = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
        "--label",
        labels_csv,
    ]
    return {
        "ok": True,
        "mode": "pr_only",
        "question_number": question_number,
        "base": base,
        "branch": branch,
        "title": title,
        "body": body,
        "labels": labels,
        "paths": paths,
        "high_risk": high_risk,
        "need_human_review": high_risk,
        "git_commit": git_commit,
        "git_steps": git_steps,
        "gh_argv": gh_argv,
        "auto_push": False,
        "note": "Default apply is dry_run; live open requires apply_mutation_pr_plan(dry_run=False).",
    }


def apply_mutation_pr_plan(
    plan: dict[str, Any] | None,
    *,
    dry_run: bool = True,
    allow_high_risk: bool = False,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Apply (or dry-run) a structured mutation PR plan (#929).

    - ``dry_run=True`` (default): returns would_execute steps; **no** git/network.
    - ``dry_run=False``: invokes ``runner(plan)`` if provided; otherwise reports blocked
      with guidance (engine never auto-pushes without an injectable runner).
    - High-risk plans require ``allow_high_risk=True`` for non-dry apply.
    """
    if not plan or not plan.get("ok"):
        return {
            "ok": False,
            "applied": False,
            "dry_run": dry_run,
            "error": (plan or {}).get("error") or "invalid_plan",
        }

    high_risk = bool(plan.get("high_risk") or plan.get("need_human_review"))
    steps = list(plan.get("git_steps") or []) + [
        " ".join(str(x) for x in (plan.get("gh_argv") or [])[:8]) + " ..."
    ]

    if dry_run:
        return {
            "ok": True,
            "applied": False,
            "dry_run": True,
            "would_execute": steps,
            "high_risk": high_risk,
            "branch": plan.get("branch"),
            "base": plan.get("base"),
            "title": plan.get("title"),
            "note": "Dry-run only; no git push or gh pr create executed.",
        }

    if high_risk and not allow_high_risk:
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": "high_risk_requires_allow_high_risk",
            "high_risk": True,
            "note": "Set allow_high_risk=True after human review for AGENTS.md/SPEC/workflows.",
        }

    if runner is None:
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": "runner_required",
            "would_execute": steps,
            "note": "Provide runner(plan)->dict to open PR; default engine never auto-pushes.",
        }

    try:
        result = runner(plan)
    except Exception as exc:  # noqa: BLE001 — surface to caller
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": f"runner_failed: {exc}",
            "high_risk": high_risk,
        }

    out = {
        "ok": True,
        "applied": True,
        "dry_run": False,
        "high_risk": high_risk,
        "branch": plan.get("branch"),
        "base": plan.get("base"),
        "title": plan.get("title"),
        "runner_result": result,
    }
    if isinstance(result, dict):
        out["pr_url"] = result.get("pr_url") or result.get("url")
        out["pr_number"] = result.get("pr_number") or result.get("number")
    return out


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
        mutation_intents: list[dict[str, Any]] = []
        mutation_pr_draft: str | None = None
        mutation_pr_plan: dict[str, Any] | None = None
        mutation_pr_apply: dict[str, Any] | None = None
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

        # Git commit first so mutation PR drafts can cite provenance (#923/#925)
        git_commit = _git_head_sha()
        mutation_intents = _detect_artifact_mutation_intents(answer_text)
        if mutation_intents:
            mutation_pr_draft = _format_mutation_pr_draft(
                question_number=question_number,
                answer_text=answer_text,
                intents=mutation_intents,
                git_commit=git_commit,
            )
            mutation_pr_plan = build_mutation_pr_plan(
                question_number=question_number,
                answer_text=answer_text,
                intents=mutation_intents,
                git_commit=git_commit,
            )
            # Safe-by-default: always dry-run apply during contemplate (#929).
            mutation_pr_apply = apply_mutation_pr_plan(mutation_pr_plan, dry_run=True)
            high = sum(1 for i in mutation_intents if i.get("need_human_review"))
            actions.append(
                f"Detected {len(mutation_intents)} artifact mutation intent(s) "
                f"({high} high-risk); PR-only mode"
            )
            if mutation_pr_plan.get("ok"):
                actions.append(
                    f"Built mutation PR plan branch={mutation_pr_plan.get('branch')} "
                    f"base={mutation_pr_plan.get('base')} (dry-run apply only)"
                )

        # Prefer Documentation mutation plan issue over generic Feature when intents fire.
        if mutation_intents and not close_signal_met:
            try:
                paths = ", ".join(i["path"] for i in mutation_intents)
                title = (
                    f"[Feature]: Artifact mutation PR plan from Question #{question_number}"
                )
                body = (
                    f"Contemplation-driven **PR-only** process artifact mutation plan "
                    f"from answer to Question #{question_number}.\n\n"
                    f"**Parent Question:** #{question_number}\n\n"
                    f"**Target paths:** {paths}\n\n"
                    "Open a **Documentation** (or Feature) PR targeting `release` using the "
                    "draft body below. Never push mutations directly to main.\n\n"
                    f"{mutation_pr_draft}\n\n"
                    f"<!-- plate-contemplation-mutation-ref: q{question_number} @{timestamp} -->"
                )
                labels = ["Feature"]
                if any(i.get("need_human_review") for i in mutation_intents):
                    labels.append("need:human-review")
                new_issue = self.gh.api(
                    f"repos/{target}/issues",
                    method="POST",
                    fields={"title": title, "body": body, "labels": labels},
                )
                created_issues.append(
                    {
                        "number": new_issue.get("number"),
                        "title": title,
                        "url": new_issue.get("html_url"),
                        "type": "Feature",
                        "mutation_plan": True,
                    }
                )
                actions.append(
                    f"Created Feature mutation plan: #{new_issue.get('number')}"
                )
            except GhApiError as exc:
                actions.append(f"Create mutation plan issue failed: {exc}")
        elif (
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
            f"Artifact mutation intents: {len(mutation_intents)}",
        ]
        for intent in mutation_intents:
            hr = " need:human-review" if intent.get("need_human_review") else ""
            log_lines.append(
                f"Mutation intent: {intent.get('path')} "
                f"risk={intent.get('risk')} mode={intent.get('mode')}{hr} "
                f"— {intent.get('rationale')}"
            )
        if mutation_pr_plan and mutation_pr_plan.get("ok"):
            log_lines.append(
                f"Mutation PR plan: branch={mutation_pr_plan.get('branch')} "
                f"base={mutation_pr_plan.get('base')} "
                f"high_risk={mutation_pr_plan.get('high_risk')} "
                f"auto_push={mutation_pr_plan.get('auto_push')}"
            )
            log_lines.append(
                "Mutation PR apply: dry_run="
                f"{(mutation_pr_apply or {}).get('dry_run', True)} "
                f"applied={(mutation_pr_apply or {}).get('applied', False)}"
            )
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
            if mutation_intents:
                actions.append(
                    "Answer signal satisfied; close via PR that applies mutation intents"
                )
            else:
                actions.append(
                    "Answer signal satisfied; Question is ready to close via a PR artifact"
                )
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
            "mutation_intents": mutation_intents,
            "mutation_pr_draft": mutation_pr_draft,
            "mutation_pr_plan": mutation_pr_plan,
            "mutation_pr_apply": mutation_pr_apply,
            "note": "Strict checklist-based contemplation engine. Questions become PR-close-ready only when every answer-signal checklist item is backed by cited evidence from effective answers. Process artifacts use structured PR plans with dry-run apply by default (#925/#929).",
        }


def trigger_contemplation(
    question_number: int,
    answer_text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience entrypoint used by RecordAnswerTool and MCP plate_contemplate."""

    engine = ContemplationEngine(kwargs.pop("client", None))
    return engine.contemplate(question_number, answer_text, **kwargs)
