"""Q&A-driven epic and release planning (#640 / #629).

Structured scripts + plan builders that produce proposed Epic trees and
Release plans for human approval. Host creates GitHub issues after approve.
Standalone from feature/product planning (#630/#628) so it can land independently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

MARKER_BEGIN = "<!-- PLATE-EPIC-RELEASE-PLAN:BEGIN -->"
MARKER_END = "<!-- PLATE-EPIC-RELEASE-PLAN:END -->"

EPIC_PLANNING_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "intent",
        "prompt": "What is the epic intent / outcome (one sentence)?",
        "field": "intent",
        "required": True,
    },
    {
        "id": "problem",
        "prompt": "What problem or opportunity does this epic address?",
        "field": "problem",
        "required": True,
    },
    {
        "id": "success",
        "prompt": "How will we know the epic succeeded? (success signals)",
        "field": "success",
        "required": True,
    },
    {
        "id": "scope_in",
        "prompt": "What is in scope? (semicolon-separated)",
        "field": "scope_in",
        "required": True,
    },
    {
        "id": "scope_out",
        "prompt": "What is out of scope?",
        "field": "scope_out",
        "required": False,
    },
    {
        "id": "children",
        "prompt": "Name child Features (semicolon-separated short titles), or 'auto' for Research→Design→Feature stubs.",
        "field": "children",
        "required": False,
    },
    {
        "id": "risk",
        "prompt": "Risk tolerance for auto-stubs: off|low|medium|high (default medium).",
        "field": "risk",
        "required": False,
    },
    {
        "id": "track",
        "prompt": "Release track if known: Major|Minor|Patch|none.",
        "field": "track",
        "required": False,
    },
]

RELEASE_PLANNING_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "version_intent",
        "prompt": "What is this release for? (theme / user-facing outcome)",
        "field": "version_intent",
        "required": True,
    },
    {
        "id": "semver_hint",
        "prompt": "Semver intent: major|minor|patch|auto?",
        "field": "semver_hint",
        "required": True,
    },
    {
        "id": "scope_items",
        "prompt": "Which Epics/Features/issue numbers are in scope? (semicolon-separated)",
        "field": "scope_items",
        "required": True,
    },
    {
        "id": "success_signals",
        "prompt": "Release success signals / go-live checks?",
        "field": "success_signals",
        "required": False,
    },
    {
        "id": "risks",
        "prompt": "Risks, rollbacks, or human Tasks needed?",
        "field": "risks",
        "required": False,
    },
    {
        "id": "marketing",
        "prompt": "Marketing / release-notes highlights (or 'none').",
        "field": "marketing",
        "required": False,
    },
    {
        "id": "media_plan",
        "prompt": "GIF/video/demo plan for the release (or 'none').",
        "field": "media_plan",
        "required": False,
    },
    {
        "id": "cost_estimate",
        "prompt": "Rough token/cost ceiling for remaining release work?",
        "field": "cost_estimate",
        "required": False,
    },
]


@dataclass
class ERSession:
    kind: str  # epic | release
    turn: int = 0
    answers: dict[str, str] = field(default_factory=dict)
    complete: bool = False
    started_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split(text: str | None) -> list[str]:
    if not text:
        return []
    raw = str(text).replace("\n", ";")
    return [p.strip(" -•\t") for p in raw.split(";") if p.strip(" -•\t")]


def _qs(kind: str) -> list[dict[str, Any]]:
    return list(RELEASE_PLANNING_QUESTIONS if kind == "release" else EPIC_PLANNING_QUESTIONS)


def start_er_session(kind: str = "epic") -> dict[str, Any]:
    k = "release" if kind == "release" else "epic"
    qs = _qs(k)
    session = ERSession(kind=k, turn=0, answers={}, complete=False, started_at=_now())
    return {
        "session": session.to_dict(),
        "total_questions": len(qs),
        "next_question": qs[0] if qs else None,
        "prompt_segment": f"Present via ask_user_question: {qs[0]['prompt']}" if qs else "",
        "tui_hint": "One question at a time; then plate_er_planning_answer; build with plate_er_planning_build.",
        "issue_refs": ["#640", "#629", "#654"],
    }


def apply_er_answer(
    session: dict[str, Any] | ERSession,
    answer_text: str,
    *,
    question_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(session, ERSession):
        s = session
    else:
        s = ERSession(
            kind=session.get("kind") or "epic",
            turn=int(session.get("turn") or 0),
            answers=dict(session.get("answers") or {}),
            complete=bool(session.get("complete")),
            started_at=session.get("started_at") or _now(),
        )
    qs = _qs(s.kind)
    if s.complete or s.turn >= len(qs):
        return {
            "session": s.to_dict(),
            "complete": True,
            "next_question": None,
            "note": "session complete; call plate_er_planning_build",
        }
    q = qs[s.turn]
    field = question_id or q["field"]
    s.answers[field] = (answer_text or "").strip()
    s.turn += 1
    if s.turn >= len(qs):
        s.complete = True
        return {
            "session": s.to_dict(),
            "complete": True,
            "next_question": None,
            "prompt_segment": "Session complete. Build plan for human approval.",
        }
    nq = qs[s.turn]
    return {
        "session": s.to_dict(),
        "complete": False,
        "next_question": nq,
        "prompt_segment": f"Present via ask_user_question: {nq['prompt']}",
    }


def build_epic_plan(answers: dict[str, Any], *, title_hint: str | None = None) -> dict[str, Any]:
    intent = str(answers.get("intent") or "").strip()
    problem = str(answers.get("problem") or "").strip()
    success = str(answers.get("success") or "").strip()
    scope_in = _split(answers.get("scope_in"))
    scope_out = _split(answers.get("scope_out"))
    children_raw = str(answers.get("children") or "auto").strip()
    risk = str(answers.get("risk") or "medium").strip().lower()
    track = str(answers.get("track") or "none").strip()

    short = title_hint or intent[:70] or "Untitled epic"
    title = short if short.lower().startswith("[epic]") else f"[Epic]: {short}"

    children: list[dict[str, Any]] = []
    if children_raw.lower() in ("", "auto", "default"):
        children = [
            {
                "type": "Research",
                "title": f"[Research]: Foundations for {short}",
                "labels": ["Research", "need:refinement"],
            },
            {
                "type": "Design",
                "title": f"[Design]: Architecture for {short}",
                "labels": ["Design", "need:refinement"],
            },
            {
                "type": "Feature",
                "title": f"[Feature]: First slice of {short}",
                "labels": ["Feature", "need:refinement", "status:stub", f"risk:{risk if risk in ('low','medium','high') else 'medium'}"],
            },
        ]
        if risk == "high":
            children.append(
                {
                    "type": "Feature",
                    "title": f"[Feature]: Second slice of {short}",
                    "labels": ["Feature", "need:refinement", "status:stub", "risk:medium"],
                }
            )
        if risk == "off":
            children = []  # fully manual child creation
    else:
        for name in _split(children_raw):
            children.append(
                {
                    "type": "Feature",
                    "title": f"[Feature]: {name}",
                    "labels": ["Feature", "need:refinement", "status:stub"],
                }
            )

    body = f"""## Intent
{intent or '(not provided)'}

