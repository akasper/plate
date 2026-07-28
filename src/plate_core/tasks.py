"""First-class Task issue creation (#359) and human-blocker detection (#360).

Task issues track human-only blockers / explicit human action items.
Agents create them via MCP/CLI; agents never fabricate the done signal.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote_plus

from .github_client import GhClient
from .health import resolve_repo

TASK_CLOSED_MARKER = "<!-- PLATE-TASK-CLOSED -->"
BLOCKER_MARKER_BEGIN = "<!-- PLATE-HUMAN-BLOCKER:BEGIN -->"
BLOCKER_MARKER_END = "<!-- PLATE-HUMAN-BLOCKER:END -->"

_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer\s+[a-z0-9._\-]{8,}|"
    r"ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{20,}|sk-[a-zA-Z0-9]{16,})"
)

# Supported human-only blocker classes (#360). Patterns are case-insensitive.
BLOCKER_CLASSES: list[dict[str, Any]] = [
    {
        "id": "credentials",
        "patterns": [
            r"\bcredentials?\b",
            r"\bapi[_ -]?keys?\b",
            r"\bsecrets?\s+(required|missing|not\s+set)\b",
            r"\bmissing\s+(env|environment)\b",
            r"\bGITHUB_TOKEN\b",
            r"\bdeploy\s+token\b",
        ],
        "title": "Provision or rotate credentials",
        "human_action": "Create/rotate the required credential in the owning external system and store it in the repo secrets surface the human controls.",
        "why": "Agents must not create, copy, or paste live credentials into GitHub issues, logs, or chat.",
        "instructions": "1. Identify the secret name required by CI/workflow.\n2. Generate it in the external console as the account owner.\n3. Add it via GitHub Settings → Secrets (or org vault).\n4. Comment completion with PLATE-TASK-CLOSED (no secret values).",
    },
    {
        "id": "trusted_publisher",
        "patterns": [
            r"\btrusted\s+publisher\b",
            r"\boidc\b.*\bpypi\b",
            r"\bpypi\b.*\btrusted\b",
        ],
        "title": "Configure PyPI trusted publisher",
        "human_action": "Log into PyPI as the project owner and configure GitHub Actions OIDC trusted publisher for this repository.",
        "why": "Trusted publisher binding requires human identity/ownership on PyPI; agents cannot complete account linkage.",
        "instructions": "1. Open pypi.org → project → Publishing.\n2. Add GitHub as trusted publisher for this owner/repo + workflow.\n3. Re-run publish workflow.\n4. Close Task with PLATE-TASK-CLOSED.",
    },
    {
        "id": "pypi_account",
        "patterns": [
            r"\bpypi\s+account\b",
            r"\bpublish\s+to\s+pypi\b",
            r"\bplate-core\b.*\bpypi\b",
        ],
        "title": "PyPI account / package ownership",
        "human_action": "Ensure the human-owned PyPI account has publish rights for plate-core (or the target package).",
        "why": "PyPI account creation and ownership are human-only external identity actions.",
        "instructions": "1. Confirm PyPI project ownership.\n2. Complete any 2FA/org invites.\n3. Link trusted publisher if needed.\n4. Close with PLATE-TASK-CLOSED.",
    },
    {
        "id": "marketplace_publish",
        "patterns": [
            r"\bmarketplace\s+publish\b",
            r"\bcopilot\s+marketplace\b",
            r"\bgh\s+extension\s+publish\b",
        ],
        "title": "Marketplace / extension publish",
        "human_action": "Complete the marketplace or gh extension publish steps as the human publisher of record.",
        "why": "Marketplace listing and publisher identity require human ownership on third-party systems.",
        "instructions": "1. Follow marketplace listing checklist.\n2. Publish from the human-owned account.\n3. Verify install path.\n4. Close with PLATE-TASK-CLOSED.",
    },
    {
        "id": "billing",
        "patterns": [
            r"\bbilling\b",
            r"\bpayment\s+method\b",
            r"\bcredit\s+card\b",
            r"\bsubscription\s+required\b",
        ],
        "title": "Billing or payment setup",
        "human_action": "Update billing/payment settings on the external service that is blocking progress.",
        "why": "Billing and payment instruments are human-only and must never be handled by agents.",
        "instructions": "1. Open the provider billing console.\n2. Add/update payment method as account owner.\n3. Confirm service unblocked.\n4. Close with PLATE-TASK-CLOSED (no card details).",
    },
    {
        "id": "external_account",
        "patterns": [
            r"\bcreate\s+(an?\s+)?account\b",
            r"\bexternal\s+account\b",
            r"\bsign\s*up\s+required\b",
            r"\bhuman\s+identity\b",
        ],
        "title": "External account creation",
        "human_action": "Create or claim the required external account as the human owner.",
        "why": "Agents cannot legally/safely assume human identity on third-party services.",
        "instructions": "1. Create the account in a browser as the owner.\n2. Complete verification/2FA.\n3. Grant least-privilege access for CI if needed.\n4. Close with PLATE-TASK-CLOSED.",
    },
]


@dataclass
class HumanBlocker:
    """A classified human-only blocker (#360)."""

    class_id: str
    title: str
    human_action: str
    why_agent_cannot: str
    instructions: str
    evidence: str = ""
    impact: str = "high"
    safe_workaround: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_human_blocker(text: str | None) -> HumanBlocker | None:
    """Classify free-text signal into a supported human-only blocker class.

    Returns None when no supported class matches, or when the text indicates an
    agent-solvable condition without human-only constraint.
    """
    if not text or not str(text).strip():
        return None
    raw = str(text)
    lower = raw.lower()

    # Explicit agent-solvable cues → do not open Task
    agent_ok = (
        "can fix in code",
        "agent can",
        "safe workaround",
        "local only",
        "unit test",
        "need:reproduction only",
    )
    if any(x in lower for x in agent_ok) and not any(
        k in lower for k in ("credential", "secret", "pypi", "billing", "marketplace")
    ):
        return None

    for cls in BLOCKER_CLASSES:
        for pat in cls["patterns"]:
            if re.search(pat, raw, re.IGNORECASE):
                return HumanBlocker(
                    class_id=str(cls["id"]),
                    title=str(cls["title"]),
                    human_action=str(cls["human_action"]),
                    why_agent_cannot=str(cls["why"]),
                    instructions=str(cls["instructions"]),
                    evidence=redact_sensitive(raw)[:400],
                    impact="high",
                    safe_workaround=False,
                )
    return None


def detect_human_blockers(
    signals: list[str] | None = None,
    *,
    text: str | None = None,
) -> list[HumanBlocker]:
    """Detect unique human-only blockers from one or more signals."""
    found: list[HumanBlocker] = []
    seen: set[str] = set()
    blobs: list[str] = []
    if text:
        blobs.append(text)
    for s in signals or []:
        if s:
            blobs.append(str(s))
    for blob in blobs:
        b = classify_human_blocker(blob)
        if b and b.class_id not in seen:
            seen.add(b.class_id)
            found.append(b)
    return found


def redact_sensitive(text: str | None, *, placeholder: str = "[REDACTED]") -> str:
    """Best-effort redaction of secret-looking substrings for Task bodies."""
    if not text:
        return ""
    return _SECRETISH.sub(placeholder, str(text))


def build_task_body(
    *,
    human_action: str,
    why_agent_cannot: str,
    context: str,
    instructions: str,
    done_signal: str | None = None,
    related_links: str | list[str] | None = None,
    epic_milestone: str | None = None,
) -> str:
    """Build a Task issue body matching the Task template contract."""
    ha = redact_sensitive(human_action).strip() or "(not provided)"
    why = redact_sensitive(why_agent_cannot).strip() or "(not provided)"
    ctx = redact_sensitive(context).strip() or "(not provided)"
    inst = redact_sensitive(instructions).strip() or "(not provided)"
    done = (
        redact_sensitive(done_signal).strip()
        if done_signal
        else (
            f"Human posts a short completion comment containing `{TASK_CLOSED_MARKER}` "
            "(no secrets), then closes the issue."
        )
    )
    if isinstance(related_links, list):
        links = "\n".join(f"- {redact_sensitive(x)}" for x in related_links if x)
    else:
        links = redact_sensitive(related_links).strip() if related_links else "(none)"
    if not links:
        links = "(none)"

    parts = [
        "## Human action required",
        "",
        ha,
        "",
        "## Why the agent cannot safely proceed",
        "",
        why,
        "",
        "## Context and affected artifacts",
        "",
        ctx,
        "",
        "## Best-effort instructions / next steps",
        "",
        inst,
        "",
        "## Done signal",
        "",
        done,
        "",
        "## Related links",
        "",
        links,
        "",
    ]
    if epic_milestone:
        parts.extend(
            [
                "## Epic milestone",
                "",
                redact_sensitive(epic_milestone).strip(),
                "",
            ]
        )
    parts.extend(
        [
            "---",
            "",
            f"Closing: completion comment must include `{TASK_CLOSED_MARKER}` and must not include secrets.",
            "",
        ]
    )
    return "\n".join(parts)


def create_task(
    title: str,
    *,
    human_action: str,
    why_agent_cannot: str,
    context: str,
    instructions: str,
    done_signal: str | None = None,
    related_links: str | list[str] | None = None,
    milestone: str | int | None = None,
    epic_milestone_name: str | None = None,
    labels: list[str] | None = None,
    repo: str | None = None,
    client: GhClient | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a GitHub Task issue (label Task only as type).

    Returns {ok, number?, url?, title, body, dry_run, error?}.
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    clean_title = (title or "").strip()
    if not clean_title:
        return {"ok": False, "error": "title required", "dry_run": dry_run}
    # Prefer human-readable title; prefix if not already Task-ish
    if not clean_title.lower().startswith("[task]"):
        display_title = f"[Task]: {clean_title}"
    else:
        display_title = clean_title

    body = build_task_body(
        human_action=human_action,
        why_agent_cannot=why_agent_cannot,
        context=context,
        instructions=instructions,
        done_signal=done_signal,
        related_links=related_links,
        epic_milestone=epic_milestone_name or (str(milestone) if milestone else None),
    )

    # Exactly one issue type: Task (plus optional area/risk extras, never other types)
    type_labels = {"Bug", "Feature", "Epic", "Release", "Research", "Design", "Question", "Audit", "Migration", "Feedback Response", "Documentation"}
    extra = [l for l in (labels or []) if l and l != "Task" and l not in type_labels]
    issue_labels = ["Task", *extra]

    payload: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "title": display_title,
        "body": body,
        "labels": issue_labels,
        "repo": target,
    }

    # Resolve milestone number if name given
    milestone_num: int | None = None
    if isinstance(milestone, int):
        milestone_num = milestone
    elif isinstance(milestone, str) and milestone.isdigit():
        milestone_num = int(milestone)
    elif epic_milestone_name or (isinstance(milestone, str) and milestone):
        name = epic_milestone_name or str(milestone)
        try:
            owner, name_repo = target.split("/", 1)
            miles = gh.api(f"repos/{owner}/{name_repo}/milestones?state=open&per_page=100") or []
            if isinstance(miles, list):
                for m in miles:
                    if str(m.get("title") or "").lower() == name.lower():
                        milestone_num = int(m["number"])
                        break
        except Exception:
            payload["milestone_warning"] = f"could not resolve milestone {name!r}"

    if dry_run:
        payload["milestone"] = milestone_num
        payload["would_create"] = True
        return payload

    fields: dict[str, Any] = {
        "title": display_title,
        "body": body,
        "labels": issue_labels,
    }
    if milestone_num is not None:
        fields["milestone"] = milestone_num

    try:
        created = gh.api(f"repos/{target}/issues", method="POST", fields=fields)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "dry_run": False, "title": display_title, "body": body}

    if not isinstance(created, dict):
        return {"ok": False, "error": "unexpected create response", "dry_run": False}

    payload.update(
        {
            "number": created.get("number"),
            "url": created.get("html_url"),
            "milestone": milestone_num,
            "created": True,
        }
    )
    return payload


