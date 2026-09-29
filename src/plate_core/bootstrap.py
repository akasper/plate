"""Bootstrap planning/apply helpers for new PLATE repositories and adoption (#619)."""

from __future__ import annotations

import base64
import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .github_client import GhApiError, GhClient
from .health import REQUIRED_LABELS, get_health, resolve_repo
from .import_payload import list_payload_relative_paths
from .payload_surface import filter_plate_scripts, prepare_copied_text, resolve_local_goals_wiki
from .plate_config import ALLOWED_PLATFORMS, DEFAULT_CONFIG, PLATFORM_POSIX, PlateConfigError
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
    platform: str = "posix"
    adoption_mode: bool = False
    adoption_signals: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "apply_mode": self.apply_mode,
            "template_source": self.template_source,
            "platform": self.platform,
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
        if (root / "docs").is_dir():
            _goals_path, _goals_rel, goals_present = resolve_local_goals_wiki(root)
            if not goals_present and not plate_present:
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
        "Review CODEOWNERS / @handles, the Goals wiki mission text (docs/wiki/Goals.md, or docs/plate/wiki/Goals.md when PLATE docs are namespaced), and CI coexistence (product CI + PLATE enforcement).",
        "Run `gh plate health` and fix remaining gaps; use `gh plate migrate plan` if this repo was template-derived.",
        "Do not seed duplicate Epics/Questions when real planning already exists — bootstrap skips when open Epics/Questions present.",
        "See docs/migration/adoption-guide.md for the full adoption path (#619 / #633).",
    ]
    if health is not None and not getattr(health, "goals_page_present", True):
        steps.insert(
            1,
            "Seed or write the Goals wiki page (docs/wiki/Goals.md, or docs/plate/wiki/Goals.md when PLATE docs are namespaced) for Information Audits.",
        )
    if health is not None and not getattr(health, "plate_config_present", True):
        steps.insert(1, "Ensure root `.plate` exists (`gh plate config init` or bootstrap init-plate-config).")
    return steps


def _is_missing_content_error(error: GhApiError) -> bool:
    message = str(error).lower()
    return "404" in message or "not found" in message


def _template_payload_relative_paths(template_root: Path) -> list[str]:
    """Shared planner with import_payload (#620) — same manifest-filtered paths."""
    return list_payload_relative_paths(template_root)


def _decode_github_text(payload: Any) -> str | None:
    """Decode a GitHub contents API file body. Missing or empty content is None."""
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        raw = base64.b64decode(content)
    except (ValueError, TypeError):
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def resolve_bootstrap_platform(
    explicit: str | None,
    repo: str,
    gh: GhClient,
    *,
    plate_config_present: bool,
) -> str:
    """Explicit argument wins, then a readable remote ``.plate``, then ``posix``.

    Any explicit value, including ``""`` and whitespace, is validated before
    the remote file is read. A missing file, missing key, JSON null, or
    unreadable body falls back to ``posix`` only when no explicit value was
    passed. JSON that does not parse, a non-object document, and a platform
    outside the enum fail closed.
    """
    if explicit is not None:
        if not isinstance(explicit, str):
            allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
            raise PlateConfigError(f"invalid platform: {explicit!r} (allowed: {allowed})")
        value = explicit.strip()
        if value not in ALLOWED_PLATFORMS:
            allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
            raise PlateConfigError(f"invalid platform: {explicit!r} (allowed: {allowed})")
        return value
    if not plate_config_present:
        return PLATFORM_POSIX
    endpoint = f"repos/{repo}/contents/.plate"
    try:
        payload = gh.api(endpoint)
    except GhApiError as error:
        if _is_missing_content_error(error):
            return PLATFORM_POSIX
        raise
    text = _decode_github_text(payload)
    if not text or not text.strip():
        return PLATFORM_POSIX
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlateConfigError(f"invalid JSON in .plate: {exc}") from exc
    if not isinstance(data, dict):
        raise PlateConfigError(".plate must contain a top-level object")
    stored = data.get("platform")
    if stored is None:
        return PLATFORM_POSIX
    if not isinstance(stored, str) or stored not in ALLOWED_PLATFORMS:
        allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
        raise PlateConfigError(f"invalid platform: {stored!r} (allowed: {allowed})")
    return stored


def _load_existing_remote_plate(repo: str, gh: GhClient) -> tuple[dict[str, Any], str] | None:
    """Parse an existing remote ``.plate`` before bootstrap writes anything.

    Returns ``None`` when the file is absent. An unreadable body, invalid JSON,
    a non-object, or a missing blob sha raises ``RuntimeError``.
    """
    endpoint = f"repos/{repo}/contents/.plate"
    try:
        payload = gh.api(endpoint)
    except GhApiError as error:
        if _is_missing_content_error(error):
            return None
        raise
    text = _decode_github_text(payload)
    sha = payload.get("sha") if isinstance(payload, dict) else None
    if text is None:
        raise RuntimeError("Cannot update .plate platform: remote .plate content is unreadable.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Cannot update .plate platform: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Cannot update .plate platform: .plate is not a JSON object.")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError("Cannot update .plate platform: GitHub contents response has no sha.")
    return data, sha


