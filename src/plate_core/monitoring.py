"""Scheduled discussion review + market condition monitoring (#642).

Cadence-friendly helpers used by AutonomyEngine procedures and PM/fleet:
- Rank GitHub Discussions/Ideas into draft Issue stubs (Epic/Feature/Question)
- Synthesize market signals into draft Questions for the endless feed
- Durable proposals under .agentic/monitoring/ (local coordination; GitHub = truth)

Does not auto-create GitHub issues without explicit apply — default is propose + feed.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MONITOR_DIR = Path(".agentic/monitoring")
PROPOSALS_FILE = "proposals.json"
MARKER_BEGIN = "<!-- PLATE-MONITOR:BEGIN -->"
MARKER_END = "<!-- PLATE-MONITOR:END -->"

# Heuristic keywords for issue type + priority
_EPIC_HINTS = re.compile(r"\b(epic|roadmap|vision|platform|orchestrat|lifecycle)\b", re.I)
_FEATURE_HINTS = re.compile(r"\b(feature|add|support|implement|integrate|enable)\b", re.I)
_BUG_HINTS = re.compile(r"\b(bug|broken|fail|error|regression|fix)\b", re.I)
_QUESTION_HINTS = re.compile(r"\b(should we|how (do|should)|what if|consider|opinion|poll)\b", re.I)
_HIGH_SIGNAL = re.compile(
    r"\b(marketplace|autonom|budget|security|pricing|competitor|launch|adoption|1\.0|v1)\b",
    re.I,
)


@dataclass
class MonitorProposal:
    """Draft issue/Question from discussion review or market monitor."""

    id: str
    source: str  # discussion | market
    proposed_type: str  # Epic | Feature | Bug | Question
    title: str
    body: str
    status: str = "pending"  # pending | approved | rejected | created
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    discussion_number: int | None = None
    discussion_url: str | None = None
    related_issue: int | None = None
    created_issue: int | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitorProposal":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or MONITOR_DIR
    if d.name == PROPOSALS_FILE:
        return d
    return d / PROPOSALS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "proposals": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "proposals": []}
        data.setdefault("version", 1)
        data.setdefault("proposals", [])
        if not isinstance(data["proposals"], list):
            data["proposals"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "proposals": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_monitor_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def classify_discussion_title(title: str, body: str = "") -> tuple[str, float]:
    """Return (proposed_type, score 0-100) from title+body heuristics."""
    text = f"{title}\n{body}"
    score = 20.0
    if _HIGH_SIGNAL.search(text):
        score += 25
    if len(title or "") > 40:
        score += 5
    if len(body or "") > 200:
        score += 10
    if _EPIC_HINTS.search(text):
        return "Epic", min(100.0, score + 20)
    if _BUG_HINTS.search(text):
        return "Bug", min(100.0, score + 15)
    if _QUESTION_HINTS.search(text):
        return "Question", min(100.0, score + 10)
    if _FEATURE_HINTS.search(text):
        return "Feature", min(100.0, score + 15)
    return "Feature", min(100.0, score)


def draft_stub_body(
    *,
    proposed_type: str,
    title: str,
    source_label: str,
    source_url: str | None = None,
    summary: str = "",
    evidence: list[str] | None = None,
) -> str:
    """Build a stub issue body with provenance (no secrets)."""
    lines = [
        f"**Stub {proposed_type}** proposed by scheduled monitoring (#642).",
        "",
        f"**Source:** {source_label}" + (f" — {source_url}" if source_url else ""),
        "",
        "## Summary",
        summary.strip() or title,
        "",
        "## Acceptance criteria (stub)",
        "- [ ] Refine scope and type with human / Q&A",
        "- [ ] Link to parent Epic or Release when known",
        "- [ ] Add tests / docs expectations when refined",
        "",
    ]
    if evidence:
        lines.append("## Evidence")
        for e in evidence:
            lines.append(f"- {e}")
        lines.append("")
    lines.append(render_monitor_marker({"source": source_label, "title": title, "type": proposed_type}))
    return "\n".join(lines)


def score_discussion(item: dict[str, Any]) -> dict[str, Any]:
    """Score one discussion-like dict into a proposal payload (not persisted)."""
    title = str(item.get("title") or item.get("name") or "Untitled discussion")
    body = str(item.get("body") or item.get("bodyText") or "")
    number = item.get("number")
    url = item.get("url") or item.get("html_url")
    category = str(item.get("category") or item.get("category_name") or "ideas")
    ptype, score = classify_discussion_title(title, body)
    stub_title = f"[Stub {ptype}]: {title}" if not title.startswith("[") else title
    evidence = []
    if number is not None:
        evidence.append(f"Discussion #{number}" + (f" ({url})" if url else ""))
    if category:
        evidence.append(f"Category: {category}")
    body_draft = draft_stub_body(
        proposed_type=ptype,
        title=title,
        source_label=f"GitHub Discussion #{number}" if number is not None else "GitHub Discussion",
        source_url=str(url) if url else None,
        summary=body[:500] if body else title,
        evidence=evidence,
    )
    return {
        "source": "discussion",
        "proposed_type": ptype,
        "title": stub_title,
        "body": body_draft,
        "score": score,
        "evidence": evidence,
        "discussion_number": int(number) if number is not None else None,
        "discussion_url": str(url) if url else None,
        "metadata": {"category": category},
    }


def score_market_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """Turn a market signal dict into a Question proposal (not persisted)."""
    title = str(signal.get("title") or signal.get("headline") or "Market signal")
    detail = str(signal.get("detail") or signal.get("summary") or signal.get("body") or "")
    sources = list(signal.get("sources") or signal.get("evidence") or [])
    if signal.get("url"):
        sources.append(str(signal["url"]))
    impact = str(signal.get("impact") or "medium").lower()
    score = 40.0
    if impact in ("high", "critical"):
        score += 30
    if _HIGH_SIGNAL.search(f"{title} {detail}"):
        score += 20
    if sources:
        score += min(15, 5 * len(sources))
    q_title = f"Market signal: {title}" if not title.lower().startswith("market") else title
    body = draft_stub_body(
        proposed_type="Question",
        title=q_title,
        source_label="Market monitor (#642)",
        source_url=str(signal.get("url") or "") or None,
        summary=detail[:800] or title,
        evidence=[str(s) for s in sources],
    )
    body += (
        "\n## Answer signal\n"
        "- What is the impact on PLATE roadmap / feed priority?\n"
        "- Should we open a Feature/Epic stub, or ignore?\n"
    )
    return {
        "source": "market",
        "proposed_type": "Question",
        "title": q_title if q_title.startswith("[") else f"[Question]: {q_title}",
        "body": body,
        "score": min(100.0, score),
        "evidence": [str(s) for s in sources],
        "discussion_number": None,
        "discussion_url": str(signal.get("url") or "") or None,
        "metadata": {"impact": impact, "raw": {k: signal[k] for k in signal if k not in ("detail", "summary", "body")}},
    }


def persist_proposal(draft: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    """Persist a scored draft as pending MonitorProposal (dedupe by title+source)."""
    data = _load(base_dir)
    title = str(draft.get("title") or "")
    source = str(draft.get("source") or "")
    for p in data["proposals"]:
        if p.get("status") == "pending" and p.get("title") == title and p.get("source") == source:
            p["score"] = draft.get("score", p.get("score"))
            p["updated_at"] = _now()
            p["body"] = draft.get("body") or p.get("body")
            _save(data, base_dir)
            return {"ok": True, "proposal": p, "updated": True}
    ts = _now()
    prop = MonitorProposal(
        id=f"mon-{uuid.uuid4().hex[:10]}",
        source=source,
        proposed_type=str(draft.get("proposed_type") or "Feature"),
        title=title,
        body=str(draft.get("body") or ""),
        status="pending",
        score=float(draft.get("score") or 0),
        evidence=list(draft.get("evidence") or []),
        discussion_number=draft.get("discussion_number"),
        discussion_url=draft.get("discussion_url"),
        created_at=ts,
        updated_at=ts,
        metadata=dict(draft.get("metadata") or {}),
    )
    data["proposals"].append(prop.to_dict())
    _save(data, base_dir)
    return {"ok": True, "proposal": prop.to_dict(), "updated": False}


def list_proposals(
    *,
    status: str = "pending",
    source: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    data = _load(base_dir)
    out: list[dict[str, Any]] = []
    for p in data.get("proposals") or []:
        if status and status != "all" and p.get("status") != status:
            continue
        if source and p.get("source") != source:
            continue
        out.append(p)
    out.sort(key=lambda x: (-float(x.get("score") or 0), x.get("created_at") or ""), reverse=False)
    out.sort(key=lambda x: -float(x.get("score") or 0))
    return out[: max(1, int(limit or 50))]


def decide_proposal(
    proposal_id: str,
    decision: str,
    *,
    base_dir: Path | None = None,
    created_issue: int | None = None,
) -> dict[str, Any]:
    """approve | reject | created for a pending proposal."""
    data = _load(base_dir)
    dec = (decision or "").lower().strip()
    if dec not in ("approve", "approved", "reject", "rejected", "created"):
        return {"ok": False, "error": f"invalid decision: {decision}"}
    status_map = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "created": "created",
    }
    found = None
    for p in data["proposals"]:
        if p.get("id") == proposal_id:
            found = p
            break
    if not found:
        return {"ok": False, "error": f"proposal not found: {proposal_id}"}
    found["status"] = status_map[dec]
    found["updated_at"] = _now()
    if created_issue is not None:
        found["created_issue"] = created_issue
    _save(data, base_dir)
    return {"ok": True, "proposal": found}


def review_discussions(
    discussions: list[dict[str, Any]] | None = None,
    *,
    repo: str | None = None,
    min_score: float = 30.0,
    limit: int = 10,
    persist: bool = True,
    base_dir: Path | None = None,
    fetch_live: bool = False,
) -> dict[str, Any]:
    """Review discussion candidates; return ranked proposals (optionally live Ideas)."""
    items = list(discussions or [])
    if fetch_live and not items:
        try:
            from .discussions import list_open_ideas

            live = list_open_ideas(repo=repo)
            for d in live:
                if hasattr(d, "to_dict"):
                    items.append(d.to_dict())
                elif isinstance(d, dict):
                    items.append(d)
                else:
                    items.append(
                        {
                            "number": getattr(d, "number", None),
                            "title": getattr(d, "title", str(d)),
                            "body": getattr(d, "body", ""),
                            "url": getattr(d, "url", None),
                            "category": "ideas",
                        }
                    )
        except Exception as exc:
            return {
                "ok": False,
                "error": f"live discussion fetch failed: {exc}",
                "proposals": [],
                "n_scanned": 0,
            }

    scored = [score_discussion(it) for it in items]
    scored = [s for s in scored if float(s.get("score") or 0) >= min_score]
    scored.sort(key=lambda x: -float(x.get("score") or 0))
    scored = scored[: max(1, int(limit or 10))] if scored else []

    proposals = []
    for s in scored:
        if persist:
            r = persist_proposal(s, base_dir=base_dir)
            if r.get("proposal"):
                proposals.append(r["proposal"])
        else:
            proposals.append(s)

    return {
        "ok": True,
        "n_scanned": len(items),
        "n_proposed": len(proposals),
        "proposals": proposals,
        "min_score": min_score,
        "marker": render_monitor_marker(
            {"proc": "discussion-review", "n_scanned": len(items), "n_proposed": len(proposals)}
        ),
    }


def monitor_market_signals(
    signals: list[dict[str, Any]] | None = None,
    *,
    min_score: float = 40.0,
    limit: int = 10,
    persist: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Synthesize market signal dicts into Question proposals for the feed.

    Hosts inject signals (from web_search / x_* / feedback aggregation); this
    module does not call external networks itself.
    """
    items = list(signals or [])
    scored = [score_market_signal(it) for it in items]
    scored = [s for s in scored if float(s.get("score") or 0) >= min_score]
    scored.sort(key=lambda x: -float(x.get("score") or 0))
    scored = scored[: max(1, int(limit or 10))] if scored else []

    proposals = []
    for s in scored:
        if persist:
            r = persist_proposal(s, base_dir=base_dir)
            if r.get("proposal"):
                proposals.append(r["proposal"])
        else:
            proposals.append(s)

    return {
        "ok": True,
        "n_signals": len(items),
        "n_proposed": len(proposals),
        "proposals": proposals,
        "min_score": min_score,
        "marker": render_monitor_marker(
            {"proc": "market-monitor", "n_signals": len(items), "n_proposed": len(proposals)}
        ),
    }


