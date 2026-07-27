"""Local adoption readiness for frictionless <30m onboarding (#935/#949 / Epic #633).

Pure filesystem checks — no network, no auto-apply by default. Operators use the
report to drive import-payload + bootstrap --adopt + first Q&A seed in order
(see docs/migration/adoption-guide.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

# Shared catalog with bootstrap seed-initial-questions (#153 / #949).
STARTER_QUESTIONS: list[dict[str, str]] = [
    {
        "title": "[Question]: What is the primary purpose or value proposition of this software?",
        "body": (
            "What problem does this project solve? Who benefits and how?\n\n"
            "**Answer signal:** A clear, one-paragraph statement that can guide "
            "all future work and prioritization."
        ),
    },
    {
        "title": "[Question]: Who are the primary users or customers of this software?",
        "body": (
            "Describe the main personas or organizations that will use or pay for this.\n\n"
            "**Answer signal:** A concise description of the target users that can be "
            "used for roadmap and design decisions."
        ),
    },
    {
        "title": "[Question]: What are the biggest risks or unknowns for this project right now?",
        "body": (
            "Technical, market, team, or other uncertainties that could derail success.\n\n"
            "**Answer signal:** A short prioritized list that the team can actively de-risk."
        ),
    },
]

_FIRST_QA_MARKER = Path(".agentic") / "adoption" / "first_qa_seed.json"


def _check(
    *,
    check_id: str,
    title: str,
    ok: bool,
    minutes: int,
    fix_command: str,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "ok": ok,
        "minutes_if_missing": minutes if not ok else 0,
        "fix_command": fix_command if not ok else "",
        "detail": detail,
    }


def assess_adoption_readiness(
    repo_root: str | Path | None = None,
    *,
    include_optional: bool = True,
) -> dict[str, Any]:
    """Assess local checkout against #633 adoption criteria (status only).

    Returns checklist, estimated minutes remaining, next_command, and TUI payload.
    """
    root = Path(repo_root or ".").resolve()
    checks: list[dict[str, Any]] = []

    plate = root / ".plate"
    plate_ok = plate.is_file() or (plate.is_dir() and any(plate.iterdir()))
    checks.append(
        _check(
            check_id="plate_config",
            title=".plate config present",
            ok=plate_ok,
            minutes=5,
            fix_command="gh plate config init --repo-root . &&/or gh plate bootstrap --adopt --apply",
            detail=str(plate.relative_to(root)) if plate_ok else "missing",
        )
    )

    agents = root / "AGENTS.md"
    checks.append(
        _check(
            check_id="agents_md",
            title="AGENTS.md present",
            ok=agents.is_file(),
            minutes=3,
            fix_command="gh plate import-payload --dry-run --strategy conservative --json",
            detail="AGENTS.md" if agents.is_file() else "missing",
        )
    )

    goals = root / "docs" / "wiki" / "Goals.md"
    checks.append(
        _check(
            check_id="goals_wiki",
            title="docs/wiki/Goals.md present",
            ok=goals.is_file(),
            minutes=4,
            fix_command="gh plate bootstrap --adopt --apply  # seeds Goals when wiki enabled",
            detail="docs/wiki/Goals.md" if goals.is_file() else "missing",
        )
    )

    releases = root / ".agentic" / "releases"
    unreleased = releases / "unreleased"
    agentic_ok = releases.is_dir() and (unreleased.is_dir() or any(releases.glob("v*")))
    checks.append(
        _check(
            check_id="agentic_releases",
            title=".agentic/releases layout present",
            ok=agentic_ok,
            minutes=3,
            fix_command="gh plate import-payload --apply --strategy conservative",
            detail=".agentic/releases" if agentic_ok else "missing",
        )
    )

    labels = root / ".github" / "labels.yml"
    plate_ci = root / ".github" / "workflows" / "plate-ci.yml"
    ci_any = list((root / ".github" / "workflows").glob("*.yml")) if (root / ".github" / "workflows").is_dir() else []
    process_ok = labels.is_file() or plate_ci.is_file() or any(
        "plate" in p.name.lower() for p in ci_any
    )
    checks.append(
        _check(
            check_id="github_process",
            title="GitHub labels or plate workflow present",
            ok=process_ok,
            minutes=5,
            fix_command="gh plate import-payload --apply --strategy conservative; gh plate bootstrap --adopt --apply",
            detail="labels/workflows" if process_ok else "missing",
        )
    )

    if include_optional:
        spec = root / "SPEC.md"
        checks.append(
            _check(
                check_id="spec_md",
                title="SPEC.md present (optional)",
                ok=spec.is_file(),
                minutes=2,
                fix_command="gh plate import-payload --dry-run  # review SPEC conflict",
                detail="SPEC.md" if spec.is_file() else "optional missing",
            )
        )
        current = root / "CURRENT.md"
        checks.append(
            _check(
                check_id="current_md",
                title="CURRENT.md present (optional index)",
                ok=current.is_file(),
                minutes=1,
                fix_command="gh plate import-payload --apply  # seeds CURRENT.md when absent (#618)",
                detail="CURRENT.md" if current.is_file() else "optional missing",
            )
        )

    failed = [c for c in checks if not c["ok"]]
    # Optional failures do not block "core ready" or inflate hard budget the same way
    core_failed = [c for c in failed if c["id"] not in ("spec_md", "current_md")]
    est = sum(int(c["minutes_if_missing"]) for c in core_failed)
    optional_est = sum(
        int(c["minutes_if_missing"]) for c in failed if c["id"] in ("spec_md", "current_md")
    )

    core_ready = len(core_failed) == 0
    first_qa = first_qa_seed_status(root)

    if not plate_ok:
        next_cmd = "gh plate import-payload --dry-run --strategy conservative --json"
    elif core_failed:
        next_cmd = "gh plate bootstrap --repo OWNER/REPO --adopt --apply"
    elif core_ready and not first_qa.get("seeded"):
        next_cmd = "gh plate adopt --first-qa-plan --json"
    else:
        next_cmd = "gh plate health && gh plate feed --json"

    next_steps: list[str] = []
    if not plate_ok or not agents.is_file() or not agentic_ok:
        next_steps.append(
            "1. Local payload: gh plate import-payload --dry-run --strategy conservative"
        )
        next_steps.append(
            "2. Apply payload: gh plate import-payload --apply --strategy conservative"
        )
    if not plate_ok or not goals.is_file() or not process_ok:
        next_steps.append(
            "3. GitHub baseline: gh plate bootstrap --adopt --apply (labels/wiki/.plate)"
        )
    next_steps.append("4. Verify: gh plate health; write mission text in docs/wiki/Goals.md")
    if core_ready and not first_qa.get("seeded"):
        next_steps.append(
            "5. First Q&A seed: gh plate adopt --first-qa-plan --json "
            "(optional --apply-first-qa with runner)"
        )
    else:
        next_steps.append("5. First Q&A: gh plate feed / gh plate plan (product planning)")

    within_30 = est <= 30

    ask = {
        "question": (
            "Adoption readiness: continue under-30m PLATE onboarding?"
            if not core_ready
            else (
                "Core adoption ready — seed first Q&A Questions?"
                if not first_qa.get("seeded")
                else "Core adoption + first Q&A seeded — open feed / product planning?"
            )
        ),
        "options": (
            [
                {"label": "Import payload dry-run", "description": next_cmd},
                {"label": "Bootstrap --adopt", "description": "GitHub-side baseline"},
                {"label": "Open adoption guide", "description": "docs/migration/adoption-guide.md"},
                {"label": "Defer", "description": "Leave status report only"},
            ]
            if not core_ready
            else (
                [
                    {
                        "label": "First Q&A seed plan",
                        "description": "gh plate adopt --first-qa-plan --json",
                    },
                    {"label": "Open feed", "description": "gh plate feed --json"},
                    {"label": "Health only", "description": "gh plate health"},
                ]
                if not first_qa.get("seeded")
                else [
                    {"label": "Open feed", "description": "gh plate feed --json"},
                    {"label": "Start product plan", "description": "gh plate plan"},
                    {"label": "Health only", "description": "gh plate health"},
                ]
            )
        ),
    }

    return {
        "ok": True,
        "repo_root": str(root),
        "core_ready": core_ready,
        "first_qa": first_qa,
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": len(failed),
        "core_failed": len(core_failed),
        "estimated_minutes_remaining": est,
        "optional_minutes_remaining": optional_est,
        "within_30m_budget": within_30,
        "target_minutes": 30,
        "next_command": next_cmd,
        "next_steps": next_steps,
        "ask_user_question": ask,
        "guide": "docs/migration/adoption-guide.md",
        "related_issues": ["#935", "#949", "#633", "#619", "#616", "#654"],
        "note": (
            "Status only — does not apply import/bootstrap/seed. "
            "Human/agent executes next_command."
        ),
    }


def first_qa_seed_status(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Offline status of first Q&A seed marker (#949)."""
    root = Path(repo_root or ".").resolve()
    marker = root / _FIRST_QA_MARKER
    if not marker.is_file():
        return {
            "seeded": False,
            "marker_path": str(marker),
            "count": 0,
            "titles": [],
        }
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "seeded": False,
            "marker_path": str(marker),
            "count": 0,
            "titles": [],
            "error": "marker_unreadable",
        }
    titles = list(data.get("titles") or [])
    return {
        "seeded": bool(data.get("seeded")) or len(titles) >= 3,
        "marker_path": str(marker),
        "count": int(data.get("count") or len(titles)),
        "titles": titles,
        "applied_at": data.get("applied_at"),
        "mode": data.get("mode"),
    }


