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
    if "created_at" not in out:
        out["created_at"] = out["updated_at"]
    # Ensure feed-ready approval payload is always present (#628/#630 harden)
    if not out.get("ask_user_question"):
        out["ask_user_question"] = pending_plan_ask_user_payload(out)
    if not out.get("approval_prompt"):
        out["approval_prompt"] = out["ask_user_question"].get("question")
    if not out.get("prompt_segment"):
        out["prompt_segment"] = (
            f"Present plan approval via ask_user_question for {out.get('id')}; "
            f"decide with plate_planning_decide / gh plate plan --decide."
        )
    path = root / f"{re.sub(r'[^a-zA-Z0-9._-]', '_', pid)}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out["path"] = str(path)
    return out


def get_pending_plan(plan_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Load one pending (or decided) plan by id."""
    if not plan_id:
        return None
    root = base_dir if base_dir is not None else PENDING_DIR
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", plan_id)
    path = root / f"{safe}.json"
    if not path.is_file():
        # prefix / glob
        if root.is_dir():
            matches = sorted(root.glob(f"{safe}*.json"))
            if not matches:
                # also search decided sibling
                decided = root.parent / "decided" if root.name == "pending" else root / "decided"
                if decided.is_dir():
                    matches = sorted(decided.glob(f"{safe}*.json"))
                if not matches:
                    return None
            path = matches[0]
        else:
            return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except (OSError, json.JSONDecodeError):
        return None


def pending_plan_ask_user_payload(plan: dict[str, Any]) -> dict[str, Any]:
    """TUI payload for approving a pending Q&A plan (#628/#630)."""
    pid = str(plan.get("id") or "plan")
    kind = str(plan.get("kind") or "feature")
    title = str(plan.get("title") or "untitled plan")[:80]
    status = str(plan.get("status") or "pending_approval")
    if status in ("revise_requested", "revised"):
        return {
            "item_id": pid,
            "item_type": "planning_approval",
            "kind": kind,
            "status": status,
            "question": f"Revise requested for {kind} plan: {title} — resubmit?",
            "options": [
                {
                    "id": "resubmit",
                    "label": "Resubmit for approval",
                    "description": (
                        f"plate_planning_resubmit {pid} (or gh plate plan --resubmit {pid}) "
                        "after updating plan body/session answers"
                    ),
                },
                {
                    "id": "resume_session",
                    "label": "Resume Q&A session",
                    "description": f"Continue session {plan.get('session_id') or 'n/a'} then rebuild plan",
                },
                {
                    "id": "reject",
                    "label": "Reject",
                    "description": f"plate_planning_decide {pid} reject — drop plan",
                },
            ],
            "multi_select": False,
        }
    return {
        "item_id": pid,
        "item_type": "planning_approval",
        "kind": kind,
        "status": status,
        "question": f"Approve {kind} plan: {title}?",
        "options": [
            {
                "id": "approve",
                "label": "Approve",
                "description": f"plate_planning_decide {pid} approve — create GitHub stubs (host)",
            },
            {
                "id": "revise",
                "label": "Revise",
                "description": f"plate_planning_decide {pid} revise — keep actionable until resubmit",
            },
            {
                "id": "reject",
                "label": "Reject",
                "description": f"plate_planning_decide {pid} reject — drop plan",
            },
        ],
        "multi_select": False,
    }


def _plan_history_path(plan_path: Path) -> Path:
    return plan_path.with_suffix(".history.jsonl")


def append_plan_history(
    plan_path: Path,
    event: dict[str, Any],
) -> None:
    """Append one decision/resubmit event to plan history sidecar."""
    hist = _plan_history_path(plan_path)
    hist.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", _now())
    with hist.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def get_plan_history(
    plan_id: str,
    *,
    base_dir: Path | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read decision history for a plan (pending or decided)."""
    plan = get_pending_plan(plan_id, base_dir=base_dir)
    if not plan or not plan.get("path"):
        return []
    hist_path = _plan_history_path(Path(plan["path"]))
    if not hist_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in hist_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-limit:]


def list_actionable_plans(
    *,
    base_dir: Path | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Pending + revise_requested plans still needing human feed action (#630 harden)."""
    root = base_dir if base_dir is not None else PENDING_DIR
    if not root.is_dir():
        return []
    actionable = []
    for f in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        st = str(data.get("status") or "pending_approval")
        if st not in ("pending_approval", "pending", "", "revise_requested", "revised"):
            continue
        data["path"] = str(f)
        actionable.append(data)
        if len(actionable) >= limit:
            break
    return actionable


def resubmit_pending_plan(
    plan_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    note: str = "",
    resubmitted_by: str = "human",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Re-open a revise_requested plan for approval (#630 parity with #632 resubmit).

    Bumps version, sets status=pending_approval, restores ask_user_question,
    appends history event. Does not create GitHub issues.
    """
    plan = get_pending_plan(plan_id, base_dir=base_dir)
    if not plan:
        return {"ok": False, "error": f"pending plan not found: {plan_id}"}
    status = str(plan.get("status") or "")
    if status not in ("revise_requested", "revised", "pending_approval", "pending", ""):
        return {
            "ok": False,
            "error": f"cannot resubmit plan in status={status}",
            "plan": plan,
        }
    if title is not None and str(title).strip():
        plan["title"] = str(title).strip()
    if body is not None:
        plan["body"] = body
    try:
        ver = int(plan.get("version") or 1)
    except (TypeError, ValueError):
        ver = 1
    plan["version"] = ver + 1
    plan["status"] = "pending_approval"
    plan["resubmitted_by"] = resubmitted_by
    plan["resubmit_note"] = note or None
    plan["updated_at"] = _now()
    plan["decided_at"] = None
    plan["decided_by"] = None
    plan["decision_note"] = None
    plan["archived"] = False
    plan["ask_user_question"] = pending_plan_ask_user_payload(plan)
    plan["approval_prompt"] = plan["ask_user_question"].get("question")
    plan["prompt_segment"] = (
        f"Present plan approval via ask_user_question for {plan.get('id')}; "
        f"decide with plate_planning_decide / gh plate plan --decide."
    )

    pending_root = base_dir if base_dir is not None else PENDING_DIR
    pending_root.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", str(plan.get("id") or plan_id))
    # Prefer keep path if still under pending; else write new pending file
    path = Path(plan.get("path") or (pending_root / f"{safe}.json"))
    if path.parent.name == "decided" or not str(path).startswith(str(pending_root)):
        path = pending_root / f"{safe}.json"
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plan["path"] = str(path)
    append_plan_history(
        path,
        {
            "decision": "resubmitted",
            "by": resubmitted_by,
            "note": note or None,
            "version": plan["version"],
            "plan_id": plan.get("id"),
        },
    )
    return {
        "ok": True,
        "id": plan.get("id"),
        "version": plan["version"],
        "status": plan["status"],
        "plan": plan,
        "history": get_plan_history(str(plan.get("id")), base_dir=base_dir, limit=10),
        "marker": plan.get("marker") or render_plan_marker(plan),
    }


def decide_pending_plan(
    plan_id: str,
    decision: str,
    *,
    note: str = "",
    decided_by: str = "human",
    base_dir: Path | None = None,
    archive: bool = True,
) -> dict[str, Any]:
    """Record approve|revise|reject on a pending plan and optionally archive to decided/.

    Approve does **not** auto-create GitHub issues (agent/host owns create);
    it marks the plan approved and returns create instructions from the plan body.

    revise keeps the plan in pending as ``revise_requested`` (actionable in feed)
    until ``resubmit_pending_plan`` re-opens approval (#630 harden / #632 parity).
    """
    plan = get_pending_plan(plan_id, base_dir=base_dir)
    if not plan:
        return {"ok": False, "error": f"pending plan not found: {plan_id}"}
    status = str(plan.get("status") or "")
    # Allow decide from pending; reject also allowed from revise_requested
    if status not in ("pending_approval", "pending", "", "revise_requested", "revised"):
        return {
            "ok": False,
            "error": f"plan already decided: status={status}",
            "plan": plan,
        }
    dec = (decision or "").lower().strip()
    mapping = {
        "approve": "approved",
        "approved": "approved",
        "revise": "revise_requested",
        "reject": "rejected",
        "rejected": "rejected",
    }
    if dec not in mapping:
        return {
            "ok": False,
            "error": f"invalid decision '{decision}'; use approve|revise|reject",
        }
    # Cannot approve while still revise_requested without resubmit
    if mapping[dec] == "approved" and status in ("revise_requested", "revised"):
        return {
            "ok": False,
            "error": "plan has revise_requested; resubmit before approve",
            "plan": plan,
            "next_steps": [
                f"plate_planning_resubmit {plan_id}",
                "Then plate_planning_decide approve",
            ],
        }
    plan["status"] = mapping[dec]
    plan["decided_by"] = decided_by
    plan["decision_note"] = note or None
    plan["decided_at"] = _now()
    plan["updated_at"] = plan["decided_at"]

    pending_root = base_dir if base_dir is not None else PENDING_DIR
    path = Path(plan.get("path") or (pending_root / f"{re.sub(r'[^a-zA-Z0-9._-]', '_', plan['id'])}.json"))
    path.parent.mkdir(parents=True, exist_ok=True)

    if plan["status"] == "revise_requested":
        # Stay actionable in pending for feed + resubmit
        plan["ask_user_question"] = pending_plan_ask_user_payload(plan)
        plan["approval_prompt"] = plan["ask_user_question"].get("question")
        plan["prompt_segment"] = (
            f"Plan {plan.get('id')} needs revision; resubmit via plate_planning_resubmit "
            f"or resume session {plan.get('session_id')}."
        )
        plan["archived"] = False
        path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        plan["path"] = str(path)
        append_plan_history(
            path,
            {
                "decision": "revise",
                "by": decided_by,
                "note": note or None,
                "version": plan.get("version") or 1,
                "plan_id": plan.get("id"),
            },
        )
    else:
        plan["ask_user_question"] = None
        path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        append_plan_history(
            path,
            {
                "decision": dec,
                "by": decided_by,
                "note": note or None,
                "version": plan.get("version") or 1,
                "plan_id": plan.get("id"),
                "status": plan["status"],
            },
        )
        if archive and plan["status"] in ("approved", "rejected"):
            decided_root = (
                pending_root.parent / "decided"
                if pending_root.name == "pending"
                else pending_root / "decided"
            )
            decided_root.mkdir(parents=True, exist_ok=True)
            dest = decided_root / path.name
            dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            # move history sidecar if present
            hist = _plan_history_path(path)
            if hist.is_file():
                try:
                    dest_hist = _plan_history_path(dest)
                    dest_hist.write_text(hist.read_text(encoding="utf-8"), encoding="utf-8")
                    hist.unlink()
                except OSError:
                    pass
            try:
                path.unlink()
            except OSError:
                pass
            plan["path"] = str(dest)
            plan["archived"] = True

    next_steps: list[str] = []
    if plan["status"] == "approved":
        next_steps = [
            "Create GitHub issue(s) from plan title/body/labels (agent/host)",
            "Attach milestone/Epic link from plan epic_link if present",
            "For linked Design/Research stubs, open as child issues with need:refinement",
            "Do not merge implementation without Feature PR ceremony",
        ]
    elif plan["status"] == "revise_requested":
        next_steps = [
            f"Resume or restart planning session session_id={plan.get('session_id')}",
            f"Update plan content then plate_planning_resubmit {plan.get('id')}",
            "Feed keeps revise_requested until resubmit + re-approve",
        ]
    else:
        next_steps = ["Plan rejected; no GitHub issues created."]

    return {
        "ok": True,
        "plan": plan,
        "decision": dec,
        "status": plan["status"],
        "next_steps": next_steps,
        "history": get_plan_history(str(plan.get("id")), base_dir=base_dir, limit=10),
        "marker": plan.get("marker") or render_plan_marker(plan),
    }


def list_active_planning_sessions(
    *,
    base_dir: Path | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Incomplete durable sessions that can resume in the feed."""
    root = base_dir if base_dir is not None else SESSIONS_DIR
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


def planning_feed_items(
    *,
    pending_dir: Path | None = None,
    sessions_dir: Path | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Feed rows for pending/revise plan approvals + incomplete planning sessions (#628/#630)."""
    items: list[dict[str, Any]] = []
    # Actionable = pending_approval + revise_requested (#630 harden)
    for pl in list_actionable_plans(base_dir=pending_dir, limit=limit):
        st = str(pl.get("status") or "pending_approval")
        # Epic/release pending plans are owned by er_planning_feed_items (#629/#640)
        kind = str(pl.get("kind") or "feature")
        if kind in ("epic", "release"):
            continue
        auj = pl.get("ask_user_question") or pending_plan_ask_user_payload(pl)
        pid = str(pl.get("id") or "plan")
        revised = st in ("revise_requested", "revised")
        items.append(
            {
                "id": pid,
                "item_type": "planning_approval",
                "kind": kind,
                "title": pl.get("title") or "Pending plan",
                "status": st,
                "version": pl.get("version") or 1,
                "rank": 14 if revised else 16,
                "impact": "high",
                "reason": (
                    "Q&A plan revise requested — resubmit (#630)"
                    if revised
                    else "Q&A plan awaiting approval (#628/#630)"
                ),
                "approval_prompt": auj.get("question"),
                "prompt_segment": pl.get("prompt_segment")
                or (
                    f"Resubmit plan {pid}: plate_planning_resubmit {pid}"
                    if revised
                    else f"Approve plan {pid}: plate_planning_decide {pid} approve|revise|reject"
                ),
                "summary": (pl.get("body") or "")[:240],
                "ask_user_question": auj,
                "source": "planning",
                "session_id": pl.get("session_id"),
            }
        )
    for sess in list_active_planning_sessions(base_dir=sessions_dir, limit=max(1, limit // 2)):
        sid = str(sess.get("id") or "")
        kind = str(sess.get("kind") or "feature")
        turn = int(sess.get("turn") or 0)
        qs = _questions_for(kind)
        total = len(qs)
        nq = qs[turn] if turn < total else None
        items.append(
            {
                "id": sid,
                "item_type": "planning_session",
                "kind": kind,
                "title": f"Resume {kind} planning ({turn}/{total})",
                "status": "in_progress",
                "rank": 22,
                "impact": "medium",
                "reason": "Incomplete Q&A planning session",
                "prompt_segment": (
                    f"Resume session {sid}: plate_planning_answer session_id={sid}"
                ),
                "ask_user_question": question_ask_user_payload(
                    nq, kind=kind, turn=turn, total=total
                )
                if nq
                else {
                    "question": f"Session {sid} ready to build?",
                    "options": [
                        {
                            "id": "build",
                            "label": "Build plan",
                            "description": "plate_planning_build",
                        }
                    ],
                },
                "source": "planning",
                "session_id": sid,
            }
        )
    items.sort(key=lambda x: (int(x.get("rank") or 99), str(x.get("title") or "")))
    return items[: max(1, limit)]


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


# Heuristic planning costs (#634 / #628 / #630).
_PLAN_SESSION_BASE = 4000
_PLAN_PRODUCT_EXTRA = 2000
_PLAN_BUILD_BASE = 5000
_PLAN_PRODUCT_BUILD_EXTRA = 2500


def estimate_planning_cost(
    *,
    kind: str = "feature",
    phase: str = "start",
) -> dict[str, Any]:
    """Advisory token estimate for Q&A planning start or build (#634/#628/#630)."""
    k = "product" if (kind or "").lower() == "product" else "feature"
    phase_n = (phase or "start").lower()
    if phase_n not in ("start", "build"):
        phase_n = "start"
    if phase_n == "start":
        tokens = _PLAN_SESSION_BASE + (_PLAN_PRODUCT_EXTRA if k == "product" else 0)
    else:
        tokens = _PLAN_BUILD_BASE + (_PLAN_PRODUCT_BUILD_EXTRA if k == "product" else 0)
    return {
        "ok": True,
        "kind": k,
        "phase": phase_n,
        "estimated_tokens": int(tokens),
        "breakdown": {
            "base": _PLAN_SESSION_BASE if phase_n == "start" else _PLAN_BUILD_BASE,
            "product_extra": (
                (_PLAN_PRODUCT_EXTRA if phase_n == "start" else _PLAN_PRODUCT_BUILD_EXTRA)
                if k == "product"
                else 0
            ),
        },
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine enforce hard ceilings.",
            "start_planning_session / build_plan_from_session hydrate remaining when use_live_budget.",
        ],
    }


def _planning_budget_gate(
    *,
    kind: str,
    phase: str,
    budget_remaining: int | None,
    use_live_budget: bool,
    budget_base_dir: Path | None = None,
) -> tuple[dict[str, Any], int | None, list[str], dict[str, Any] | None]:
    cost_est = estimate_planning_cost(kind=kind, phase=phase)
    est = int(cost_est.get("estimated_tokens") or 0)
    notes: list[str] = []
    effective = budget_remaining
    if effective is None and use_live_budget:
        try:
            from .autonomy import durable_budget_surface_pause, get_budget_snapshot

            snap = get_budget_snapshot(
                estimate_tokens=est,
                base_dir=budget_base_dir,
            )
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective = int(rem)
                notes.append(
                    f"budget hydrated: remaining_tokens={effective} "
                    f"pressure={snap.get('budget_pressure')}"
                )
            # #634/#873: hard-block on durable would_pause / critical pressure
            # even when est still fits remaining (risk-independent surface rails).
            surface = durable_budget_surface_pause(snap)
            if surface.get("pause"):
                notes.append(surface.get("reason") or "blocked: durable budget rails")
                rem_out = (
                    int(effective)
                    if effective is not None
                    else (surface.get("remaining") if surface.get("remaining") is not None else 0)
                )
                return (
                    cost_est,
                    int(rem_out) if rem_out is not None else effective,
                    notes,
                    {
                        "ok": False,
                        "blocked": True,
                        "reason": "budget",
                        "error": (
                            f"budget: durable rails pause planning "
                            f"(pressure={surface.get('pressure')} remaining={rem_out})"
                        ),
                        "cost_estimate_tokens": est,
                        "budget_remaining": int(rem_out) if rem_out is not None else 0,
                        "budget_pressure": surface.get("pressure"),
                        "would_pause_next_cycle": True,
                        "cost_estimate": cost_est,
                        "notes": notes,
                    },
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


def start_planning_session(
    kind: str = "feature",
    *,
    base_dir: Path | None = None,
    persist: bool = True,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Begin a Q&A planning session; returns first question + session state.

    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    Charge durable spend only when ``persist=True`` (preview sessions are free).
    """
    k = "product" if kind == "product" else "feature"
    budget_base: Path | None = None
    if base_dir is not None:
        budget_base = Path(base_dir) / "budget"
    cost_est, effective_remaining, budget_notes, blocked = _planning_budget_gate(
        kind=k,
        phase="start",
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
        budget_base_dir=budget_base,
    )
    if blocked is not None:
        return blocked
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
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    out: dict[str, Any] = {
        "ok": True,
        "session": sdict,
        "session_id": sdict.get("id"),
        "total_questions": len(qs),
        "next_question": nq,
        "cost_estimate_tokens": est_tokens,
        "budget_remaining": effective_remaining,
        "cost_estimate": cost_est,
        "notes": list(budget_notes),
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
    if persist and use_live_budget and est_tokens > 0:
        try:
            from .autonomy import apply_live_budget_charge

            apply_live_budget_charge(
                out,
                tokens=est_tokens,
                use_live_budget=use_live_budget,
                action_kind="planning_start",
                reason=f"start_planning_session:{k}:{sdict.get('id')}",
                base_dir=budget_base,
            )
        except Exception:
            pass
    elif (not persist) and use_live_budget and est_tokens > 0:
        out["notes"] = list(out.get("notes") or []) + [
            f"preview: skipped budget charge of est {est_tokens} tokens"
        ]
    return out


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
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Build plan from session; optionally persist under planning_root/pending/.

    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    """
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
    budget_base: Path | None = None
    if planning_root is not None:
        budget_base = Path(planning_root) / "budget"
    cost_est, effective_remaining, budget_notes, blocked = _planning_budget_gate(
        kind=str(kind),
        phase="build",
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
        budget_base_dir=budget_base,
    )
    if blocked is not None:
        return blocked
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
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    out: dict[str, Any] = {
        "ok": True,
        "plan": plan,
        "session_complete": complete,
        "ask_user_question": approval_payload,
        "pending_path": plan.get("path"),
        "cost_estimate_tokens": est_tokens,
        "budget_remaining": effective_remaining,
        "cost_estimate": cost_est,
        "notes": list(budget_notes),
    }
    if persist_pending and use_live_budget and est_tokens > 0:
        try:
            from .autonomy import apply_live_budget_charge

            apply_live_budget_charge(
                out,
                tokens=est_tokens,
                use_live_budget=use_live_budget,
                action_kind="planning_build",
                reason=f"build_plan:{kind}:{sid or plan.get('id')}",
                base_dir=budget_base,
            )
        except Exception:
            pass
    elif (not persist_pending) and use_live_budget and est_tokens > 0:
        out["notes"] = list(out.get("notes") or []) + [
            f"preview: skipped budget charge of est {est_tokens} tokens"
        ]
    return out


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
