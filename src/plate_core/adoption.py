"""Local adoption readiness for frictionless <30m onboarding (#935 / Epic #633).

Pure filesystem checks — no network, no auto-apply. Operators use the report to
drive import-payload + bootstrap --adopt in order (see docs/migration/adoption-guide.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


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

    if not plate_ok:
        next_cmd = "gh plate import-payload --dry-run --strategy conservative --json"
    elif core_failed:
        next_cmd = "gh plate bootstrap --repo OWNER/REPO --adopt --apply"
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
    next_steps.append("5. First Q&A: gh plate feed / gh plate plan (product planning)")

    core_ready = len(core_failed) == 0
    within_30 = est <= 30

    ask = {
        "question": (
            "Adoption readiness: continue under-30m PLATE onboarding?"
            if not core_ready
            else "Core adoption checks pass — start first Q&A / product planning?"
        ),
        "options": (
            [
                {"label": "Import payload dry-run", "description": next_cmd},
                {"label": "Bootstrap --adopt", "description": "GitHub-side baseline"},
                {"label": "Open adoption guide", "description": "docs/migration/adoption-guide.md"},
                {"label": "Defer", "description": "Leave status report only"},
            ]
            if not core_ready
            else [
                {"label": "Open feed", "description": "gh plate feed --json"},
                {"label": "Start product plan", "description": "gh plate plan"},
                {"label": "Health only", "description": "gh plate health"},
            ]
        ),
    }

    return {
        "ok": True,
        "repo_root": str(root),
        "core_ready": core_ready,
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
        "related_issues": ["#935", "#633", "#619", "#616", "#654"],
        "note": "Status only — does not apply import/bootstrap. Human/agent executes next_command.",
    }
