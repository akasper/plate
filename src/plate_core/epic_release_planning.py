"""Q&A-driven epic and release planning (#640 / #629).

Structured scripts + plan builders that produce proposed Epic trees and
Release plans for human approval. Host creates GitHub issues after approve.
Standalone from feature/product planning (#630/#628) so it can land independently.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER_BEGIN = "<!-- PLATE-EPIC-RELEASE-PLAN:BEGIN -->"
MARKER_END = "<!-- PLATE-EPIC-RELEASE-PLAN:END -->"

# Durable multi-turn ER sessions (#629/#640) — sibling of feature/product planning
ER_SESSIONS_DIR = Path(".agentic/planning/er_sessions")

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
    id: str = ""

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


def _er_session_path(session_id: str, base_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", session_id or "unknown")
    return (base_dir or ER_SESSIONS_DIR) / f"{safe}.json"


def save_er_session(
    session: dict[str, Any] | ERSession,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    data = session.to_dict() if isinstance(session, ERSession) else dict(session)
    sid = data.get("id") or f"er-{data.get('kind', 'epic')}-{uuid.uuid4().hex[:10]}"
    data["id"] = sid
    data["updated_at"] = _now()
    path = _er_session_path(sid, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    data["path"] = str(path)
    return data


def load_er_session(session_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = _er_session_path(session_id, base_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except (OSError, json.JSONDecodeError):
        return None


def er_question_payload(
    question: dict[str, Any] | None,
    *,
    kind: str = "epic",
    turn: int = 0,
    total: int = 0,
) -> dict[str, Any] | None:
    """Native ask_user_question payload for one ER script question (#629/#640)."""
    if not question:
        return None
    qid = str(question.get("id") or f"q-{turn}")
    prompt = str(question.get("prompt") or "")
    progress = f" ({turn + 1}/{total})" if total else ""
    return {
        "item_id": qid,
        "item_type": "er_planning_question",
        "kind": kind,
        "question": f"[{kind} planning{progress}] {prompt}",
        "options": [
            {"id": "answer", "label": "Answer (free text)", "description": "Provide text to plate_er_planning_answer."},
            {"id": "skip_optional", "label": "Skip / none", "description": "Record 'none' when optional."},
            {"id": "pause", "label": "Pause session", "description": "Resume later via durable session_id."},
        ],
        "field": question.get("field"),
        "required": bool(question.get("required")),
        "multi_select": False,
        "allow_free_text": True,
    }


# Heuristic epic/release planning costs (#634 / #629 / #640).
_ER_SESSION_BASE = 4500
_ER_RELEASE_EXTRA = 1500
_ER_BUILD_BASE = 5500
_ER_RELEASE_BUILD_EXTRA = 2000


def estimate_er_planning_cost(
    *,
    kind: str = "epic",
    phase: str = "start",
) -> dict[str, Any]:
    """Advisory token estimate for epic/release Q&A planning start or build (#634/#629/#640)."""
    k = "release" if (kind or "").lower() == "release" else "epic"
    phase_n = (phase or "start").lower()
    if phase_n not in ("start", "build"):
        phase_n = "start"
    if phase_n == "start":
        tokens = _ER_SESSION_BASE + (_ER_RELEASE_EXTRA if k == "release" else 0)
    else:
        tokens = _ER_BUILD_BASE + (_ER_RELEASE_BUILD_EXTRA if k == "release" else 0)
    return {
        "ok": True,
        "kind": k,
        "phase": phase_n,
        "estimated_tokens": int(tokens),
        "breakdown": {
            "base": _ER_SESSION_BASE if phase_n == "start" else _ER_BUILD_BASE,
            "release_extra": (
                (_ER_RELEASE_EXTRA if phase_n == "start" else _ER_RELEASE_BUILD_EXTRA)
                if k == "release"
                else 0
            ),
        },
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine enforce hard ceilings.",
            "start_er_session / build_er_plan_from_session hydrate remaining when use_live_budget.",
        ],
    }


