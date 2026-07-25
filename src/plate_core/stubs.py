"""Autonomous stub issue authoring + refinement lifecycle (#637).

Author and refine stubbed Issues of all PLATE types from Q&A/signals:
Release | Feature | Bug | Epic | Design | Research | Question | Task

Local durable drafts under .agentic/stubs/ before GitHub create.
Labels: type + status:stub + need:refinement (and optional area/risk).
Does not replace type-specific helpers (create_task, plan_epic) — unifies them.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .github_client import GhClient
from .health import resolve_repo

STUBS_DIR = Path(".agentic/stubs")
DRAFTS_FILE = "drafts.json"
MARKER_BEGIN = "<!-- PLATE-STUB:BEGIN -->"
MARKER_END = "<!-- PLATE-STUB:END -->"

ISSUE_TYPES = (
    "Feature",
    "Bug",
    "Epic",
    "Release",
    "Research",
    "Design",
    "Question",
    "Task",
)

# Intent keywords → type
_TYPE_HINTS: list[tuple[str, re.Pattern[str]]] = [
    ("Bug", re.compile(r"\b(bug|broken|fail|error|regression|crash|fix)\b", re.I)),
    ("Epic", re.compile(r"\b(epic|roadmap|theme|initiative|program)\b", re.I)),
    ("Release", re.compile(r"\b(release|semver|cut v|ship v|version)\b", re.I)),
    ("Research", re.compile(r"\b(research|investigate|spike|survey|benchmark)\b", re.I)),
    ("Design", re.compile(r"\b(design|wireframe|ux|ui|architecture diagram)\b", re.I)),
    ("Question", re.compile(r"\b(should we|how (do|should)|what if|decide|question)\b", re.I)),
    ("Task", re.compile(r"\b(human (only|action)|credential|manual|task:)\b", re.I)),
    ("Feature", re.compile(r"\b(feature|add|support|implement|enable|build)\b", re.I)),
]


@dataclass
class StubDraft:
    """Local stub draft before/after GitHub create."""

    id: str
    issue_type: str
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | pending_create | created | refining | ready
    acceptance_criteria: list[str] = field(default_factory=list)
    parent_epic: str | int | None = None
    milestone: str | int | None = None
    related_links: list[str] = field(default_factory=list)
    source: str = "qa"  # qa | signal | monitor | agent | human
    github_number: int | None = None
    github_url: str | None = None
    refinement_notes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StubDraft":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or STUBS_DIR
    if d.name == DRAFTS_FILE:
        return d
    return d / DRAFTS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "drafts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "drafts": []}
        data.setdefault("version", 1)
        data.setdefault("drafts", [])
        if not isinstance(data["drafts"], list):
            data["drafts"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "drafts": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_stub_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def normalize_issue_type(issue_type: str | None) -> str:
    t = (issue_type or "").strip()
    for known in ISSUE_TYPES:
        if t.lower() == known.lower():
            return known
    return "Feature"


def detect_issue_type(intent: str, *, hint: str | None = None) -> str:
    """Infer PLATE issue type from free-text intent."""
    if hint:
        return normalize_issue_type(hint)
    text = intent or ""
    for itype, pat in _TYPE_HINTS:
        if pat.search(text):
            return itype
    return "Feature"


def default_labels_for_type(issue_type: str, *, as_stub: bool = True) -> list[str]:
    itype = normalize_issue_type(issue_type)
    labels = [itype]
    if as_stub:
        labels.append("status:stub")
        labels.append("need:refinement")
    return labels


def format_stub_title(issue_type: str, title: str) -> str:
    itype = normalize_issue_type(issue_type)
    t = (title or "").strip() or "Untitled"
    # Avoid double-prefix
    if re.match(rf"^\[{itype}\]", t, re.I) or t.lower().startswith(f"[{itype.lower()}]"):
        return t
    if t.lower().startswith("[stub"):
        return t
    return f"[Stub {itype}]: {t}"


def build_stub_body(
    *,
    issue_type: str,
    title: str,
    summary: str = "",
    acceptance_criteria: list[str] | None = None,
    parent_epic: str | int | None = None,
    related_links: list[str] | None = None,
    source: str = "qa",
    extra_sections: dict[str, str] | None = None,
) -> str:
    itype = normalize_issue_type(issue_type)
    ac = list(acceptance_criteria or [])
    if not ac:
        ac = [
            "Refine scope and acceptance criteria via Q&A",
            "Confirm type labels and parent Epic/milestone",
            "Add tests / docs expectations when ready-to-work",
        ]
    lines = [
        f"**Stub {itype}** authored for autonomous lifecycle (#637).",
        "",
        f"**Source:** {source}",
        "",
        "## Summary",
        (summary or title).strip(),
        "",
        "## Acceptance criteria",
    ]
    for a in ac:
        lines.append(f"- [ ] {a}")
    lines.append("")
    if parent_epic is not None:
        lines.append(f"**Parent Epic / milestone:** {parent_epic}")
        lines.append("")
    if related_links:
        lines.append("## Related")
        for link in related_links:
            lines.append(f"- {link}")
        lines.append("")
    if extra_sections:
        for heading, content in extra_sections.items():
            lines.append(f"## {heading}")
            lines.append(content.strip())
            lines.append("")
    # Type-specific light scaffolding
    if itype == "Question":
        lines.extend(
            [
                "## Answer signal",
                "- Decision recorded with evidence links",
                "- Follow-up issues opened if product intent changes",
                "",
            ]
        )
    elif itype == "Bug":
        lines.extend(
            [
                "## Reproduction (stub)",
                "- [ ] Steps to reproduce",
                "- [ ] Expected vs actual",
                "",
            ]
        )
    elif itype == "Task":
        lines.extend(
            [
                "## Human action required",
                "(Fill via plate_task_create fields when promoting.)",
                "",
            ]
        )
    lines.append(
        render_stub_marker(
            {
                "issue_type": itype,
                "title": title,
                "source": source,
                "status": "stub",
            }
        )
    )
    return "\n".join(lines)


def author_stub(
    intent: str,
    *,
    issue_type: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    acceptance_criteria: list[str] | None = None,
    parent_epic: str | int | None = None,
    milestone: str | int | None = None,
    related_links: list[str] | None = None,
    source: str = "qa",
    labels: list[str] | None = None,
    persist: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Author a local stub draft from intent/Q&A text."""
    text = (intent or "").strip()
    if not text and not title:
        return {"ok": False, "error": "intent or title required"}
    itype = detect_issue_type(text or title or "", hint=issue_type)
    clean_title = (title or "").strip()
    if not clean_title:
        # First line / sentence of intent
        clean_title = re.split(r"[\n.]", text)[0].strip()[:120] or "Untitled stub"
    display = format_stub_title(itype, clean_title)
    body = build_stub_body(
        issue_type=itype,
        title=clean_title,
        summary=summary or text,
        acceptance_criteria=acceptance_criteria,
        parent_epic=parent_epic,
        related_links=related_links,
        source=source,
    )
    labs = default_labels_for_type(itype, as_stub=True)
    for lab in labels or []:
        if lab and lab not in labs and lab not in ISSUE_TYPES:
            labs.append(lab)
        elif lab in ISSUE_TYPES and lab != itype:
            # ignore conflicting type labels
            pass
    ts = _now()
    draft = StubDraft(
        id=f"stub-{uuid.uuid4().hex[:10]}",
        issue_type=itype,
        title=display,
        body=body,
        labels=labs,
        status="draft",
        acceptance_criteria=list(acceptance_criteria or []),
        parent_epic=parent_epic,
        milestone=milestone,
        related_links=list(related_links or []),
        source=source,
        created_at=ts,
        updated_at=ts,
        metadata={"intent": text[:500]},
    )
    if persist:
        data = _load(base_dir)
        data["drafts"].append(draft.to_dict())
        _save(data, base_dir)
    return {
        "ok": True,
        "draft": draft.to_dict(),
        "marker": render_stub_marker(draft.to_dict()),
    }


