"""Q&A-driven product and feature planning workflows (#628 / #630).

Structured question scripts + plan builders that turn user answers into
proposed GitHub issue stubs (Feature / Epic + children) with labels, ACs,
tests, docs impact, media plan, and approval gates.

Host presents questions via ask_user_question / gh plate plan; this module
is pure planning (no issue create) so agents keep GitHub truth ownership.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER_BEGIN = "<!-- PLATE-PLAN:BEGIN -->"
MARKER_END = "<!-- PLATE-PLAN:END -->"

# Durable multi-turn sessions + pending plans (#628/#630 harden)
PLANNING_DIR = Path(".agentic/planning")
SESSIONS_DIR = PLANNING_DIR / "sessions"
PENDING_DIR = PLANNING_DIR / "pending"

# Feature planning script (#630) — order matters for session turn index
FEATURE_PLANNING_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "problem",
        "prompt": "What problem does this feature solve, and for whom?",
        "field": "problem",
        "required": True,
    },
    {
        "id": "desired_behavior",
        "prompt": "What should the system do when the feature is done? (observable behavior)",
        "field": "desired_behavior",
        "required": True,
    },
    {
        "id": "acceptance_criteria",
        "prompt": "List acceptance criteria (one per line or semicolon-separated).",
        "field": "acceptance_criteria",
        "required": True,
    },
    {
        "id": "tests",
        "prompt": "What tests or verification prove it works? (unit/integration/e2e)",
        "field": "tests",
        "required": True,
    },
    {
        "id": "docs_impact",
        "prompt": "What docs/wiki/SPEC/fragments need updates?",
        "field": "docs_impact",
        "required": False,
    },
    {
        "id": "design_needs",
        "prompt": "Is a Design or Research issue needed first? (none / design / research / both)",
        "field": "design_needs",
        "required": False,
    },
    {
        "id": "cost_risk",
        "prompt": "Rough cost/risk (tokens, risk:low|medium|high, any human Tasks)?",
        "field": "cost_risk",
        "required": False,
    },
    {
        "id": "media_plan",
        "prompt": "Video/GIF/demo plan for PR evidence (or 'none').",
        "field": "media_plan",
        "required": False,
    },
    {
        "id": "epic_link",
        "prompt": "Parent Epic number or short name (or 'none').",
        "field": "epic_link",
        "required": False,
    },
]

PRODUCT_PLANNING_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "value_prop",
        "prompt": "What is the core value proposition of the product (or this product area)?",
        "field": "value_prop",
        "required": True,
    },
    {
        "id": "users",
        "prompt": "Who are the primary users/personas?",
        "field": "users",
        "required": True,
    },
    {
        "id": "goals",
        "prompt": "List top goals (semicolon-separated).",
        "field": "goals",
        "required": True,
    },
    {
        "id": "non_goals",
        "prompt": "What is explicitly out of scope?",
        "field": "non_goals",
        "required": False,
    },
    {
        "id": "risks",
        "prompt": "Key risks and open questions?",
        "field": "risks",
        "required": False,
    },
    {
        "id": "initial_epics",
        "prompt": "Name 1–5 initial Epics (semicolon-separated short names).",
        "field": "initial_epics",
        "required": True,
    },
    {
        "id": "spec_updates",
        "prompt": "Which SPEC/Goals sections should change?",
        "field": "spec_updates",
        "required": False,
    },
]


@dataclass
class PlanningSession:
    kind: str  # feature | product
    turn: int = 0
    answers: dict[str, str] = field(default_factory=dict)
    complete: bool = False
    started_at: str = ""
    id: str = ""  # durable session id under .agentic/planning/sessions/

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_list(text: str | None) -> list[str]:
    if not text:
        return []
    raw = str(text).replace("\n", ";")
    parts = [p.strip(" -•\t") for p in raw.split(";")]
    return [p for p in parts if p]


def _questions_for(kind: str) -> list[dict[str, Any]]:
    if kind == "product":
        return list(PRODUCT_PLANNING_QUESTIONS)
    return list(FEATURE_PLANNING_QUESTIONS)


def _session_path(session_id: str, base_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", session_id or "unknown")
    root = base_dir if base_dir is not None else SESSIONS_DIR
    return root / f"{safe}.json"


def save_planning_session(
    session: dict[str, Any] | PlanningSession,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Persist session for multi-process / multi-turn Q&A (#628/#630)."""
    data = session.to_dict() if isinstance(session, PlanningSession) else dict(session)
    sid = data.get("id") or f"plan-{data.get('kind', 'feature')}-{uuid.uuid4().hex[:10]}"
    data["id"] = sid
    data["updated_at"] = _now()
    path = _session_path(sid, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    data["path"] = str(path)
    return data


def load_planning_session(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any] | None:
    path = _session_path(session_id, base_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except (OSError, json.JSONDecodeError):
        return None


def list_pending_plans(*, base_dir: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List durable plan stubs awaiting human approval."""
    root = base_dir if base_dir is not None else PENDING_DIR
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def save_pending_plan(
    plan: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Persist built plan under .agentic/planning/pending/ for feed/approval."""
    root = base_dir if base_dir is not None else PENDING_DIR
    root.mkdir(parents=True, exist_ok=True)
    pid = plan.get("id") or f"planstub-{plan.get('kind', 'feature')}-{uuid.uuid4().hex[:10]}"
    out = dict(plan)
    out["id"] = pid
    out["status"] = out.get("status") or "pending_approval"
    out["updated_at"] = _now()
    path = root / f"{re.sub(r'[^a-zA-Z0-9._-]', '_', pid)}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out["path"] = str(path)
    return out


def question_ask_user_payload(
    question: dict[str, Any] | None,
    *,
    kind: str = "feature",
    turn: int = 0,
    total: int = 0,
) -> dict[str, Any] | None:
    """Native TUI payload for one planning script question (#628/#630)."""
    if not question:
        return None
    qid = str(question.get("id") or f"q-{turn}")
    prompt = str(question.get("prompt") or "")
    progress = f" ({turn + 1}/{total})" if total else ""
    options = [
        {"id": "answer", "label": "Answer (free text)", "description": "Provide the answer text to plate_planning_answer."},
        {"id": "skip_optional", "label": "Skip / none", "description": "Record 'none' when the field is optional."},
        {"id": "pause", "label": "Pause session", "description": "Stop; resume later via session id (durable)."},
    ]
    # free-form Q&A: options guide host; primary answer is free text
    return {
        "item_id": qid,
        "item_type": "planning_question",
        "kind": kind,
        "question": f"[{kind} planning{progress}] {prompt}",
        "options": options,
        "field": question.get("field"),
        "required": bool(question.get("required")),
        "multi_select": False,
        "allow_free_text": True,
    }


def start_planning_session(
    kind: str = "feature",
    *,
    base_dir: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Begin a Q&A planning session; returns first question + session state."""
    k = "product" if kind == "product" else "feature"
    qs = _questions_for(k)
    session = PlanningSession(
        kind=k,
        turn=0,
        answers={},
        complete=False,
        started_at=_now(),
        id=f"plan-{k}-{uuid.uuid4().hex[:10]}",
    )
    sdict = session.to_dict()
    if persist:
        sdict = save_planning_session(sdict, base_dir=base_dir)
    nq = qs[0] if qs else None
    return {
        "session": sdict,
        "session_id": sdict.get("id"),
        "total_questions": len(qs),
        "next_question": nq,
        "ask_user_question": question_ask_user_payload(nq, kind=k, turn=0, total=len(qs)),
        "prompt_segment": (
            f"Present via native ask_user_question: {qs[0]['prompt']}"
            if qs
            else "No questions configured."
        ),
        "tui_hint": (
            "One question at a time via ask_user_question (see ask_user_question payload); "
            "record free-text answer with plate_planning_answer; session_id is durable."
        ),
    }


def apply_planning_answer(
    session: dict[str, Any] | PlanningSession,
    answer_text: str,
    *,
    question_id: str | None = None,
    base_dir: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Record one answer and advance the session."""
    if isinstance(session, PlanningSession):
        s = session
    else:
        # hydrate durable session if only id passed
        if session.get("id") and not session.get("answers") and base_dir is not None:
            loaded = load_planning_session(str(session["id"]), base_dir=base_dir)
            if loaded:
                session = loaded
        s = PlanningSession(
            kind=session.get("kind") or "feature",
            turn=int(session.get("turn") or 0),
            answers=dict(session.get("answers") or {}),
            complete=bool(session.get("complete")),
            started_at=session.get("started_at") or _now(),
            id=str(session.get("id") or ""),
        )
    if not s.id:
        s.id = f"plan-{s.kind}-{uuid.uuid4().hex[:10]}"
    qs = _questions_for(s.kind)
    if s.complete or s.turn >= len(qs):
        sdict = s.to_dict()
        if persist:
            sdict = save_planning_session(sdict, base_dir=base_dir)
        return {
            "session": sdict,
            "session_id": sdict.get("id"),
            "complete": True,
            "next_question": None,
            "ask_user_question": None,
            "note": "session already complete; call plate_planning_build",
        }
    q = qs[s.turn]
    if question_id and question_id != q["id"]:
        # allow explicit field write
        field = question_id
    else:
        field = q["field"]
    s.answers[field] = (answer_text or "").strip()
    s.turn += 1
    if s.turn >= len(qs):
        s.complete = True
        sdict = s.to_dict()
        if persist:
            sdict = save_planning_session(sdict, base_dir=base_dir)
        return {
            "session": sdict,
            "session_id": sdict.get("id"),
            "complete": True,
            "next_question": None,
            "ask_user_question": {
                "item_id": "build",
                "item_type": "planning_complete",
                "kind": s.kind,
                "question": "Planning Q&A complete. Build stubs for approval?",
                "options": [
                    {"id": "build", "label": "Build plan", "description": "plate_planning_build → pending approval"},
                    {"id": "revise", "label": "Revise answers", "description": "Start a new session or edit answers."},
                ],
                "multi_select": False,
            },
            "prompt_segment": "Session complete. Call plate_planning_build to produce stubs for approval.",
        }
    nq = qs[s.turn]
    sdict = s.to_dict()
    if persist:
        sdict = save_planning_session(sdict, base_dir=base_dir)
    return {
        "session": sdict,
        "session_id": sdict.get("id"),
        "complete": False,
        "next_question": nq,
        "ask_user_question": question_ask_user_payload(
            nq, kind=s.kind, turn=s.turn, total=len(qs)
        ),
        "prompt_segment": f"Present via native ask_user_question: {nq['prompt']}",
    }


def build_feature_plan(
    answers: dict[str, Any],
    *,
    title_hint: str | None = None,
    require_approval: bool = True,
) -> dict[str, Any]:
    """Turn feature Q&A answers into a proposed Feature issue stub (#630)."""
    problem = str(answers.get("problem") or "").strip()
    behavior = str(answers.get("desired_behavior") or "").strip()
    acs = _split_list(answers.get("acceptance_criteria"))
    tests = str(answers.get("tests") or "").strip()
    docs = str(answers.get("docs_impact") or "Update fragment under .agentic/releases/unreleased/.").strip()
    design_needs = str(answers.get("design_needs") or "none").strip().lower()
    cost_risk = str(answers.get("cost_risk") or "risk:medium").strip()
    media = str(answers.get("media_plan") or "none").strip()
    epic = str(answers.get("epic_link") or "none").strip()

    short = title_hint or (behavior[:60] if behavior else problem[:60] or "Untitled feature")
    title = short if short.lower().startswith("[feature]") else f"[Feature]: {short}"

    risk_label = "risk:medium"
    for tok in cost_risk.replace(",", " ").split():
        if tok.startswith("risk:"):
            risk_label = tok
            break

    labels = ["Feature", "need:refinement", risk_label, "status:stub"]
    linked: list[dict[str, Any]] = []
    if design_needs in ("design", "both"):
        linked.append(
            {
                "type": "Design",
                "title": f"[Design]: {short}",
                "labels": ["Design", "need:refinement"],
                "body": f"Design for feature plan.\n\nProblem: {problem}\n\nDesired: {behavior}",
            }
        )
    if design_needs in ("research", "both"):
        linked.append(
            {
                "type": "Research",
                "title": f"[Research]: {short}",
                "labels": ["Research", "need:refinement"],
                "body": f"Research for feature plan.\n\nProblem: {problem}",
            }
        )

    ac_md = "\n".join(f"- [ ] {a}" for a in acs) if acs else "- [ ] (add acceptance criteria)"
    body = f"""## Problem
{problem or '(not provided)'}

## Desired behavior
{behavior or '(not provided)'}

## Acceptance criteria
{ac_md}

## Tests / verification
{tests or '(not provided)'}

## Documentation impact
{docs}

## Media / demo plan
{media}

## Cost / risk
{cost_risk}

## Epic
{epic}

## Planning provenance
Generated by Q&A feature planning (#630). Requires human approval before implementation.
"""
    plan = {
        "kind": "feature",
        "title": title,
        "body": body,
        "labels": labels,
        "acceptance_criteria": acs,
        "tests": tests,
        "docs_impact": docs,
        "media_plan": media,
        "cost_risk": cost_risk,
        "epic_link": epic,
        "linked_stubs": linked,
        "requires_approval": require_approval,
        "approval_prompt": (
            "Approve this Feature plan? Options: Approve (create stubs), Revise (continue Q&A), Reject."
        ),
        "prompt_segment": (
            "Present the proposed Feature plan via ask_user_question for approval. "
            "On Approve: create GitHub Feature issue with labels + linked Design/Research stubs. "
            "On Revise: resume planning session. Do not start implementation until approved."
        ),
        "created_at": _now(),
    }
    plan["marker"] = render_plan_marker(plan)
    return plan


def build_product_plan(
    answers: dict[str, Any],
    *,
    title_hint: str | None = None,
    require_approval: bool = True,
) -> dict[str, Any]:
    """Turn product Q&A answers into proposed Epic stubs (#628)."""
    value = str(answers.get("value_prop") or "").strip()
    users = str(answers.get("users") or "").strip()
    goals = _split_list(answers.get("goals"))
    non_goals = _split_list(answers.get("non_goals"))
    risks = str(answers.get("risks") or "").strip()
    epics = _split_list(answers.get("initial_epics"))
    spec = str(answers.get("spec_updates") or "Update SPEC.md Goals + Beta Roadmap as needed.").strip()

    title = title_hint or (value[:70] if value else "Product planning session")
    proposed = []
    for name in epics:
        slug = name.strip()
        proposed.append(
            {
                "type": "Epic",
                "title": f"[Epic]: {slug}",
                "labels": ["Epic", "need:refinement", "status:stub"],
                "children": [
                    {"type": "Research", "title": f"[Research]: Scope {slug}", "labels": ["Research", "need:refinement"]},
                    {"type": "Design", "title": f"[Design]: Architecture for {slug}", "labels": ["Design", "need:refinement"]},
                    {"type": "Feature", "title": f"[Feature]: First slice of {slug}", "labels": ["Feature", "need:refinement", "status:stub"]},
                ],
            }
        )

    body = f"""## Value proposition
{value or '(not provided)'}

## Users
{users or '(not provided)'}

## Goals
{chr(10).join('- ' + g for g in goals) or '- (none)'}

## Non-goals
{chr(10).join('- ' + g for g in non_goals) or '- (none)'}

## Risks
{risks or '(none listed)'}

## SPEC / Goals updates
{spec}

## Planning provenance
Generated by Q&A product planning (#628). Requires human approval before creating Epics.
"""
    plan = {
        "kind": "product",
        "title": f"[Product plan]: {title}",
        "summary_body": body,
        "value_prop": value,
        "users": users,
        "goals": goals,
        "non_goals": non_goals,
        "risks": risks,
        "spec_updates": spec,
        "proposed_epics": proposed,
        "requires_approval": require_approval,
        "approval_prompt": (
            "Approve this product plan? Options: Approve (create Epic stubs), Revise, Reject."
        ),
        "prompt_segment": (
            "Present product plan via ask_user_question. On Approve: create Epic issues + "
            "Research/Design/Feature child stubs with need:refinement. Update SPEC/Goals only with human OK."
        ),
        "created_at": _now(),
    }
    plan["marker"] = render_plan_marker(plan)
    return plan


def build_plan_from_session(
    session: dict[str, Any] | PlanningSession,
    *,
    planning_root: Path | None = None,
    persist_pending: bool = True,
) -> dict[str, Any]:
    """Build plan from session; optionally persist under planning_root/pending/."""
    if isinstance(session, PlanningSession):
        kind = session.kind
        answers = session.answers
        complete = session.complete
        sid = session.id
    else:
        kind = session.get("kind") or "feature"
        answers = dict(session.get("answers") or {})
        complete = bool(session.get("complete"))
        sid = str(session.get("id") or "")
    if not complete and not answers:
        return {"ok": False, "error": "session incomplete or empty"}
    if kind == "product":
        plan = build_product_plan(answers)
    else:
        plan = build_feature_plan(answers)
    plan["session_id"] = sid
    if persist_pending:
        pending_root = (planning_root / "pending") if planning_root is not None else None
        plan = save_pending_plan(plan, base_dir=pending_root)
    approval_payload = {
        "item_id": plan.get("id") or "plan",
        "item_type": "planning_approval",
        "kind": kind,
        "question": f"Approve {kind} plan: {plan.get('title') or 'untitled'}?",
        "options": [
            {"id": "approve", "label": "Approve", "description": "Create GitHub issues/stubs from plan (host)."},
            {"id": "revise", "label": "Revise", "description": "Return to Q&A; do not create issues."},
            {"id": "reject", "label": "Reject", "description": "Drop plan; keep session for audit only."},
        ],
        "multi_select": False,
    }
    return {
        "ok": True,
        "plan": plan,
        "session_complete": complete,
        "ask_user_question": approval_payload,
        "pending_path": plan.get("path"),
    }


def get_planning_script(kind: str = "feature") -> dict[str, Any]:
    k = "product" if kind == "product" else "feature"
    qs = _questions_for(k)
    return {
        "kind": k,
        "questions": qs,
        "count": len(qs),
        "issue_refs": ["#630", "#628", "#654"],
    }


def render_plan_marker(plan: dict[str, Any]) -> str:
    import json

    slim = {
        "kind": plan.get("kind"),
        "title": plan.get("title"),
        "requires_approval": plan.get("requires_approval"),
        "created_at": plan.get("created_at"),
        "linked_stubs": len(plan.get("linked_stubs") or plan.get("proposed_epics") or []),
    }
    return f"{MARKER_BEGIN}\n{json.dumps(slim, indent=2)}\n{MARKER_END}"