def _write_remote_plate_platform(
    repo: str,
    branch: str,
    gh: GhClient,
    data: dict[str, Any],
    sha: str,
    platform: str,
) -> None:
    """PUT ``platform`` onto a ``.plate`` object that was already parsed."""
    if data.get("platform") == platform:
        return
    updated = dict(data)
    updated["platform"] = platform
    encoded = base64.b64encode((json.dumps(updated, indent=2) + "\n").encode("utf-8")).decode("ascii")
    gh.api(
        f"repos/{repo}/contents/.plate",
        method="PUT",
        fields={
            "message": f"Bootstrap: set .plate platform to {platform}",
            "content": encoded,
            "sha": sha,
            "branch": branch,
        },
    )


def _platform_copy_suffix(platform: str, omitted: list[str]) -> str:
    suffix = f" for platform {platform}"
    if omitted:
        suffix += f"; omitted {len(omitted)} PLATE-owned script twin(s)"
    return suffix


def _copy_template_payload(
    repo: str,
    default_branch: str,
    gh: GhClient,
    template_root: Path,
    *,
    platform: str,
) -> tuple[int, int]:
    copied = 0
    skipped = 0
    rel_paths, _omitted = filter_plate_scripts(_template_payload_relative_paths(template_root), platform)
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

        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            encoded = raw
        else:
            text = prepare_copied_text(rel, text, platform, namespaced=False)
            encoded = text.encode("utf-8")
        content = base64.b64encode(encoded).decode("ascii")
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
    platform: str | None = None,
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
    explicit_platform = platform is not None and str(platform).strip() != ""
    resolved_platform = resolve_bootstrap_platform(
        platform,
        target,
        gh,
        plate_config_present=bool(getattr(health, "plate_config_present", False)),
    )
    template_paths, omitted_paths = filter_plate_scripts(
        _template_payload_relative_paths(template_root),
        resolved_platform,
    )
    platform_suffix = _platform_copy_suffix(resolved_platform, omitted_paths)
    # An explicit platform persisted onto an existing .plate must be parsed
    # before any apply write. A bad body fails the plan and the apply alike.
    pending_plate: tuple[dict[str, Any], str] | None = None
    if explicit_platform and bool(getattr(health, "plate_config_present", False)):
        pending_plate = _load_existing_remote_plate(target, gh)
    actions.append(
        BootstrapAction(
            name="template-source",
            state="detected",
            detail=f"{template_source} ({template_root})",
        )
    )
    if apply_mode:
        _validate_bootstrap_preconditions(target, repo_obj, default_branch, gh)
        if pending_plate is not None:
            plate_data, plate_sha = pending_plate
            _write_remote_plate_platform(
                target,
                default_branch,
                gh,
                plate_data,
                plate_sha,
                resolved_platform,
            )
        copied_count, skipped_count = _copy_template_payload(
            target,
            default_branch,
            gh,
            template_root,
            platform=resolved_platform,
        )
        if copied_count:
            state = "applied"
            detail = (
                f"Copied {copied_count} template payload files into the repository from {template_source}"
                f"{platform_suffix}"
            )
            if skipped_count:
                detail += f" and skipped {skipped_count} existing file{'s' if skipped_count != 1 else ''}"
        else:
            state = "already-configured"
            detail = (
                f"Template payload already present from {template_source} "
                f"({skipped_count} existing file{'s' if skipped_count != 1 else ''})"
                f"{platform_suffix}"
            )
    else:
        state = "planned"
        if adoption_mode:
            detail = (
                f"Prefer local `gh plate import-payload --strategy conservative` for checkout files; "
                f"remote would copy {len(template_paths)} template payload files from {template_source}"
                f"{platform_suffix} (skips existing paths)"
            )
        else:
            detail = (
                f"Copy {len(template_paths)} template payload files into the repository from {template_source}"
                f"{platform_suffix}"
            )
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
            seeded = copy.deepcopy(DEFAULT_CONFIG)
            seeded["platform"] = resolved_platform
            content = base64.b64encode((json.dumps(seeded, indent=2) + "\n").encode("utf-8")).decode("ascii")
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
            detail = f"Initialized root .plate baseline config (platform {resolved_platform})"
        else:
            state = "planned"
            detail = f"Initialize root .plate baseline config (platform {resolved_platform})"
        actions.append(BootstrapAction(name="init-plate-config", state=state, detail=detail))
    else:
        actions.append(
            BootstrapAction(
                name="init-plate-config",
                state="already-configured",
                detail="Root .plate config already present",
            )
        )
        if explicit_platform:
            plat_state = "applied" if apply_mode else "planned"
            actions.append(
                BootstrapAction(
                    name="set-plate-platform",
                    state=plat_state,
                    detail=f"Set root .plate platform to {resolved_platform}",
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
        platform=resolved_platform,
        adoption_mode=adoption_mode,
        adoption_signals=adoption_signals,
        next_steps=next_steps,
    )