def refine_stub(
    draft_id: str,
    *,
    answers: dict[str, Any] | None = None,
    add_acceptance: list[str] | None = None,
    summary_append: str | None = None,
    issue_type: str | None = None,
    note: str | None = None,
    mark_ready: bool = False,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Refine a stub draft from further Q&A / contemplation answers."""
    data = _load(base_dir)
    found: dict[str, Any] | None = None
    for d in data["drafts"]:
        if d.get("id") == draft_id or (
            draft_id.isdigit() and d.get("github_number") == int(draft_id)
        ):
            found = d
            break
    if not found:
        return {"ok": False, "error": f"draft not found: {draft_id}"}

    if issue_type:
        itype = normalize_issue_type(issue_type)
        found["issue_type"] = itype
        # Fix labels: replace type
        labs = [l for l in (found.get("labels") or []) if l not in ISSUE_TYPES]
        labs.insert(0, itype)
        if "status:stub" not in labs and not mark_ready:
            labs.append("status:stub")
        if "need:refinement" not in labs and not mark_ready:
            labs.append("need:refinement")
        found["labels"] = labs
        # Refresh title prefix
        raw = re.sub(r"^\[Stub [^\]]+\]:\s*", "", str(found.get("title") or ""), flags=re.I)
        found["title"] = format_stub_title(itype, raw)

    ac = list(found.get("acceptance_criteria") or [])
    for a in add_acceptance or []:
        if a and a not in ac:
            ac.append(a)
    # Parse answers dict into AC / notes
    ans = answers or {}
    for k, v in ans.items():
        if v is None:
            continue
        note_line = f"{k}: {v}"
        if str(k).lower() in ("acceptance", "ac", "criteria") and isinstance(v, list):
            for item in v:
                if item and str(item) not in ac:
                    ac.append(str(item))
        elif str(k).lower() in ("acceptance", "ac", "criteria") and isinstance(v, str):
            if v not in ac:
                ac.append(v)
        else:
            found.setdefault("refinement_notes", []).append(note_line)
    found["acceptance_criteria"] = ac

    if summary_append:
        found["body"] = str(found.get("body") or "") + f"\n\n## Refinement\n{summary_append.strip()}\n"
    if note:
        found.setdefault("refinement_notes", []).append(note)

    # Rebuild body acceptance section lightly
    body = str(found.get("body") or "")
    if ac:
        ac_block = "## Acceptance criteria\n" + "\n".join(f"- [ ] {a}" for a in ac) + "\n"
        if "## Acceptance criteria" in body:
            body = re.sub(
                r"## Acceptance criteria\n(?:- \[[ x]\].*\n)*",
                ac_block,
                body,
                count=1,
            )
        else:
            body = body.replace("## Summary", ac_block + "\n## Summary", 1)
        found["body"] = body

    found["status"] = "ready" if mark_ready else "refining"
    if mark_ready:
        labs = [l for l in (found.get("labels") or []) if l not in ("status:stub", "need:refinement")]
        labs.append("status:ready-to-work")
        found["labels"] = labs
    found["updated_at"] = _now()
    _save(data, base_dir)
    return {"ok": True, "draft": found}


def list_stubs(
    *,
    status: str = "all",
    issue_type: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    data = _load(base_dir)
    out: list[dict[str, Any]] = []
    for d in data.get("drafts") or []:
        if status and status != "all" and d.get("status") != status:
            continue
        if issue_type and normalize_issue_type(str(d.get("issue_type"))) != normalize_issue_type(issue_type):
            continue
        out.append(d)
    return out[: max(1, int(limit or 50))]


def get_stub(draft_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for d in list_stubs(status="all", limit=500, base_dir=base_dir):
        if d.get("id") == draft_id:
            return d
        if draft_id.isdigit() and d.get("github_number") == int(draft_id):
            return d
    return None


def create_stub_issue(
    draft_id: str | None = None,
    *,
    draft: dict[str, Any] | None = None,
    repo: str | None = None,
    client: GhClient | None = None,
    dry_run: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create GitHub issue from a draft (default dry_run)."""
    found = draft
    if draft_id and not found:
        found = get_stub(draft_id, base_dir=base_dir)
    if not found:
        return {"ok": False, "error": "draft required", "dry_run": dry_run}

    target = resolve_repo(repo)
    title = str(found.get("title") or "")
    body = str(found.get("body") or "")
    labels = list(found.get("labels") or default_labels_for_type(str(found.get("issue_type") or "Feature")))
    payload: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "title": title,
        "body": body,
        "labels": labels,
        "repo": target,
        "draft_id": found.get("id"),
    }

    milestone_num: int | None = None
    milestone = found.get("milestone") or found.get("parent_epic")
    if isinstance(milestone, int):
        milestone_num = milestone
    elif isinstance(milestone, str) and milestone.isdigit():
        milestone_num = int(milestone)

    if dry_run:
        payload["would_create"] = True
        payload["milestone"] = milestone_num
        return payload

    gh = client or GhClient()
    fields: dict[str, Any] = {
        "title": title,
        "body": body,
        "labels": labels,
    }
    if milestone_num is not None:
        fields["milestone"] = milestone_num
    try:
        created = gh.api(f"repos/{target}/issues", method="POST", fields=fields)
        if not isinstance(created, dict):
            return {"ok": False, "error": "unexpected API response", "dry_run": False}
        number = created.get("number")
        url = created.get("html_url")
        # Update local draft
        data = _load(base_dir)
        for d in data["drafts"]:
            if d.get("id") == found.get("id"):
                d["status"] = "created"
                d["github_number"] = number
                d["github_url"] = url
                d["updated_at"] = _now()
                break
        _save(data, base_dir)
        payload.update(
            {
                "number": number,
                "url": url,
                "status": "created",
            }
        )
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc), "dry_run": False, "draft_id": found.get("id")}


