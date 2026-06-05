"""Bootstrap planning/apply helpers for new PLATE repositories."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass

from .github_client import GhClient
from .health import REQUIRED_LABELS, get_health, resolve_repo
from .plate_config import DEFAULT_CONFIG


DEFAULT_LABEL_COLOR = "5319e7"

# Placeholder for bootstrap init of Goals wiki page (per convention).
GOALS_PAGE_PLACEHOLDER = """# Goals

**This page is part of the PLATE convention for managing high-level project intent.**

Every PLATE project is encouraged to maintain a `Goals` page in its Wiki. This page serves as the canonical, agent-accessible source for the project's overall **mission** — why it exists and how it intends to succeed.

This is distinct from `SPEC.md`, which focuses on product implementation details, architecture decisions, and engineering outcomes.

## Purpose of This Page

The `Goals` page answers high-level questions such as:
- Why is this project being built?
- Who is it for, and what outcomes matter most?
- What does "winning" look like at a strategic level?
- What are the key principles or constraints that should guide major decisions?

Agents performing Information Audits are expected to read this page as one of their primary signals.

## Mission

> [Replace this with your project's broad directional mission. Keep it high-level — why you exist and how you intend to succeed (go-to-market, impact, revenue model, etc.).]

## Core Principles

- [Principle 1 with short rationale]
- [Principle 2 with short rationale]

## How We Intend to Succeed

- [Broad strategic outcome 1]
- [Broad strategic outcome 2]

## Current State & Evidence

[Light, high-level snapshot of where things stand today.]

## Open Strategic Questions

[Link to major `Question` issues that represent big unresolved informational goals against the mission above.]

---

*This is the recommended starting template for the PLATE Goals wiki page convention (see `docs/design/goals-wiki-page-convention.md` in the template payload for full guidance).*
"""


@dataclass
class BootstrapAction:
    name: str
    state: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BootstrapReport:
    repo: str
    apply_mode: bool
    actions: list[BootstrapAction]

    def to_dict(self) -> dict:
        return {"repo": self.repo, "apply_mode": self.apply_mode, "actions": [a.to_dict() for a in self.actions]}


def run_bootstrap(repo: str | None = None, apply_mode: bool = False, client: GhClient | None = None) -> BootstrapReport:
    gh = client or GhClient()
    target = resolve_repo(repo)
    health = get_health(target, gh)
    repo_obj = gh.api(f"repos/{target}")
    actions: list[BootstrapAction] = []

    for label in health.missing_labels:
        if apply_mode:
            gh.api(
                f"repos/{target}/labels",
                method="POST",
                fields={"name": label, "color": DEFAULT_LABEL_COLOR, "description": f"PLATE label: {label}"},
            )
            state = "applied"
        else:
            state = "planned"
        actions.append(BootstrapAction(name="create-label", state=state, detail=label))

    if not repo_obj.get("has_wiki", False):
        if apply_mode:
            gh.api(f"repos/{target}", method="PATCH", fields={"has_wiki": True})
            state = "applied"
        else:
            state = "planned"
        actions.append(BootstrapAction(name="enable-wiki", state=state, detail="Set has_wiki=true"))
    else:
        actions.append(BootstrapAction(name="enable-wiki", state="already-configured", detail="Wiki already enabled"))

    # Bootstrap support for Goals page convention (for #266 / beta, building on #229 / #224).
    # Seeds docs/wiki/Goals.md with placeholder if missing (after enabling wiki).
    # Supports "flag or interactive" via always planning if wiki on and no page (interactive in future CLI).
    # For apply, creates via contents API.
    default_branch = repo_obj.get("default_branch", "main")
    goals_present = False
    try:
        gh.api(f"repos/{target}/contents/docs/wiki/Goals.md")
        goals_present = True
    except Exception:
        pass
    if not goals_present:
        if apply_mode:
            content = base64.b64encode(GOALS_PAGE_PLACEHOLDER.encode("utf-8")).decode("ascii")
            gh.api(
                f"repos/{target}/contents/docs%2Fwiki%2FGoals.md",
                method="PUT",
                fields={
                    "message": "Bootstrap: initialize docs/wiki/Goals.md per PLATE convention (Epic #218 / #266)",
                    "content": content,
                    "branch": default_branch,
                },
            )
            state = "applied"
            detail = "Initialized docs/wiki/Goals.md with PLATE convention placeholder"
        else:
            state = "planned"
            detail = "Initialize docs/wiki/Goals.md (PLATE Goals wiki page convention for agent audits + health nudges; flag/interactive in CLI)"
        actions.append(BootstrapAction(name="init-goals-page", state=state, detail=detail))
    else:
        actions.append(
            BootstrapAction(
                name="init-goals-page",
                state="already-configured",
                detail="docs/wiki/Goals.md already present (Goals convention adopted)",
            )
        )

    if not health.plate_config_present:
        if apply_mode:
            content = base64.b64encode((json.dumps(DEFAULT_CONFIG, indent=2) + "\n").encode("utf-8")).decode("ascii")
            gh.api(
                f"repos/{target}/contents/.plate",
                method="PUT",
                fields={
                    "message": "Bootstrap: initialize .plate baseline config (Epic #259)",
                    "content": content,
                    "branch": default_branch,
                },
            )
            state = "applied"
            detail = "Initialized root .plate baseline config"
        else:
            state = "planned"
            detail = "Initialize root .plate baseline config"
        actions.append(BootstrapAction(name="init-plate-config", state=state, detail=detail))
    else:
        actions.append(
            BootstrapAction(
                name="init-plate-config",
                state="already-configured",
                detail="Root .plate config already present",
            )
        )

    if health.open_epic_count == 0:
        if apply_mode:
            gh.api(
                f"repos/{target}/issues",
                method="POST",
                fields={"title": "[Epic] Initial PLATE epic", "body": "Bootstrap-created initial Epic for project setup."},
            )
            state = "applied"
        else:
            state = "planned"
        actions.append(BootstrapAction(name="create-initial-epic", state=state, detail="Create first Epic issue"))
    else:
        actions.append(
            BootstrapAction(name="create-initial-epic", state="already-configured", detail="At least one open Epic exists")
        )

    # Feature #153: Seed initial Curiosity / informational goal Questions (per Epic #139)
    # These give new PLATE projects immediate value from the Q&A / Curiosity mode.
    starter_questions = [
        {
            "title": "[Question]: What is the primary purpose or value proposition of this software?",
            "body": "What problem does this project solve? Who benefits and how?\n\n**Answer signal:** A clear, one-paragraph statement that can guide all future work and prioritization.",
        },
        {
            "title": "[Question]: Who are the primary users or customers of this software?",
            "body": "Describe the main personas or organizations that will use or pay for this.\n\n**Answer signal:** A concise description of the target users that can be used for roadmap and design decisions.",
        },
        {
            "title": "[Question]: What are the biggest risks or unknowns for this project right now?",
            "body": "Technical, market, team, or other uncertainties that could derail success.\n\n**Answer signal:** A short prioritized list that the team can actively de-risk.",
        },
    ]

    # Check if any starter Questions already exist (simple heuristic for now)
    # Use direct API call (per_page=100 sufficient; matches labels/epics patterns in health.py)
    existing_questions = gh.api(
        f"repos/{target}/issues?labels=Question&state=open&per_page=100"
    ) or []
    has_starter_questions = any(
        q.get("title", "").startswith("[Question]:") for q in existing_questions
    )

    if not has_starter_questions:
        if apply_mode:
            for q in starter_questions:
                gh.api(
                    f"repos/{target}/issues",
                    method="POST",
                    fields={
                        "title": q["title"],
                        "body": q["body"],
                        "labels": ["Question"],
                    },
                )
            state = "applied"
            detail = f"Seeded {len(starter_questions)} initial Curiosity Questions"
        else:
            state = "planned"
            detail = f"Seed {len(starter_questions)} initial Curiosity Questions (project purpose, users, risks)"
        actions.append(BootstrapAction(name="seed-initial-questions", state=state, detail=detail))
    else:
        actions.append(
            BootstrapAction(
                name="seed-initial-questions",
                state="already-configured",
                detail="Initial Curiosity Questions already present",
            )
        )

    if health.branch_protection_enabled:
        actions.append(
            BootstrapAction(name="branch-protection", state="already-configured", detail="Default branch protection enabled")
        )
    else:
        actions.append(
            BootstrapAction(
                name="branch-protection",
                state="manual-required",
                detail="Enable branch protection manually (repo policy-specific settings required).",
            )
        )

    # Release track branches (refined multi-track model per release-ceremony-refinement Epic #306).
    # Creates the permissive next-* branches for Major/Minor/Patch tracks (associated with standing "Next Release").
    # Legacy single "release" is still created for transition/compat with old ceremony.
    # Versioned release-vX.Y.Z branches are created later during packaging (not in bootstrap).
    track_branches = ["release-major", "release-minor", "release-patch", "release"]
    for branch_name in track_branches:
        try:
            gh.api(f"repos/{target}/branches/{branch_name}")
            actions.append(
                BootstrapAction(
                    name=f"create-{branch_name}-branch",
                    state="already-configured",
                    detail=f"{branch_name} branch already exists",
                )
            )
        except Exception:
            if apply_mode:
                repo_obj_fresh = gh.api(f"repos/{target}")
                default_branch = repo_obj_fresh.get("default_branch", "main")
                branch_data = gh.api(f"repos/{target}/branches/{default_branch}")
                sha = branch_data["commit"]["sha"]
                gh.api(
                    f"repos/{target}/git/refs",
                    method="POST",
                    fields={"ref": f"refs/heads/{branch_name}", "sha": sha},
                )
                state = "applied"
                detail = f"Created {branch_name} branch from {default_branch} at {sha[:7]}"
            else:
                state = "planned"
                if branch_name == "release":
                    detail = (
                        f"Create legacy '{branch_name}' branch from main (for transition). "
                        "Protect appropriately. See docs/design/release-ceremony-refinement.md and AGENTS.md for the refined 3-track model (release-major/minor/patch as permissive next- integrators; versioned release-v* created at packaging time)."
                    )
                else:
                    detail = (
                        f"Create '{branch_name}' branch from main. "
                        "This is a permissive 'next' integration branch for the corresponding Major/Minor/Patch track during active development toward the standing Next Release. "
                        "After creation, protect it (PRs required; status checks like main). Versioned branches and hard-resets happen at packaging/finalization."
                    )
            actions.append(BootstrapAction(name=f"create-{branch_name}-branch", state=state, detail=detail))

    return BootstrapReport(repo=target, apply_mode=apply_mode, actions=actions)
