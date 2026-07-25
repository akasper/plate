"""Unified Questions + Tasks feed for the endless user surface (#631).

Proactively ranks open Question and Task issues (plus optional autonomy/dashboard
signals) into a single feed for TUI / CLI / MCP / Copilot presentation.

v1 slice:
- Harvest open Questions (label:Question) and Tasks (label:Task) via GitHub search
- Rank: blocking/high-need Tasks and Questions first, then recency
- Emit presentation-ready items (title, type, badges, prompt_segment)
- Integrate optional what_next + autonomy open_human_checkpoints when available
- Pure helpers accept injected items for offline unit tests

Follow-ups: full ask_user_question host bridge, Projects v2 ranking, media badges.
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
    for key in ("need:human-review", "status:blocked", "risk:high", "risk:critical", "status:ready-to-work"):
        if key in {x.lower() for x in labels}:
            badges.append(key)
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


def build_feed_items(
    *,
    questions: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    process_items: list[dict[str, Any]] | None = None,
    checkpoints: list[str | dict[str, Any]] | None = None,
    signal_items: list[dict[str, Any]] | None = None,
    approval_items: list[dict[str, Any]] | None = None,
) -> list[FeedItem]:
    items: list[FeedItem] = []
    for iss in questions or []:
        items.append(issue_to_feed_item(iss, "question"))
    for iss in tasks or []:
        items.append(issue_to_feed_item(iss, "task"))
    for i, cp in enumerate(checkpoints or []):
        items.append(_checkpoint_to_feed_item(cp, i))
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
        from .design_research_approval import list_proposals

        approval_items = list_proposals(status="pending", limit=15)
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

    items = build_feed_items(
        questions=q_items,
        tasks=t_items,
        process_items=process_items,
        checkpoints=checkpoints,
        signal_items=signal_items,
        approval_items=approval_items,
    )
    top = items[: max(1, limit)]
    presentation = []
    for i, it in enumerate(top):
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
            "ask_user_question": ask_user_question_payload(it),
        }
        presentation.append(row)
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "repo": target,
        "generated_for": "user_feed",
        "issue_refs": ["#631", "#654", "#656", "#632"],
        "timestamp": ts,
        "counts": {
            "questions": len(q_items or []),
            "tasks": len(t_items or []),
            "checkpoints": len(checkpoints),
            "approvals": len(approval_items),
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