def _er_budget_gate(
    *,
    kind: str,
    phase: str,
    budget_remaining: int | None,
    use_live_budget: bool,
) -> tuple[dict[str, Any], int | None, list[str], dict[str, Any] | None]:
    cost_est = estimate_er_planning_cost(kind=kind, phase=phase)
    est = int(cost_est.get("estimated_tokens") or 0)
    notes: list[str] = []
    effective = budget_remaining
    if effective is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(estimate_tokens=est)
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective = int(rem)
                notes.append(
                    f"budget hydrated: remaining_tokens={effective} "
                    f"pressure={snap.get('budget_pressure')}"
                )
        except Exception as exc:
            notes.append(f"budget hydrate skipped: {exc}")
    if effective is not None and est > int(effective):
        return (
            cost_est,
            effective,
            notes,
            {
                "ok": False,
                "blocked": True,
                "reason": "budget",
                "error": f"budget: est {est} tokens exceeds remaining {effective}",
                "cost_estimate_tokens": est,
                "budget_remaining": int(effective),
                "cost_estimate": cost_est,
                "notes": notes,
            },
        )
    return cost_est, effective, notes, None


def start_er_session(
    kind: str = "epic",
    *,
    base_dir: Path | None = None,
    persist: bool = True,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Begin epic/release Q&A planning session.

    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    """
    k = "release" if kind == "release" else "epic"
    cost_est, effective_remaining, budget_notes, blocked = _er_budget_gate(
        kind=k,
        phase="start",
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
    if blocked is not None:
        return blocked
    qs = _qs(k)
    session = ERSession(
        kind=k,
        turn=0,
        answers={},
        complete=False,
        started_at=_now(),
        id=f"er-{k}-{uuid.uuid4().hex[:10]}",
    )
    sdict = session.to_dict()
    if persist:
        sdict = save_er_session(sdict, base_dir=base_dir)
    nq = qs[0] if qs else None
    return {
        "ok": True,
        "session": sdict,
        "session_id": sdict.get("id"),
        "total_questions": len(qs),
        "next_question": nq,
        "cost_estimate_tokens": int(cost_est.get("estimated_tokens") or 0),
        "budget_remaining": effective_remaining,
        "cost_estimate": cost_est,
        "notes": budget_notes,
        "ask_user_question": er_question_payload(nq, kind=k, turn=0, total=len(qs)),
        "prompt_segment": f"Present via ask_user_question: {qs[0]['prompt']}" if qs else "",
        "tui_hint": (
            "One question at a time via ask_user_question payload; "
            "plate_er_planning_answer; build with plate_er_planning_build; session_id is durable."
        ),
        "issue_refs": ["#640", "#629", "#654", "#634"],
    }


def apply_er_answer(
    session: dict[str, Any] | ERSession,
    answer_text: str,
    *,
    question_id: str | None = None,
    base_dir: Path | None = None,
    persist: bool = True,
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
            id=str(session.get("id") or ""),
        )
    if not s.id:
        s.id = f"er-{s.kind}-{uuid.uuid4().hex[:10]}"
    qs = _qs(s.kind)
    if s.complete or s.turn >= len(qs):
        sdict = s.to_dict()
        if persist:
            sdict = save_er_session(sdict, base_dir=base_dir)
        return {
            "session": sdict,
            "session_id": sdict.get("id"),
            "complete": True,
            "next_question": None,
            "ask_user_question": None,
            "note": "session complete; call plate_er_planning_build",
        }
    q = qs[s.turn]
    field = question_id or q["field"]
    s.answers[field] = (answer_text or "").strip()
    s.turn += 1
    if s.turn >= len(qs):
        s.complete = True
        sdict = s.to_dict()
        if persist:
            sdict = save_er_session(sdict, base_dir=base_dir)
        return {
            "session": sdict,
            "session_id": sdict.get("id"),
            "complete": True,
            "next_question": None,
            "ask_user_question": {
                "item_id": "build",
                "item_type": "er_planning_complete",
                "kind": s.kind,
                "question": f"{s.kind.title()} planning Q&A complete. Build plan for approval?",
                "options": [
                    {"id": "build", "label": "Build plan", "description": "plate_er_planning_build → pending approval"},
                    {"id": "revise", "label": "Revise", "description": "Start a new session."},
                ],
                "multi_select": False,
            },
            "prompt_segment": "Session complete. Build plan for human approval.",
        }
    nq = qs[s.turn]
    sdict = s.to_dict()
    if persist:
        sdict = save_er_session(sdict, base_dir=base_dir)
    return {
        "session": sdict,
        "session_id": sdict.get("id"),
        "complete": False,
        "next_question": nq,
        "ask_user_question": er_question_payload(nq, kind=s.kind, turn=s.turn, total=len(qs)),
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


def build_er_plan_from_session(
    session: dict[str, Any] | ERSession,
    *,
    planning_root: Path | None = None,
    persist_pending: bool = True,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Build epic/release plan from session.

    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    """
    if isinstance(session, ERSession):
        kind, answers, complete = session.kind, session.answers, session.complete
        sid = session.id
    else:
        kind = session.get("kind") or "epic"
        answers = dict(session.get("answers") or {})
        complete = bool(session.get("complete"))
        sid = str(session.get("id") or "")
    if not answers:
        return {"ok": False, "error": "session empty"}
    cost_est, effective_remaining, budget_notes, blocked = _er_budget_gate(
        kind=str(kind),
        phase="build",
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
    if blocked is not None:
        return blocked
    plan = build_release_plan(answers) if kind == "release" else build_epic_plan(answers)
    plan["session_id"] = sid
    if persist_pending:
        try:
            from .planning import save_pending_plan

            pending_root = (planning_root / "pending") if planning_root is not None else None
            plan = save_pending_plan(plan, base_dir=pending_root)
        except Exception:
            pass
    pid = str(plan.get("id") or "er-plan")
    approval_payload = {
        "item_id": pid,
        "item_type": "er_planning_approval",
        "kind": kind,
        "question": f"Approve {kind} plan: {plan.get('title') or 'untitled'}?",
        "options": [
            {
                "id": "approve",
                "label": "Approve",
                "description": f"plate_er_planning_decide {pid} approve — create Epic/Release artifacts (host)",
            },
            {
                "id": "revise",
                "label": "Revise",
                "description": f"plate_er_planning_decide {pid} revise — return to Q&A",
            },
            {
                "id": "reject",
                "label": "Reject",
                "description": f"plate_er_planning_decide {pid} reject — drop plan",
            },
        ],
        "multi_select": False,
    }
    # Keep pending file payload in sync when saved
    if plan.get("path") and plan.get("status") in ("pending_approval", "pending", None, ""):
        plan["ask_user_question"] = approval_payload
        try:
            Path(plan["path"]).write_text(
                json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError:
            pass
    return {
        "ok": True,
        "plan": plan,
        "session_complete": complete,
        "ask_user_question": approval_payload,
        "pending_path": plan.get("path"),
        "cost_estimate_tokens": int(cost_est.get("estimated_tokens") or 0),
        "budget_remaining": effective_remaining,
        "cost_estimate": cost_est,
        "notes": budget_notes,
    }


def er_plan_ask_user_payload(plan: dict[str, Any]) -> dict[str, Any]:
    """TUI for epic/release plan approval (#629/#640), including revise_requested resubmit."""
    pid = str(plan.get("id") or "er-plan")
    kind = str(plan.get("kind") or "epic")
    title = str(plan.get("title") or "untitled")[:80]
    status = str(plan.get("status") or "pending_approval")
    if status in ("revise_requested", "revised"):
        return {
            "item_id": pid,
            "item_type": "er_planning_approval",
            "kind": kind,
            "status": status,
            "question": f"Revise requested for {kind} plan: {title} — resubmit?",
            "options": [
                {
                    "id": "resubmit",
                    "label": "Resubmit for approval",
                    "description": (
                        f"plate_er_planning_resubmit {pid} / gh plate er-plan --resubmit {pid}"
                    ),
                },
                {
                    "id": "resume_session",
                    "label": "Resume ER Q&A",
                    "description": f"Continue session {plan.get('session_id') or 'n/a'} then rebuild",
                },
                {
                    "id": "reject",
                    "label": "Reject",
                    "description": f"plate_er_planning_decide {pid} reject",
                },
            ],
            "multi_select": False,
        }
    return {
        "item_id": pid,
        "item_type": "er_planning_approval",
        "kind": kind,
        "status": status,
        "question": f"Approve {kind} plan: {title}?",
        "options": [
            {
                "id": "approve",
                "label": "Approve",
                "description": f"plate_er_planning_decide {pid} approve — create Epic/Release artifacts (host)",
            },
            {
                "id": "revise",
                "label": "Revise",
                "description": f"plate_er_planning_decide {pid} revise — keep actionable until resubmit",
            },
            {
                "id": "reject",
                "label": "Reject",
                "description": f"plate_er_planning_decide {pid} reject — drop plan",
            },
        ],
        "multi_select": False,
    }


def resubmit_er_plan(
    plan_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    note: str = "",
    resubmitted_by: str = "human",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Resubmit revise_requested epic/release plan for re-approval (#640/#629)."""
    from .planning import resubmit_pending_plan

    out = resubmit_pending_plan(
        plan_id,
        title=title,
        body=body,
        note=note,
        resubmitted_by=resubmitted_by,
        base_dir=base_dir,
    )
    if not out.get("ok"):
        return out
    plan = out.get("plan") or {}
    # Prefer ER-shaped TUI after resubmit
    plan["ask_user_question"] = er_plan_ask_user_payload(plan)
    plan["approval_prompt"] = plan["ask_user_question"].get("question")
    if plan.get("path"):
        try:
            Path(plan["path"]).write_text(
                json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError:
            pass
    out["plan"] = plan
    out["ask_user_question"] = plan["ask_user_question"]
    return out


def decide_er_plan(
    plan_id: str,
    decision: str,
    *,
    note: str = "",
    decided_by: str = "human",
    base_dir: Path | None = None,
    archive: bool = True,
) -> dict[str, Any]:
    """Approve/revise/reject a pending epic/release plan (#629/#640).

    Reuses the shared pending-plan ledger under `.agentic/planning/pending/`.
    Does not create GitHub issues or cut releases. Revise stays feed-actionable
    until resubmit_er_plan (#630 parity).
    """
    from .planning import decide_pending_plan

    out = decide_pending_plan(
        plan_id,
        decision,
        note=note,
        decided_by=decided_by,
        base_dir=base_dir,
        archive=archive,
    )
    if not out.get("ok"):
        return out
    plan = out.get("plan") or {}
    kind = str(plan.get("kind") or "")
    # Specialize next steps for epic vs release
    if out.get("status") == "approved":
        if kind == "release":
            out["next_steps"] = [
                "Ensure open Next Release issue exists (or rename when packaging)",
                "Link scope Epics/Features via Development sidebar",
                "Draft notes skeleton from plan notes_skeleton / fragments",
                "Do not cut/tag/finalize without release ceremony + human approval",
            ]
        elif kind == "epic":
            out["next_steps"] = [
                "Create Epic issue from plan title/body/labels",
                "Create child Feature/Design/Research stubs with need:refinement",
                "Assign milestone / track label when known",
                "Do not implement children until refined ACs land",
            ]
    elif out.get("status") == "revise_requested":
        # Keep ER TUI on the still-pending plan
        plan["ask_user_question"] = er_plan_ask_user_payload(plan)
        plan["approval_prompt"] = plan["ask_user_question"].get("question")
        if plan.get("path"):
            try:
                Path(plan["path"]).write_text(
                    json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
            except OSError:
                pass
        out["plan"] = plan
        out["ask_user_question"] = plan["ask_user_question"]
        out["next_steps"] = [
            f"Resume ER session session_id={plan.get('session_id')}",
            f"Update plan then plate_er_planning_resubmit {plan.get('id')}",
            "Feed keeps revise_requested until resubmit + re-approve",
        ]
    return out


def list_active_er_sessions(
    *,
    base_dir: Path | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Incomplete durable epic/release sessions for feed resume."""
    root = base_dir if base_dir is not None else ER_SESSIONS_DIR
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("complete"):
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def er_planning_feed_items(
    *,
    pending_dir: Path | None = None,
    sessions_dir: Path | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Feed rows for pending/revise epic/release plans + incomplete ER sessions (#629/#640)."""
    from .planning import list_actionable_plans

    items: list[dict[str, Any]] = []
    for pl in list_actionable_plans(base_dir=pending_dir, limit=limit * 2):
        kind = str(pl.get("kind") or "")
        if kind not in ("epic", "release"):
            continue
        st = str(pl.get("status") or "pending_approval")
        pid = str(pl.get("id") or "er-plan")
        revised = st in ("revise_requested", "revised")
        auj = pl.get("ask_user_question") or er_plan_ask_user_payload(pl)
        # Ensure revise_requested has resubmit option even if stale payload
        if revised and not any(
            o.get("id") == "resubmit" for o in (auj.get("options") or [])
        ):
            auj = er_plan_ask_user_payload(pl)
        items.append(
            {
                "id": pid,
                "item_type": "er_planning_approval",
                "kind": kind,
                "title": pl.get("title") or f"Pending {kind} plan",
                "status": st,
                "version": pl.get("version") or 1,
                "rank": 13 if revised else 15,
                "impact": "high",
                "reason": (
                    f"Q&A {kind} plan revise requested — resubmit (#629/#640)"
                    if revised
                    else f"Q&A {kind} plan awaiting approval (#629/#640)"
                ),
                "approval_prompt": auj.get("question"),
                "prompt_segment": (
                    f"Resubmit {kind} plan {pid}: plate_er_planning_resubmit {pid}"
                    if revised
                    else (
                        f"Approve {kind} plan {pid}: plate_er_planning_decide "
                        f"{pid} approve|revise|reject"
                    )
                ),
                "summary": (pl.get("body") or "")[:240],
                "ask_user_question": auj,
                "source": "er_planning",
                "session_id": pl.get("session_id"),
            }
        )
    for sess in list_active_er_sessions(base_dir=sessions_dir, limit=max(1, limit // 2)):
        sid = str(sess.get("id") or "")
        kind = str(sess.get("kind") or "epic")
        turn = int(sess.get("turn") or 0)
        qs = _qs(kind)
        total = len(qs)
        nq = qs[turn] if turn < total else None
        items.append(
            {
                "id": sid,
                "item_type": "er_planning_session",
                "kind": kind,
                "title": f"Resume {kind} planning ({turn}/{total})",
                "status": "in_progress",
                "rank": 21,
                "impact": "medium",
                "reason": "Incomplete epic/release Q&A session",
                "prompt_segment": (
                    f"Resume ER session {sid}: plate_er_planning_answer session_id={sid}"
                ),
                "ask_user_question": er_question_payload(
                    nq, kind=kind, turn=turn, total=total
                )
                if nq
                else {
                    "question": f"ER session {sid} ready to build?",
                    "options": [
                        {
                            "id": "build",
                            "label": "Build plan",
                            "description": "plate_er_planning_build",
                        }
                    ],
                },
                "source": "er_planning",
                "session_id": sid,
            }
        )
    items.sort(key=lambda x: (int(x.get("rank") or 99), str(x.get("title") or "")))
    return items[: max(1, limit)]


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
