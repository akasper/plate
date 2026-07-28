"""Bootstrap planning/apply helpers for new PLATE repositories and adoption (#619)."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .github_client import GhApiError, GhClient
from .health import REQUIRED_LABELS, get_health, resolve_repo
from .plate_config import DEFAULT_CONFIG
from .import_payload import list_payload_relative_paths
from .template_payload import resolve_template_source


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
    template_source: str = "unknown"
    adoption_mode: bool = False
    adoption_signals: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "apply_mode": self.apply_mode,
            "template_source": self.template_source,
            "adoption_mode": self.adoption_mode,
            "adoption_signals": list(self.adoption_signals),
            "next_steps": list(self.next_steps),
            "actions": [a.to_dict() for a in self.actions],
        }


def detect_adoption_mode(
    *,
    health: Any | None = None,
    repo_obj: dict[str, Any] | None = None,
    local_root: Path | None = None,
    force_adopt: bool | None = None,
) -> tuple[bool, list[str]]:
    """Detect existing-repo adoption vs greenfield bootstrap (#619).

    Returns ``(adoption_mode, signals)``. Explicit ``force_adopt`` wins when not None.
    Heuristics (any 2+ → adopt when .plate missing, or 1+ when mature signals strong):
    - no root .plate but repo has substantial history/size
    - open issues already present (epics/questions)
    - local package.json / existing CI workflows without plate signals
    """
    if force_adopt is True:
        return True, ["flag:--adopt"]
    if force_adopt is False:
        return False, ["flag:greenfield"]

    signals: list[str] = []
    h = health
    plate_present = bool(getattr(h, "plate_config_present", False)) if h is not None else False
    if plate_present:
        # Already PLATE-ish: still surface "repair" style guidance but not full adopt path
        signals.append("health:.plate_present")
    else:
        signals.append("health:.plate_missing")

    open_epics = int(getattr(h, "open_epic_count", 0) or 0) if h is not None else 0
    open_questions = int(getattr(h, "open_question_count", 0) or 0) if h is not None else 0
    if open_epics > 0:
        signals.append(f"health:open_epics={open_epics}")
    if open_questions > 0:
        signals.append(f"health:open_questions={open_questions}")

    if isinstance(repo_obj, dict):
        if repo_obj.get("size") and int(repo_obj.get("size") or 0) > 500:
            signals.append(f"repo:size={repo_obj.get('size')}")
        if repo_obj.get("has_issues") is False:
            signals.append("repo:issues_disabled")
        # forks / non-empty description often mature
        if repo_obj.get("description"):
            signals.append("repo:has_description")
        if int(repo_obj.get("open_issues_count") or 0) > 5:
            signals.append(f"repo:open_issues={repo_obj.get('open_issues_count')}")

    root = Path(local_root) if local_root is not None else Path.cwd()
    try:
        if (root / "package.json").is_file() and not (root / ".plate").is_file():
            signals.append("local:package.json_without_.plate")
        if (root / ".github" / "workflows").is_dir():
            wf = list((root / ".github" / "workflows").glob("*.yml")) + list(
                (root / ".github" / "workflows").glob("*.yaml")
            )
            if wf and not (root / ".plate").is_file():
                signals.append(f"local:workflows_without_.plate={len(wf)}")
        if (root / "docs").is_dir() and not (root / "docs" / "wiki" / "Goals.md").is_file():
            if not plate_present:
                signals.append("local:docs_without_Goals")
    except OSError:
        pass

    mature = [
        s
        for s in signals
        if s.startswith("repo:size=")
        or s.startswith("repo:open_issues=")
        or s.startswith("local:")
        or s.startswith("health:open_epics=")
        or s.startswith("health:open_questions=")
    ]
    # Adopt when not already fully plate-present and mature signals exist
    if force_adopt is None:
        if not plate_present and len(mature) >= 1:
            return True, signals
        if plate_present and len(mature) >= 2:
            # Repair/adopt hybrid: existing PLATE signals + mature project
            return True, signals
    return False, signals


def _adoption_next_steps(*, adoption_mode: bool, health: Any) -> list[str]:
    if not adoption_mode:
        return [
            "For brand-new repos: complete docs/bootstrap/new-repository-checklist.md human steps (CODEOWNERS, protection).",
            "Run `gh plate health` after apply and seed Goals.md content.",
        ]
    steps = [
        "Adoption mode: prefer local `gh plate import-payload --strategy conservative --dry-run` then `--apply` before remote bootstrap file copy when working in a checkout.",
        "Review CODEOWNERS / @handles, docs/wiki/Goals.md mission text, and CI coexistence (product CI + PLATE enforcement).",
        "Run `gh plate health` and fix remaining gaps; use `gh plate migrate plan` if this repo was template-derived.",
        "Do not seed duplicate Epics/Questions when real planning already exists — bootstrap skips when open Epics/Questions present.",
        "See docs/migration/adoption-guide.md for the full adoption path (#619 / #633).",
    ]
    if health is not None and not getattr(health, "goals_page_present", True):
        steps.insert(1, "Seed or write docs/wiki/Goals.md (mission) for Information Audits.")
    if health is not None and not getattr(health, "plate_config_present", True):
        steps.insert(1, "Ensure root `.plate` exists (`gh plate config init` or bootstrap init-plate-config).")
    return steps


def _is_missing_content_error(error: GhApiError) -> bool:
    message = str(error).lower()
    return "404" in message or "not found" in message


def _template_payload_relative_paths(template_root: Path) -> list[str]:
    """Shared planner with import_payload (#620) — same manifest-filtered paths."""
    return list_payload_relative_paths(template_root)


def _copy_template_payload(repo: str, default_branch: str, gh: GhClient, template_root: Path) -> tuple[int, int]:
    copied = 0
    skipped = 0
    rel_paths = _template_payload_relative_paths(template_root)
    if not rel_paths:
        raise RuntimeError(f"No template payload files found under {template_root}")

    for rel in rel_paths:
        source = template_root / rel
        if not source.is_file():
            raise RuntimeError(f"Template payload file missing: {source}")

        endpoint = f"repos/{repo}/contents/{quote(rel, safe='/')}"
        try:
            gh.api(endpoint)
        except GhApiError as error:
            if not _is_missing_content_error(error):
                raise
        else:
            skipped += 1
            continue

        content = base64.b64encode(source.read_bytes()).decode("ascii")
        try:
            gh.api(
                endpoint,
                method="PUT",
                fields={
                    "message": f"Bootstrap: initialize {rel} from PLATE template payload",
                    "content": content,
                    "branch": default_branch,
                },
            )
        except GhApiError as error:
            if _is_missing_content_error(error):
                workflow_scope_hint = ""
                if rel.startswith(".github/workflows/"):
                    workflow_scope_hint = (
                        " This path is under .github/workflows/, so classic PATs must include "
                        "`workflow` scope in addition to `repo`."
                    )
                raise RuntimeError(
                    "Failed to write template payload file via GitHub contents API. "
                    f"repo={repo} branch={default_branch} path={rel}. "
                    "GitHub returned 404, which usually means the target branch ref does not exist yet, "
                    "the authenticated user/token cannot write contents, or the repository identifier is incorrect."
                    f"{workflow_scope_hint} "
                    f"Original error: {error}"
                ) from error
            raise
        copied += 1

    return copied, skipped


def _validate_bootstrap_preconditions(repo: str, repo_obj: dict, default_branch: str, gh: GhClient) -> None:
    permissions = repo_obj.get("permissions")
    if isinstance(permissions, dict) and permissions.get("push") is False:
        raise RuntimeError(
            "Bootstrap requires repository contents write permission, but GitHub reports push=false "
            f"for {repo}. Authenticate with an account/token that can push to the repository."
        )

    ref_endpoint = f"repos/{repo}/git/ref/heads/{quote(default_branch, safe='')}"
    try:
        gh.api(ref_endpoint)
    except GhApiError as error:
        if _is_missing_content_error(error):
            raise RuntimeError(
                f"Bootstrap requires an existing default branch ref ('{default_branch}') in {repo}, "
                "but it was not found. If this is a brand-new empty repository, create an initial commit "
                "(for example README.md on the default branch) and rerun `gh plate bootstrap --apply`."
            ) from error
        raise


def run_bootstrap(
    repo: str | None = None,
    apply_mode: bool = False,
    client: GhClient | None = None,
    *,
    adopt: bool | None = None,
    local_root: str | Path | None = None,
) -> BootstrapReport:
    """Plan/apply baseline PLATE bootstrap.

    ``adopt``: True force adoption mode, False force greenfield, None auto-detect (#619).
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    health = get_health(target, gh)
    repo_obj = gh.api(f"repos/{target}")
    default_branch = repo_obj.get("default_branch", "main")
    actions: list[BootstrapAction] = []

    adoption_mode, adoption_signals = detect_adoption_mode(
        health=health,
        repo_obj=repo_obj if isinstance(repo_obj, dict) else {},
        local_root=Path(local_root) if local_root is not None else Path.cwd(),
        force_adopt=adopt,
    )
    actions.append(
        BootstrapAction(
            name="adoption-mode",
            state="detected" if adoption_mode else "greenfield",
            detail=(
                f"adoption_mode={adoption_mode}; signals={', '.join(adoption_signals[:8]) or 'none'}"
            ),
        )
    )

    template_root, template_source = resolve_template_source()
    template_paths = _template_payload_relative_paths(template_root)
    actions.append(
        BootstrapAction(
            name="template-source",
            state="detected",
            detail=f"{template_source} ({template_root})",
        )
    )
    if apply_mode:
        _validate_bootstrap_preconditions(target, repo_obj, default_branch, gh)
        copied_count, skipped_count = _copy_template_payload(target, default_branch, gh, template_root)
        if copied_count:
            state = "applied"
            detail = f"Copied {copied_count} template payload files into the repository from {template_source}"
            if skipped_count:
                detail += f" and skipped {skipped_count} existing file{'s' if skipped_count != 1 else ''}"
        else:
            state = "already-configured"
            detail = (
                f"Template payload already present from {template_source} "
                f"({skipped_count} existing file{'s' if skipped_count != 1 else ''})"
            )
    else:
        state = "planned"
        if adoption_mode:
            detail = (
                f"Prefer local `gh plate import-payload --strategy conservative` for checkout files; "
                f"remote would copy {len(template_paths)} template payload files from {template_source} "
                f"(skips existing paths)"
            )
        else:
            detail = f"Copy {len(template_paths)} template payload files into the repository from {template_source}"
    actions.append(BootstrapAction(name="copy-template-payload", state=state, detail=detail))

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

    # Feature #153 / #949 / #951: shared starter catalog; write first_qa marker on apply.
    from .adoption import (
        STARTER_QUESTIONS,
        first_qa_seed_status,
        write_first_qa_seed_marker,
    )

    starter_questions = list(STARTER_QUESTIONS)
    local_checkout = Path(local_root) if local_root is not None else Path.cwd()

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
            marker = write_first_qa_seed_marker(
                local_checkout,
                titles=[q["title"] for q in starter_questions],
                mode="bootstrap_apply",
            )
            state = "applied"
            detail = (
                f"Seeded {len(starter_questions)} initial Curiosity Questions; "
                f"first_qa marker written ({marker.get('marker_path')})"
            )
        else:
            state = "planned"
            detail = f"Seed {len(starter_questions)} initial Curiosity Questions (project purpose, users, risks)"
        actions.append(BootstrapAction(name="seed-initial-questions", state=state, detail=detail))
    else:
        detail = "Initial Curiosity Questions already present"
        if apply_mode and not first_qa_seed_status(local_checkout).get("seeded"):
            # Sync offline marker so what_next does not re-queue first_qa_seed (#951)
            titles = [
                str(q.get("title") or "")
                for q in existing_questions
                if str(q.get("title") or "").startswith("[Question]:")
            ]
            if not titles:
                titles = [q["title"] for q in starter_questions]
            marker = write_first_qa_seed_marker(
                local_checkout,
                titles=titles[:10],
                mode="bootstrap_sync",
            )
            detail = (
                f"Initial Curiosity Questions already present; "
                f"first_qa marker synced ({marker.get('marker_path')})"
            )
        actions.append(
            BootstrapAction(
                name="seed-initial-questions",
                state="already-configured",
                detail=detail,
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

    next_steps = _adoption_next_steps(adoption_mode=adoption_mode, health=health)
    return BootstrapReport(
        repo=target,
        apply_mode=apply_mode,
        actions=actions,
        template_source=template_source,
        adoption_mode=adoption_mode,
        adoption_signals=adoption_signals,
        next_steps=next_steps,
    )
