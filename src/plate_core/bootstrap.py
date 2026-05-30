"""Bootstrap planning/apply helpers for new PLATE repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .github_client import GhClient
from .health import REQUIRED_LABELS, get_health, resolve_repo


DEFAULT_LABEL_COLOR = "5319e7"


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

    return BootstrapReport(repo=target, apply_mode=apply_mode, actions=actions)