## Problem
{problem or '(not provided)'}

## Success signals
{success or '(not provided)'}

## Scope in
{chr(10).join('- ' + x for x in scope_in) or '- (none)'}

## Scope out
{chr(10).join('- ' + x for x in scope_out) or '- (none)'}

## Track
{track}

## Risk (auto-stub policy)
{risk}

## Planning provenance
Q&A epic planning (#640). Human approval required before creating GitHub Epic + children.
"""
    plan = {
        "kind": "epic",
        "title": title,
        "body": body,
        "labels": ["Epic", "need:refinement", "status:stub"],
        "children": children,
        "risk_tolerance": risk,
        "track": track,
        "requires_approval": True,
        "approval_prompt": "Approve epic plan? Approve (create Epic+children) | Revise | Reject",
        "prompt_segment": (
            "Present epic plan via ask_user_question. On Approve: create Epic issue, milestone, "
            "child stubs with need:refinement; link to Next Release if track set. Do not implement features yet."
        ),
        "created_at": _now(),
    }
    plan["marker"] = _marker(plan)
    return plan


def build_release_plan(answers: dict[str, Any], *, title_hint: str | None = None) -> dict[str, Any]:
    intent = str(answers.get("version_intent") or "").strip()
    semver = str(answers.get("semver_hint") or "auto").strip().lower()
    scope = _split(answers.get("scope_items"))
    success = str(answers.get("success_signals") or "").strip()
    risks = str(answers.get("risks") or "").strip()
    marketing = str(answers.get("marketing") or "none").strip()
    media = str(answers.get("media_plan") or "none").strip()
    cost = str(answers.get("cost_estimate") or "").strip()

    title = title_hint or intent[:70] or "Next release plan"
    body = f"""## Release intent
{intent or '(not provided)'}

## Semver hint
{semver}

## Scope
{chr(10).join('- ' + x for x in scope) or '- (none)'}

## Success signals
{success or '(none)'}

## Risks / human Tasks
{risks or '(none)'}

## Marketing / notes highlights
{marketing}

## Media plan
{media}

## Cost estimate
{cost or '(not provided)'}

## Ceremony checklist (draft)
- [ ] Freeze non-bug merges when packaging
- [ ] Aggregate unreleased fragments (`gh plate release cut`)
- [ ] Release PR → main with Documentation + Release labels
- [ ] Tag + finalize after human merge

## Planning provenance
Q&A release planning (#629). Human approval required before creating/renaming Release issue.
"""
    plan = {
        "kind": "release",
        "title": f"[Release plan]: {title}",
        "body": body,
        "semver_hint": semver,
        "scope_items": scope,
        "media_plan": media,
        "marketing": marketing,
        "cost_estimate": cost,
        "labels": ["Release", "Documentation", "need:refinement"],
        "requires_approval": True,
        "approval_prompt": "Approve release plan? Approve (draft Release issue + notes skeleton) | Revise | Reject",
        "prompt_segment": (
            "Present release plan via ask_user_question. On Approve: ensure Next Release issue exists, "
            "link scope items, draft notes skeleton under .agentic/releases/ — do not cut/tag without ceremony."
        ),
        "notes_skeleton": {
            "highlights": [marketing] if marketing and marketing.lower() != "none" else [],
            "scope": scope,
            "media_plan": media,
            "semver_hint": semver,
        },
        "created_at": _now(),
    }
    plan["marker"] = _marker(plan)
    return plan


def build_er_plan_from_session(session: dict[str, Any] | ERSession) -> dict[str, Any]:
    if isinstance(session, ERSession):
        kind, answers, complete = session.kind, session.answers, session.complete
    else:
        kind = session.get("kind") or "epic"
        answers = dict(session.get("answers") or {})
        complete = bool(session.get("complete"))
    if not answers:
        return {"ok": False, "error": "session empty"}
    plan = build_release_plan(answers) if kind == "release" else build_epic_plan(answers)
    return {"ok": True, "plan": plan, "session_complete": complete}


def get_er_script(kind: str = "epic") -> dict[str, Any]:
    k = "release" if kind == "release" else "epic"
    qs = _qs(k)
    return {"kind": k, "questions": qs, "count": len(qs), "issue_refs": ["#640", "#629", "#654"]}


def _marker(plan: dict[str, Any]) -> str:
    import json

    slim = {
        "kind": plan.get("kind"),
        "title": plan.get("title"),
        "requires_approval": plan.get("requires_approval"),
        "created_at": plan.get("created_at"),
        "children": len(plan.get("children") or []),
        "scope_items": len(plan.get("scope_items") or []),
    }
    return f"{MARKER_BEGIN}\n{json.dumps(slim, indent=2)}\n{MARKER_END}"
