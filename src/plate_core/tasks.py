"""First-class Task issue creation (#359) and close helper.

Task issues track human-only blockers / explicit human action items.
Agents create them via MCP/CLI; agents never fabricate the done signal.
"""

from __future__ import annotations

import re
from typing import Any

from .github_client import GhClient
from .health import resolve_repo

TASK_CLOSED_MARKER = "<!-- PLATE-TASK-CLOSED -->"
_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer\s+[a-z0-9._\-]{8,}|"
    r"ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{20,}|sk-[a-zA-Z0-9]{16,})"
)


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