def plan_first_qa_seed(
    repo_root: str | Path | None = None,
    *,
    apply: bool = False,
    runner: Callable[[dict[str, Any]], Any] | None = None,
    questions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Plan (and optionally apply via runner) first Q&A seed after adoption (#949).

    Dry-run by default. Does not call GitHub unless an injectable ``runner`` is
    provided with ``apply=True``. Writes local marker only when apply succeeds
    or when apply with runner returns ok / when dry-run writes nothing.
    """
    root = Path(repo_root or ".").resolve()
    status = first_qa_seed_status(root)
    catalog = list(questions or STARTER_QUESTIONS)
    gh_argv_list: list[list[str]] = []
    for q in catalog:
        gh_argv_list.append(
            [
                "gh",
                "issue",
                "create",
                "--title",
                q["title"],
                "--body",
                q["body"],
                "--label",
                "Question",
            ]
        )

    plan: dict[str, Any] = {
        "ok": True,
        "mode": "dry_run",
        "repo_root": str(root),
        "already_seeded": bool(status.get("seeded")),
        "questions": catalog,
        "count": len(catalog),
        "gh_argv_list": gh_argv_list,
        "marker_path": str(root / _FIRST_QA_MARKER),
        "auto_apply": False,
        "applied": False,
        "related_issues": ["#949", "#633", "#935", "#654"],
        "next_command": (
            "gh plate feed --json"
            if status.get("seeded")
            else "gh plate adopt --first-qa-plan --json"
        ),
        "note": (
            "Already seeded (local marker); no-op."
            if status.get("seeded")
            else (
                "Dry-run plan only — no GitHub issue create. "
                "Apply requires --apply-first-qa + injectable runner (#949)."
            )
        ),
        "ask_user_question": {
            "question": "Seed 3 starter Curiosity Questions for first Q&A?",
            "options": [
                {
                    "label": "Apply seed via runner",
                    "description": "Create Question issues then open feed",
                },
                {"label": "Plan only", "description": "Keep dry-run artifact"},
                {"label": "Open feed without seed", "description": "gh plate feed --json"},
            ],
        },
    }

    if status.get("seeded"):
        plan["mode"] = "already_seeded"
        return plan

    if not apply:
        return plan

    # Live apply path
    plan["mode"] = "apply"
    if runner is None:
        plan["ok"] = False
        plan["error"] = "runner_required"
        plan["note"] = (
            "Live seed requires injectable runner(plan); "
            "CLI/MCP never create GitHub issues alone (#949)."
        )
        return plan

    try:
        result = runner(plan)
    except Exception as exc:  # noqa: BLE001
        plan["ok"] = False
        plan["error"] = str(exc)
        plan["note"] = "Runner failed during first Q&A seed apply."
        return plan

    # Write local marker so offline status shows seeded
    marker = root / _FIRST_QA_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seeded": True,
        "count": len(catalog),
        "titles": [q["title"] for q in catalog],
        "mode": "apply",
        "runner_result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result),
    }
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    plan["applied"] = True
    plan["runner_result"] = result
    plan["already_seeded"] = True
    plan["next_command"] = "gh plate feed --json"
    plan["note"] = "Seed applied via runner; local marker written. Open feed for first Q&A."
    return plan