def close_task_with_signal(
    number: int,
    *,
    comment: str | None = None,
    repo: str | None = None,
    client: GhClient | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Post completion comment with PLATE-TASK-CLOSED and close the issue.

    Intended for humans or agents only after human confirmed completion.
    Does not invent secrets; redacts comment body.
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    note = redact_sensitive(comment or "Task complete.").strip()
    if TASK_CLOSED_MARKER not in note:
        note = f"{note}\n\n{TASK_CLOSED_MARKER}\n"
    if dry_run:
        return {"ok": True, "dry_run": True, "number": number, "comment": note, "would_close": True}
    try:
        gh.api(
            f"repos/{target}/issues/{number}/comments",
            method="POST",
            fields={"body": note},
        )
        gh.api(
            f"repos/{target}/issues/{number}",
            method="PATCH",
            fields={"state": "closed"},
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "number": number}
    return {"ok": True, "dry_run": False, "number": number, "closed": True}


def _blocker_fingerprint(class_id: str) -> str:
    return f"{BLOCKER_MARKER_BEGIN}\n{{\"class_id\": \"{class_id}\"}}\n{BLOCKER_MARKER_END}"


def find_open_task_for_blocker(
    class_id: str,
    *,
    repo: str | None = None,
    client: GhClient | None = None,
) -> dict[str, Any] | None:
    """Return an open Task that already tracks this blocker class (dedupe)."""
    gh = client or GhClient()
    target = resolve_repo(repo)
    try:
        # Search open Task issues; filter by marker/class in body when possible
        q = f"repo:{target} is:issue is:open label:Task {class_id}"
        data = gh.api(f"search/issues?q={quote_plus(q)}&per_page=10") or {}
        items = data.get("items") if isinstance(data, dict) else []
        for it in items or []:
            body = str(it.get("body") or "")
            if class_id in body or BLOCKER_MARKER_BEGIN in body:
                return {
                    "number": it.get("number"),
                    "url": it.get("html_url"),
                    "title": it.get("title"),
                }
    except Exception:
        return None
    return None


def create_task_for_blocker(
    blocker: HumanBlocker | dict[str, Any],
    *,
    context: str = "",
    related_links: str | list[str] | None = None,
    milestone: str | int | None = None,
    epic_milestone_name: str | None = None,
    repo: str | None = None,
    client: GhClient | None = None,
    dry_run: bool = False,
    dedupe: bool = True,
) -> dict[str, Any]:
    """Create a Task from a classified human blocker (#360).

    When dedupe=True, skips create if an open Task already tracks class_id.
    """
    if isinstance(blocker, dict):
        b = HumanBlocker(
            class_id=str(blocker.get("class_id") or "unknown"),
            title=str(blocker.get("title") or "Human action required"),
            human_action=str(blocker.get("human_action") or ""),
            why_agent_cannot=str(blocker.get("why_agent_cannot") or blocker.get("why") or ""),
            instructions=str(blocker.get("instructions") or ""),
            evidence=str(blocker.get("evidence") or ""),
            impact=str(blocker.get("impact") or "high"),
            safe_workaround=bool(blocker.get("safe_workaround")),
        )
    else:
        b = blocker

    if b.safe_workaround:
        return {
            "ok": True,
            "skipped": True,
            "reason": "safe_workaround_exists",
            "blocker": b.to_dict(),
            "dry_run": dry_run,
        }

    if dedupe and not dry_run:
        existing = find_open_task_for_blocker(b.class_id, repo=repo, client=client)
        if existing:
            return {
                "ok": True,
                "skipped": True,
                "reason": "duplicate_open_task",
                "existing": existing,
                "blocker": b.to_dict(),
                "dry_run": False,
            }

    ctx_parts = [context.strip()] if context else []
    if b.evidence:
        ctx_parts.append(f"Detection evidence (redacted): {b.evidence}")
    ctx_parts.append(_blocker_fingerprint(b.class_id))
    ctx = "\n\n".join(p for p in ctx_parts if p)

    links = related_links or []
    if isinstance(links, str):
        links = [links] if links else []
    links = list(links) + [f"blocker-class:{b.class_id}", "#360"]

    result = create_task(
        b.title,
        human_action=b.human_action,
        why_agent_cannot=b.why_agent_cannot,
        context=ctx,
        instructions=b.instructions,
        related_links=links,
        milestone=milestone,
        epic_milestone_name=epic_milestone_name,
        repo=repo,
        client=client,
        dry_run=dry_run,
    )
    result["blocker"] = b.to_dict()
    result["deduped"] = False
    return result


def detect_and_create_tasks(
    signals: list[str] | None = None,
    *,
    text: str | None = None,
    context: str = "",
    repo: str | None = None,
    client: GhClient | None = None,
    dry_run: bool = True,
    create: bool = False,
) -> dict[str, Any]:
    """Detect blockers from signals; optionally create Tasks (default detect-only).

    create=False or dry_run=True → classification only (safe default).
    create=True and dry_run=False → open Task issues for each unique class.
    """
    blockers = detect_human_blockers(signals, text=text)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    if not blockers:
        return {
            "ok": True,
            "blockers": [],
            "created": [],
            "skipped": [],
            "dry_run": dry_run,
            "create": create,
        }
    for b in blockers:
        if create:
            out = create_task_for_blocker(
                b,
                context=context,
                repo=repo,
                client=client,
                dry_run=dry_run,
            )
            if out.get("skipped"):
                skipped.append(out)
            else:
                created.append(out)
        else:
            skipped.append({"skipped": True, "reason": "detect_only", "blocker": b.to_dict()})
    return {
        "ok": True,
        "blockers": [b.to_dict() for b in blockers],
        "created": created,
        "skipped": skipped,
        "dry_run": dry_run,
        "create": create,
    }