def run_discussion_review_procedure(
    *,
    repo: str | None = None,
    discussions: list[dict[str, Any]] | None = None,
    dry_run: bool = True,
    fetch_live: bool = False,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Procedure entry: weekly discussion review (#642)."""
    result = review_discussions(
        discussions,
        repo=repo,
        persist=not dry_run,
        fetch_live=fetch_live and not dry_run,
        base_dir=base_dir,
    )
    result["proc_id"] = "weekly-discussion-review"
    result["status"] = "dry-run" if dry_run else "executed"
    result["dry_run"] = dry_run
    return result


def run_market_monitor_procedure(
    *,
    signals: list[dict[str, Any]] | None = None,
    dry_run: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Procedure entry: market condition monitoring (#642)."""
    result = monitor_market_signals(signals, persist=not dry_run, base_dir=base_dir)
    result["proc_id"] = "market-condition-monitor"
    result["status"] = "dry-run" if dry_run else "executed"
    result["dry_run"] = dry_run
    return result


def monitoring_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Present pending monitor proposals in the endless feed."""
    items: list[dict[str, Any]] = []
    for p in list_proposals(status="pending", limit=limit, base_dir=base_dir):
        pid = p.get("id")
        ptype = p.get("proposed_type") or "Feature"
        title = p.get("title") or "Monitor proposal"
        items.append(
            {
                "id": pid,
                "item_type": "monitor_proposal",
                "title": title,
                "source_kind": p.get("source"),
                "proposed_type": ptype,
                "score": p.get("score"),
                "badges": ["monitor", str(p.get("source")), ptype, "pending"],
                "source": "monitoring",
                "impact": "high" if float(p.get("score") or 0) >= 70 else "medium",
                "reason": f"Scheduled monitoring proposal ({p.get('source')})",
                "ask_user_question": {
                    "question": f"Approve creating {ptype} from monitoring: {title[:100]}?",
                    "options": [
                        {
                            "id": "approve",
                            "label": "Approve create",
                            "description": f"plate_monitor_decide {pid} approve then open issue",
                        },
                        {
                            "id": "reject",
                            "label": "Reject",
                            "description": f"plate_monitor_decide {pid} reject",
                        },
                        {
                            "id": "defer",
                            "label": "Defer",
                            "description": "Leave pending for next review",
                        },
                    ],
                },
                "marker": render_monitor_marker({"id": pid, "title": title, "type": ptype}),
            }
        )
    return items
