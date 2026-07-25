"""Unified Questions + Tasks feed for the endless user surface (#631).

Proactively ranks open Question and Task issues (plus optional autonomy/dashboard
signals) into a single feed for TUI / CLI / MCP / Copilot presentation.

v1 slice:
- Harvest open Questions (label:Question) and Tasks (label:Task) via GitHub search
- Rank: blocking/high-need Tasks and Questions first, then recency
- Emit presentation-ready items (title, type, badges, prompt_segment)
- Integrate optional what_next + autonomy open_human_checkpoints when available
- Pure helpers accept injected items for offline unit tests

Deepen (#631/#660):
- Rank open Project Manager assignments from the durable `.agentic/pm` queue
  (proposed/delegated) so the endless feed surfaces persona work packets with
  ask_user_question payloads and plate_pm_complete follow-through.

Follow-ups: Projects v2 ranking, media badges.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from .github_client import GhClient
from .health import resolve_repo

FEED_MARKER_BEGIN = "<!-- PLATE-FEED:BEGIN -->"
FEED_MARKER_END = "<!-- PLATE-FEED:END -->"


@dataclass
class FeedItem:
    id: str
    item_type: str  # question | task | checkpoint | process | signal
    number: int | None
    title: str
    rank: int
    impact: str  # low | medium | high | critical
    badges: list[str] = field(default_factory=list)
    url: str | None = None
    body_excerpt: str = ""
    labels: list[str] = field(default_factory=list)
    prompt_segment: str = ""
    reason: str = ""
    updated_at: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _client(client: GhClient | None = None) -> GhClient:
    return client or GhClient()


def _excerpt(text: str | None, n: int = 160) -> str:
    if not text:
        return ""
    t = " ".join(str(text).split())
    return t if len(t) <= n else t[: n - 1] + "…"


def _labels(issue: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for lab in issue.get("labels") or []:
        if isinstance(lab, dict):
            name = lab.get("name")
            if name:
                out.append(str(name))
        else:
            out.append(str(lab))
    return out


def _impact_from_labels(labels: list[str], item_type: str) -> str:
    lower = {x.lower() for x in labels}
    if "risk:critical" in lower or "need:security-review" in lower:
        return "critical"
    if "risk:high" in lower or "need:human-review" in lower or "status:blocked" in lower:
        return "high"
    if item_type == "task":
        return "high"  # human Tasks default high attention
    if "risk:low" in lower:
        return "low"
    return "medium"


def _rank_score(item_type: str, impact: str, labels: list[str], updated_at: str) -> int:
    """Lower rank = higher priority in feed."""
    base = {"critical": 5, "high": 20, "medium": 40, "low": 60}.get(impact, 40)
    lower = {x.lower() for x in labels}
    if item_type == "task":
        base -= 8
    if item_type == "question" and ("blocking" in " ".join(lower) or any("block" in x for x in lower)):
        base -= 10
    if "need:human-review" in lower:
        base -= 12
    if "status:ready-to-work" in lower:
        base -= 3
    if "status:stub" in lower or "need:refinement" in lower:
        base += 5  # slightly deprioritize stubs
    # mild recency boost (newer = lower rank)
    try:
        if updated_at:
            # ISO timestamps compare lexicographically when Zulu
            age_hint = updated_at[:10]
            # not a real age calc offline; keep stable order by string
            _ = age_hint
    except Exception:
        pass
    return max(1, base)


def issue_to_feed_item(issue: dict[str, Any], item_type: str) -> FeedItem:
    labels = _labels(issue)
    impact = _impact_from_labels(labels, item_type)
    number = issue.get("number")
    title = str(issue.get("title") or f"{item_type} #{number}")
    updated = str(issue.get("updated_at") or issue.get("created_at") or "")
    rank = _rank_score(item_type, impact, labels, updated)
    badges = [item_type, impact]
    lower_labs = {x.lower() for x in labels}
    for key in ("need:human-review", "status:blocked", "risk:high", "risk:critical", "status:ready-to-work"):
        if key in lower_labs:
            badges.append(key)
    # #643 driver labels: surface co-existence ownership in feed
    for dlab in ("driver:human", "driver:agent", "driver:collaborative"):
        if dlab in lower_labs:
            badges.append(dlab)
            if dlab == "driver:human":
                rank = max(1, rank - 8)  # human-driven items surface earlier
            break
    if item_type == "question":
        prompt = (
            f"Present Question #{number} via native ask_user_question with minimal front-matter. "
            f"Title: {title}. After answer: plate_record_answer + contemplate; quiet ops."
        )
        reason = "Open informational goal (Question)"
    else:
        prompt = (
            f"Surface Task #{number} as human-only action. Do not complete agent-side. "
            f"Title: {title}. Wait for <!-- PLATE-TASK-CLOSED --> completion signal."
        )
        reason = "Open human Task"
    if "driver:human" in lower_labs:
        prompt += " driver:human — agents pause auto-delegation; human owns next steps (#643)."
        reason = f"{reason}; human driving"
    return FeedItem(
        id=f"{item_type}-{number}",
        item_type=item_type,
        number=int(number) if number is not None else None,
        title=title,
        rank=rank,
        impact=impact,
        badges=badges,
        url=issue.get("html_url"),
        body_excerpt=_excerpt(issue.get("body")),
        labels=labels,
        prompt_segment=prompt,
        reason=reason,
        updated_at=updated,
        source="github_search",
    )


def fetch_open_questions(
    repo: str | None = None,
    client: GhClient | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    target = resolve_repo(repo)
    c = _client(client)
    q = f"repo:{target} is:issue is:open label:Question"
    data = c.api(f"search/issues?q={quote_plus(q)}&per_page={min(limit, 50)}")
    return list((data or {}).get("items") or [])


def fetch_open_tasks(
    repo: str | None = None,
    client: GhClient | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    target = resolve_repo(repo)
    c = _client(client)
    q = f"repo:{target} is:issue is:open label:Task"
    data = c.api(f"search/issues?q={quote_plus(q)}&per_page={min(limit, 50)}")
    return list((data or {}).get("items") or [])


def _checkpoint_to_feed_item(cp: str | dict[str, Any], index: int) -> FeedItem:
    """Normalize string or structured checkpoint into a FeedItem (#648)."""
    if isinstance(cp, dict):
        cid = str(cp.get("id") or f"checkpoint-{index}")
        title = str(cp.get("title") or cp.get("id") or "Human checkpoint")
        impact = str(cp.get("impact") or "high")
        action = str(cp.get("action_kind") or "")
        shadow = cp.get("shadow_id") or ""
        reason_txt = str(cp.get("reason") or "Open autonomy checkpoint")
        prompt = (
            f"Open human checkpoint id={cid}: {title}. "
            f"Present via ask_user_question (approve|revise|reject). "
            f"Then: plate_checkpoint_decide / gh plate checkpoint --decide {cid} --decision approve|revise|reject. "
            f"After approve, resume gate with checkpoint_id={cid}"
            + (f" shadow_ack={shadow}" if shadow else "")
            + (f" action_kind={action}" if action else "")
            + ". Do not bypass."
        )
        return FeedItem(
            id=cid,
            item_type="checkpoint",
            number=None,
            title=title,
            rank=10 + index,
            impact=impact if impact in ("low", "medium", "high", "critical") else "high",
            badges=["checkpoint", impact or "high"],
            prompt_segment=prompt,
            reason=reason_txt,
            source="checkpoint_ledger",
            body_excerpt=str(cp.get("reason") or "")[:240],
        )
    # Legacy string form from autonomy_status open_human_checkpoints
    text = str(cp)
    # Prefer "id: title" parsing when present
    cid = f"checkpoint-{index}"
    title = text
    if ":" in text:
        left, right = text.split(":", 1)
        if left.strip():
            cid = left.strip()
            title = right.strip() or text
    return FeedItem(
        id=cid,
        item_type="checkpoint",
        number=None,
        title=title,
        rank=12 + index,
        impact="high",
        badges=["checkpoint", "high"],
        prompt_segment=(
            f"Open human checkpoint: {text}. Use plate_checkpoint_decide / gh plate checkpoint "
            f"--decide {cid} after user judgment; do not bypass."
        ),
        reason="Open autonomy checkpoint",
        source="autonomy_status",
    )


def ask_user_question_payload(item: FeedItem | dict[str, Any]) -> dict[str, Any]:
    """Native TUI payload for one feed item (#631 host bridge).

    Hosts should call ask_user_question with `question` + `options` (labels only for
    multi-choice UIs). Option ids encode the intended follow-through for agents.
    """
    if isinstance(item, FeedItem):
        d = item.to_dict()
    else:
        d = dict(item)
    itype = str(d.get("item_type") or d.get("type") or "signal")
    title = str(d.get("title") or "Feed item")
    number = d.get("number")
    num = f"#{number} " if number else ""
    cid = str(d.get("id") or "")

    if itype == "question":
        question = f"Answer Question {num}{title}".strip()
        options = [
            {"id": "answer_now", "label": "Answer now", "description": "Capture answer + provenance; run contemplation."},
            {"id": "defer", "label": "Defer", "description": "Leave open; surface again later."},
            {"id": "block", "label": "Mark blocking", "description": "Treat as hard blocker for related work."},
        ]
    elif itype == "task":
        question = f"Human Task {num}{title} — status?".strip()
        options = [
            {"id": "show_instructions", "label": "Show instructions", "description": "Display body; human acts externally."},
            {"id": "done_signal", "label": "Done signal ready", "description": "Human will post <!-- PLATE-TASK-CLOSED --> (agent never fabricates)."},
            {"id": "still_blocked", "label": "Still blocked", "description": "Keep open; no auto-close."},
        ]
    elif itype == "checkpoint":
        question = f"Checkpoint {cid}: {title}"
        options = [
            {"id": "approve", "label": "Approve", "description": f"plate_checkpoint_decide / gh plate checkpoint --decide {cid} --decision approve"},
            {"id": "revise", "label": "Revise", "description": "Request changes; keep autonomy paused."},
            {"id": "reject", "label": "Reject", "description": "Reject gated action; do not proceed."},
        ]
    elif itype in ("approval", "design", "research"):
        question = f"Approve artifact: {title}"
        options = [
            {"id": "approve", "label": "Approve", "description": "plate_artifact_decide approve (authoritative)."},
            {"id": "revise", "label": "Revise", "description": "Request new version."},
            {"id": "reject", "label": "Reject", "description": "Reject proposal."},
        ]
    elif itype in ("pm_assignment", "assignment"):
        agent = str(d.get("agent_name") or d.get("agent_id") or "persona")
        aid = cid or str(d.get("assignment_id") or "asg")
        question = f"PM assignment: {title} → {agent}?"
        options = [
            {
                "id": "approve_run",
                "label": "Approve & run",
                "description": f"Execute packet for {agent}; then plate_pm_complete {aid} --status done",
            },
            {
                "id": "defer",
                "label": "Defer",
                "description": "Leave proposed; next PM cycle may re-rank.",
            },
            {
                "id": "cancel",
                "label": "Cancel",
                "description": f"plate_pm_complete {aid} --status cancelled",
            },
        ]
    else:
        question = f"{itype}: {title}"
        options = [
            {"id": "act", "label": "Act on this", "description": str(d.get("prompt_segment") or d.get("reason") or "Follow prompt_segment.")},
            {"id": "skip", "label": "Skip for now", "description": "Leave in feed; pick next item."},
        ]

    return {
        "item_id": cid,
        "item_type": itype,
        "number": number,
        "question": question,
        "options": options,
        "prompt_segment": str(d.get("prompt_segment") or ""),
        "multi_select": False,
    }


def _pm_assignment_to_feed_item(asg: dict[str, Any], index: int) -> FeedItem:
    """Normalize a PM queue assignment into a FeedItem (#660 → #631)."""
    aid = str(asg.get("assignment_id") or f"asg-{index}")
    title = str(asg.get("work_title") or asg.get("work_id") or "PM work")
    agent = str(asg.get("agent_name") or asg.get("agent_id") or "persona")
    work_type = str(asg.get("work_type") or "implement")
    status = str(asg.get("status") or "proposed")
    impact = "high" if asg.get("requires_checkpoint") else "medium"
    if str(asg.get("packet", {}).get("impact") or "").lower() in ("high", "critical"):
        impact = str(asg["packet"]["impact"]).lower()
    rank = 18 + index if status == "delegated" else 22 + index
    if asg.get("requires_checkpoint"):
        rank = 12 + index
    packet = asg.get("packet") if isinstance(asg.get("packet"), dict) else {}
    prompt = str(
        packet.get("prompt_segment")
        or asg.get("rationale")
        or f"Run PM assignment {aid} as {agent} ({work_type})."
    )
    if asg.get("checkpoint_id"):
        prompt += f" Open checkpoint {asg.get('checkpoint_id')} before execute."
    prompt += f" On finish: plate_pm_complete / gh plate pm --complete {aid}."
    return FeedItem(
        id=aid,
        item_type="pm_assignment",
        number=None,
        title=f"[{status}] {title} → {agent}",
        rank=rank,
        impact=impact,
        badges=["pm", status, work_type, impact],
        prompt_segment=prompt,
        reason=str(asg.get("rationale") or f"PM queue ({status})"),
        source="pm_queue",
        body_excerpt=str(packet.get("task_summary") or title)[:240],
        labels=[work_type, status],
    )


def build_feed_items(
    *,
    questions: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    process_items: list[dict[str, Any]] | None = None,
    checkpoints: list[str | dict[str, Any]] | None = None,
    signal_items: list[dict[str, Any]] | None = None,
    approval_items: list[dict[str, Any]] | None = None,
    pm_assignments: list[dict[str, Any]] | None = None,
) -> list[FeedItem]:
    items: list[FeedItem] = []
    for iss in questions or []:
        items.append(issue_to_feed_item(iss, "question"))
    for iss in tasks or []:
        items.append(issue_to_feed_item(iss, "task"))
    for i, cp in enumerate(checkpoints or []):
        items.append(_checkpoint_to_feed_item(cp, i))
    for i, asg in enumerate(pm_assignments or []):
        items.append(_pm_assignment_to_feed_item(asg, i))
    for i, ap in enumerate(approval_items or []):
        pid = str(ap.get("id") or f"approval-{i}")
        kind = str(ap.get("kind") or "design")
        title = str(ap.get("title") or pid)
        items.append(
            FeedItem(
                id=pid,
                item_type="approval",
                number=None,
                title=f"[{kind}] {title}",
                rank=14 + i,
                impact="high",
                badges=["approval", kind, str(ap.get("status") or "pending")],
                prompt_segment=str(
                    ap.get("approval_prompt")
                    or ap.get("prompt_segment")
                    or (
                        f"Present {kind} artifact '{title}' via ask_user_question; "
                        f"decide with plate_artifact_decide {pid}."
                    )
                ),
                reason="Pending Design/Research approval (#632)",
                source="approvals_ledger",
                body_excerpt=str(ap.get("summary") or ap.get("path") or "")[:240],
            )
        )
    for i, sig in enumerate(signal_items or []):
        stype = str(sig.get("type") or "signal")
        items.append(
            FeedItem(
                id=str(sig.get("id") or f"signal-{i}"),
                item_type="signal" if stype in ("drift", "cost_hotspot", "signal") else stype,
                number=sig.get("issue_number"),
                title=str(sig.get("title") or "signal"),
                rank=int(sig.get("rank") or (45 + i)),
                impact=str(sig.get("impact") or "medium"),
                badges=[stype, str(sig.get("impact") or "medium")],
                prompt_segment=str(
                    sig.get("prompt_segment")
                    or f"{sig.get('reason') or stype}: {sig.get('title')}"
                ),
                reason=str(sig.get("reason") or "cost/risk dashboard"),
                source=str(sig.get("source") or "cost_dashboard"),
            )
        )
    for i, p in enumerate(process_items or []):
        items.append(
            FeedItem(
                id=f"process-{i}",
                item_type="process",
                number=None,
                title=str(p.get("title") or p.get("next_action") or "process step"),
                rank=int(p.get("rank") or (55 + i)),
                impact=str(p.get("impact") or "medium"),
                badges=["process"],
                prompt_segment=str(p.get("prompt_segment") or p.get("title") or ""),
                reason=str(p.get("reason") or "process recommendation"),
                source=str(p.get("source") or "what_next"),
            )
        )
    items.sort(key=lambda x: (x.rank, x.item_type, x.title.lower()))
    return items


def get_user_feed(
    repo: str | None = None,
    client: GhClient | None = None,
    *,
    limit: int = 10,
    include_process: bool = True,
    include_autonomy: bool = True,
    questions: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return ranked Q+Task feed for endless user surfacing (#631)."""
    target = resolve_repo(repo)
    c = client
    q_items = questions
    t_items = tasks
    if q_items is None:
        try:
            q_items = fetch_open_questions(repo=target, client=c, limit=30)
        except Exception as exc:
            q_items = []
            fetch_error_q = str(exc)
        else:
            fetch_error_q = None
    else:
        fetch_error_q = None
    if t_items is None:
        try:
            t_items = fetch_open_tasks(repo=target, client=c, limit=30)
        except Exception as exc:
            t_items = []
            fetch_error_t = str(exc)
        else:
            fetch_error_t = None
    else:
        fetch_error_t = None

    process_items: list[dict[str, Any]] = []
    if include_process:
        try:
            # Lazy import to avoid circular MCP dependency in tests
            from .mcp_server import _what_next

            wn = _what_next(target, "general")
            process_items.append(
                {
                    "title": wn.get("next_action"),
                    "prompt_segment": wn.get("prompt_segment"),
                    "reason": wn.get("rationale") or "plate_what_next",
                    "rank": 50,
                    "impact": "medium",
                    "source": "what_next",
                }
            )
        except Exception:
            pass

    checkpoints: list[str | dict[str, Any]] = []
    signal_items: list[dict[str, Any]] = []
    autonomy_snap: dict[str, Any] = {}
    if include_autonomy:
        try:
            from .checkpoint import list_open_checkpoints

            rich = list_open_checkpoints(limit=20)
            if rich:
                checkpoints = rich
            else:
                from .autonomy import get_autonomy_status

                autonomy_snap = get_autonomy_status(target)
                checkpoints = list(autonomy_snap.get("open_human_checkpoints") or [])
        except Exception:
            try:
                from .autonomy import get_autonomy_status

                autonomy_snap = get_autonomy_status(target)
                checkpoints = list(autonomy_snap.get("open_human_checkpoints") or [])
            except Exception:
                autonomy_snap = {}
        # #653: merge cost/risk dashboard signals into endless feed (skip duplicate checkpoints)
        try:
            from .costs import get_cost_dashboard

            dash = get_cost_dashboard(repo=target, autonomy_status=autonomy_snap or None)
            for fi in dash.get("feed_items") or []:
                if fi.get("type") == "checkpoint":
                    continue  # already from list_open_checkpoints
                signal_items.append({**fi, "source": "cost_dashboard"})
            if not autonomy_snap:
                autonomy_snap = {
                    "burn_rate": (dash.get("projections") or {}).get("burn_rate_pct"),
                    "autopilot_score": (dash.get("risk") or {}).get("autopilot_score"),
                    "budget_remaining_tokens": (dash.get("budget") or {}).get("remaining_tokens"),
                }
        except Exception:
            pass

    approval_items: list[dict[str, Any]] = []
    try:
        from .design_research_approval import list_proposals, presentation_for_feed

        for prop in list_proposals(status="pending", limit=15):
            shaped = presentation_for_feed(prop)
            approval_items.append({
                "id": shaped.get("id") or prop.get("id"),
                "kind": shaped.get("kind") or prop.get("kind"),
                "title": shaped.get("title") or prop.get("title"),
                "status": prop.get("status") or "pending",
                "approval_prompt": shaped.get("approval_prompt"),
                "prompt_segment": shaped.get("prompt_segment"),
                "summary": prop.get("summary") or "",
                "ask_user_question": shaped.get("ask_user_question"),
            })
    except Exception:
        approval_items = []
    # #628/#630 pending Q&A plans awaiting approval
    try:
        from .planning import list_pending_plans

        for pl in list_pending_plans(limit=10):
            approval_items.append({
                "id": pl.get("id"),
                "kind": pl.get("kind") or "feature",
                "title": pl.get("title") or "Pending plan",
                "status": pl.get("status") or "pending_approval",
                "approval_prompt": pl.get("approval_prompt") or pl.get("prompt_segment"),
                "summary": (pl.get("body") or "")[:200],
            })
    except Exception:
        pass

    # #660 PM durable queue → endless feed (proposed + delegated only)
    pm_assignments: list[dict[str, Any]] = []
    if include_autonomy:
        try:
            from .pm import list_pm_queue

            for st in ("proposed", "delegated"):
                for row in list_pm_queue(status=st, limit=20):
                    pm_assignments.append(row)
        except Exception:
            pm_assignments = []

    # #651 open path/branch ownership pauses → feed signals
    try:
        from .collab import ownership_feed_items

        for own in ownership_feed_items(limit=10):
            signal_items.append(
                {
                    "id": own.get("id"),
                    "type": "collab_ownership",
                    "title": own.get("title"),
                    "rank": 18,
                    "impact": own.get("impact") or "high",
                    "reason": own.get("reason") or "Human path/branch ownership pause (#651)",
                    "prompt_segment": (
                        f"{own.get('title')}. "
                        f"Agents skip overlapping work. "
                        f"Release: plate_collab_ownership_release / gh plate collab --release {own.get('id')}."
                    ),
                    "source": "collab_ownership",
                    "ask_user_question": own.get("ask_user_question"),
                }
            )
    except Exception:
        pass

    # #644 active multi-agent handoffs → feed signals
    try:
        from .fleet import handoff_feed_items

        for ho in handoff_feed_items(limit=10):
            signal_items.append(
                {
                    "id": ho.get("id"),
                    "type": "fleet_handoff",
                    "title": ho.get("title"),
                    "rank": 16,
                    "impact": ho.get("impact") or "medium",
                    "reason": ho.get("reason") or "Fleet handoff (#644)",
                    "prompt_segment": (
                        f"{ho.get('title')}: {str(ho.get('task') or '')[:100]}. "
                        f"Complete: plate_fleet_complete / gh plate fleet --complete {ho.get('id')}."
                    ),
                    "source": "fleet_handoffs",
                    "ask_user_question": ho.get("ask_user_question"),
                }
            )
    except Exception:
        pass

    # #642 pending discussion/market monitor proposals → feed signals
    try:
        from .monitoring import monitoring_feed_items

        for mp in monitoring_feed_items(limit=10):
            signal_items.append(
                {
                    "id": mp.get("id"),
                    "type": "monitor_proposal",
                    "title": mp.get("title"),
                    "rank": 20,
                    "impact": mp.get("impact") or "medium",
                    "reason": mp.get("reason") or "Scheduled monitoring proposal (#642)",
                    "prompt_segment": (
                        f"{mp.get('title')}. "
                        f"Decide: plate_monitor_decide / gh plate monitor --decide {mp.get('id')} approve|reject."
                    ),
                    "source": "monitoring",
                    "ask_user_question": mp.get("ask_user_question"),
                }
            )
    except Exception:
        pass

    # #637 stub drafts awaiting create/refine → feed signals
    try:
        from .stubs import stubs_feed_items

        for sd in stubs_feed_items(limit=10):
            signal_items.append(
                {
                    "id": sd.get("id"),
                    "type": "stub_draft",
                    "title": sd.get("title"),
                    "rank": 22,
                    "impact": sd.get("impact") or "medium",
                    "reason": sd.get("reason") or "Stub draft (#637)",
                    "prompt_segment": (
                        f"{sd.get('title')}. "
                        f"Create: plate_stub_create {sd.get('id')}; refine: plate_stub_refine."
                    ),
                    "source": "stubs",
                    "ask_user_question": sd.get("ask_user_question"),
                }
            )
    except Exception:
        pass

    items = build_feed_items(
        questions=q_items,
        tasks=t_items,
        process_items=process_items,
        checkpoints=checkpoints,
        signal_items=signal_items,
        approval_items=approval_items,
        pm_assignments=pm_assignments,
    )
    top = items[: max(1, limit)]
    # Prefer pre-shaped ask_user_question from approval/plan/PM sources when present
    pre_payloads: dict[str, Any] = {}
    for ap in approval_items:
        if ap.get("id") and ap.get("ask_user_question"):
            pre_payloads[str(ap["id"])] = ap["ask_user_question"]
    for asg in pm_assignments:
        aid = asg.get("assignment_id")
        if aid and asg.get("ask_user_question"):
            pre_payloads[str(aid)] = asg["ask_user_question"]

    presentation = []
    for i, it in enumerate(top):
        auj = pre_payloads.get(it.id) or ask_user_question_payload(it)
        row = {
            "index": i + 1,
            "id": it.id,
            "type": it.item_type,
            "number": it.number,
            "title": it.title,
            "badges": it.badges,
            "impact": it.impact,
            "url": it.url,
            "prompt_segment": it.prompt_segment,
            "reason": it.reason,
            "ask_user_question": auj,
        }
        presentation.append(row)
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "repo": target,
        "generated_for": "user_feed",
        "issue_refs": ["#631", "#654", "#656", "#632", "#660"],
        "timestamp": ts,
        "counts": {
            "questions": len(q_items or []),
            "tasks": len(t_items or []),
            "checkpoints": len(checkpoints),
            "approvals": len(approval_items),
            "pm_assignments": len(pm_assignments),
            "signals": len(signal_items),
            "process": len(process_items),
            "returned": len(top),
        },
        "items": [it.to_dict() for it in top],
        "presentation": presentation,
        "autonomy": {
            "risk_tolerance": autonomy_snap.get("risk_tolerance"),
            "enabled": autonomy_snap.get("enabled"),
            "autopilot_score": autonomy_snap.get("autopilot_score"),
            "burn_rate": autonomy_snap.get("burn_rate"),
        },
        "errors": {
            "questions": fetch_error_q,
            "tasks": fetch_error_t,
        },
        "tui_hint": (
            "Present presentation[].ask_user_question one-at-a-time via native ask_user_question "
            "(question + options labels). For Task items do not auto-complete — wait for human "
            "PLATE-TASK-CLOSED. Checkpoints/approvals: decide only after user chooses."
        ),
        "markdown": format_feed_markdown(target, top),
        "marker": render_feed_marker(target, top, ts),
    }


def format_feed_markdown(repo: str, items: list[FeedItem]) -> str:
    lines = [f"# PLATE Feed — {repo}", ""]
    if not items:
        lines.append("_Feed empty._")
    else:
        for i, it in enumerate(items, 1):
            num = f"#{it.number} " if it.number else ""
            lines.append(
                f"{i}. **[{it.item_type}]** {num}{it.title} "
                f"({it.impact}) — {it.reason}"
            )
    lines.append("")
    return "\n".join(lines)


def render_feed_marker(repo: str, items: list[FeedItem], ts: str) -> str:
    payload = {
        "repo": repo,
        "timestamp": ts,
        "ids": [it.id for it in items],
        "types": [it.item_type for it in items],
    }
    import json

    return f"{FEED_MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{FEED_MARKER_END}"