def author_and_create(
    intent: str,
    *,
    issue_type: str | None = None,
    title: str | None = None,
    dry_run: bool = True,
    repo: str | None = None,
    base_dir: Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-shot: author draft then optionally create on GitHub."""
    authored = author_stub(
        intent,
        issue_type=issue_type,
        title=title,
        persist=True,
        base_dir=base_dir,
        **{k: v for k, v in kwargs.items() if k in (
            "summary", "acceptance_criteria", "parent_epic", "milestone",
            "related_links", "source", "labels",
        )},
    )
    if not authored.get("ok"):
        return authored
    created = create_stub_issue(
        authored["draft"]["id"],
        dry_run=dry_run,
        repo=repo,
        base_dir=base_dir,
    )
    return {
        "ok": created.get("ok", False),
        "draft": authored.get("draft"),
        "create": created,
        "dry_run": dry_run,
    }


def stubs_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Feed presentation for drafts awaiting create or refinement."""
    items: list[dict[str, Any]] = []
    for d in list_stubs(status="all", limit=limit * 2, base_dir=base_dir):
        if d.get("status") not in ("draft", "refining", "pending_create"):
            continue
        did = d.get("id")
        items.append(
            {
                "id": did,
                "item_type": "stub_draft",
                "title": d.get("title"),
                "issue_type": d.get("issue_type"),
                "status": d.get("status"),
                "badges": ["stub", str(d.get("issue_type")), str(d.get("status"))],
                "source": "stubs",
                "impact": "medium",
                "reason": "Stub draft awaiting create/refinement (#637)",
                "ask_user_question": {
                    "question": f"Stub {d.get('issue_type')}: {str(d.get('title') or '')[:100]} — next?",
                    "options": [
                        {
                            "id": "create",
                            "label": "Create on GitHub",
                            "description": f"plate_stub_create {did} dry_run=false",
                        },
                        {
                            "id": "refine",
                            "label": "Refine further",
                            "description": f"plate_stub_refine {did}",
                        },
                        {
                            "id": "ready",
                            "label": "Mark ready-to-work",
                            "description": f"plate_stub_refine {did} mark_ready=true",
                        },
                    ],
                },
                "marker": render_stub_marker({"id": did, "status": d.get("status")}),
            }
        )
        if len(items) >= limit:
            break
    return items
