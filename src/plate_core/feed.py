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


def build_feed_items(
    *,
    questions: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    process_items: list[dict[str, Any]] | None = None,
    checkpoints: list[str] | None = None,
) -> list[FeedItem]:
    items: list[FeedItem] = []
    for iss in questions or []:
        items.append(issue_to_feed_item(iss, "question"))
    for iss in tasks or []:
        items.append(issue_to_feed_item(iss, "task"))
    for i, cp in enumerate(checkpoints or []):
        items.append(
            FeedItem(
                id=f"checkpoint-{i}",
                item_type="checkpoint",
                number=None,
                title=str(cp),
                rank=12 + i,
                impact="high",
                badges=["checkpoint", "high"],
                prompt_segment=(
                    f"Open human checkpoint: {cp}. Use plate_checkpoint_decide / gh plate checkpoint "
                    "after user judgment; do not bypass."
                ),
                reason="Open autonomy checkpoint",
                source="autonomy_status",
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

    checkpoints: list[str] = []
    autonomy_snap: dict[str, Any] = {}
    if include_autonomy:
        try:
            from .autonomy import get_autonomy_status

            autonomy_snap = get_autonomy_status(target)
            checkpoints = list(autonomy_snap.get("open_human_checkpoints") or [])
        except Exception:
            autonomy_snap = {}

    items = build_feed_items(
        questions=q_items,
        tasks=t_items,
        process_items=process_items,
        checkpoints=checkpoints,
    )
    top = items[: max(1, limit)]
    presentation = [
        {
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
        }
        for i, it in enumerate(top)
    ]
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "repo": target,
        "generated_for": "user_feed",
        "issue_refs": ["#631", "#654", "#656"],
        "timestamp": ts,
        "counts": {
            "questions": len(q_items or []),
            "tasks": len(t_items or []),
            "checkpoints": len(checkpoints),
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
            "Present presentation[] via native ask_user_question one-at-a-time; "
            "for Task items do not auto-complete — wait for human PLATE-TASK-CLOSED."
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
