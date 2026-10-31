"""Bootstrap planning/apply helpers for new PLATE repositories and adoption (#619)."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .github_client import GhApiError, GhClient
from .github_labels import prepare_label_description, sync_repository_labels_from_registry
from .health import get_health, resolve_repo
from .import_payload import list_payload_relative_paths
from .payload_surface import filter_plate_scripts, prepare_copied_text, resolve_local_goals_wiki
from .plate_config import (
    ALLOWED_PLATFORMS,
    DEFAULT_CONFIG,
    PLATFORM_POSIX,
    PlateConfigError,
    format_epic_title,
)
from .template_payload import resolve_template_source


DEFAULT_LABEL_COLOR = "5319e7"
BOOTSTRAP_EPIC_MILESTONE_TITLE = "Initial milestone"
BOOTSTRAP_SEED_EPIC_NAME = "initial-plate-epic"


def _resolve_bootstrap_epic_milestone_number(
    gh: GhClient,
    repo: str,
    *,
    apply: bool,
) -> int | None:
    """Return milestone number for the bootstrap Epic (create if missing when applying)."""
    try:
        milestones = gh.api(f"repos/{repo}/milestones?state=open&per_page=100") or []
    except GhApiError:
        milestones = []
    if isinstance(milestones, list):
        for item in milestones:
            if isinstance(item, dict) and item.get("title") == BOOTSTRAP_EPIC_MILESTONE_TITLE:
                return int(item["number"])
    if not apply:
        return None
    created = gh.api(
        f"repos/{repo}/milestones",
        method="POST",
        fields={"title": BOOTSTRAP_EPIC_MILESTONE_TITLE},
    )
    if isinstance(created, dict) and created.get("number") is not None:
        return int(created["number"])
    return None


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
            "Optional: set hooks.pre_push commands in .plate and run `gh plate hooks install` (docs/bootstrap/pre-push-hook.md).",
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


def _is_empty_repository_error(error: GhApiError) -> bool:
    message = str(error).lower()
    return "409" in message and "empty" in message


def _put_repository_file(
    gh: GhClient,
    repo: str,
    rel_path: str,
    *,
    message: str,
    encoded_bytes: bytes,
    branch: str | None = None,
    sha: str | None = None,
) -> None:
    """Create or update a file via the GitHub contents API (JSON body, not argv)."""
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(encoded_bytes).decode("ascii"),
    }
    if branch:
        body["branch"] = branch
    if sha:
        body["sha"] = sha
    endpoint = f"repos/{repo}/contents/{quote(rel_path, safe='/')}"
    gh.api(endpoint, method="PUT", fields=body)


def _local_template_file_bytes(rel: str, source: Path, platform: str) -> bytes:
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    text = prepare_copied_text(rel, text, platform, namespaced=False)
    return text.encode("utf-8")


def _remote_file_digest(payload: Any) -> str | None:
    """Return SHA-256 hex digest of remote file bytes, or None if unavailable (#1257)."""
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if not isinstance(content, str):
        return None
    try:
        raw = base64.b64decode(content, validate=False)
    except (ValueError, TypeError):
        return None
    return hashlib.sha256(raw).hexdigest()


def _ensure_default_branch_ref(repo: str, default_branch: str, gh: GhClient) -> None:
    """Ensure the default branch ref exists; create an initial commit on empty repos."""
    ref_endpoint = f"repos/{repo}/git/ref/heads/{quote(default_branch, safe='')}"
    try:
        gh.api(ref_endpoint)
        return
    except GhApiError as error:
        if not (_is_missing_content_error(error) or _is_empty_repository_error(error)):
            raise

    readme = (
        "# Repository\n\n"
        "Initial commit created by `gh plate bootstrap --greenfield --apply`.\n"
    )
    try:
        _put_repository_file(
            gh,
            repo,
            "README.md",
            message="Bootstrap: initial commit for PLATE greenfield setup",
            encoded_bytes=readme.encode("utf-8"),
        )
    except GhApiError as error:
        if _is_empty_repository_error(error):
            # Retry without branch — empty repos accept the first contents PUT only.
            _put_repository_file(
                gh,
                repo,
                "README.md",
                message="Bootstrap: initial commit for PLATE greenfield setup",
                encoded_bytes=readme.encode("utf-8"),
            )
        else:
            raise

    try:
        gh.api(ref_endpoint)
    except GhApiError as error:
        raise RuntimeError(
            f"Bootstrap could not create or verify default branch ref '{default_branch}' in {repo}. "
            f"Original error: {error}"
        ) from error


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
    _put_repository_file(
        gh,
        repo,
        ".plate",
        message=f"Bootstrap: set .plate platform to {platform}",
        encoded_bytes=(json.dumps(updated, indent=2) + "\n").encode("utf-8"),
        branch=branch,
        sha=sha,
    )


def _platform_copy_suffix(platform: str, omitted: list[str]) -> str:
    suffix = f" for platform {platform}"
    if omitted:
        suffix += f"; omitted {len(omitted)} PLATE-owned script twin(s)"
    return suffix


BOOTSTRAP_STALE_UPGRADE_POINTER = (
    "Stale template files: run `gh plate self-migrate --plan`, then "
    "`gh plate import-payload --strategy conservative` (review changes in a PR before `--apply`)."
)


def _format_skipped_files_phrase(skipped_paths: list[str], *, stale: bool = False) -> str:
    """Human-readable skipped-file summary for bootstrap output (#1267, #1257)."""
    if not skipped_paths:
        return ""
    count = len(skipped_paths)
    noun = "file" if count == 1 else "files"
    cap = 20
    shown = skipped_paths[:cap]
    listing = ", ".join(shown)
    if count > cap:
        listing += f", and {count - cap} more"
    verb = "skipped but stale" if stale else "skipped"
    return f"{verb} {count} existing {noun} ({listing})"


def _append_skip_phrases_to_detail(detail: str, *, identical: list[str], stale: list[str]) -> str:
    phrases = [
        _format_skipped_files_phrase(identical),
        _format_skipped_files_phrase(stale, stale=True),
    ]
    extras = [p for p in phrases if p]
    if not extras:
        return detail
    joined = "; ".join(extras)
    if stale:
        joined += f". {BOOTSTRAP_STALE_UPGRADE_POINTER}"
    if detail.endswith("."):
        return f"{detail} {joined}"
    return f"{detail}; {joined}"


def _resolve_bootstrap_epic_title(
    gh: GhClient,
    target: str,
    *,
    plate_config_present: bool,
) -> str:
    """Title for the seeded Epic using ``.plate`` ``epic_naming_pattern`` when readable."""
    config: dict[str, Any] | None
    if plate_config_present:
        loaded = _load_existing_remote_plate(target, gh)
        config = loaded[0] if loaded else None
    else:
        config = copy.deepcopy(DEFAULT_CONFIG)
    return format_epic_title(BOOTSTRAP_SEED_EPIC_NAME, config=config)


def _process_template_payload(
    repo: str,
    default_branch: str,
    gh: GhClient,
    template_root: Path,
    *,
    platform: str,
    write_missing: bool,
) -> tuple[int, list[str], list[str]]:
    """Classify remote template paths; optionally create missing files (#1257).

    Returns ``(copied_or_would_copy, skipped_identical_paths, skipped_stale_paths)``.
    """
    copied_or_would = 0
    skipped_identical: list[str] = []
    skipped_stale: list[str] = []
    rel_paths, _omitted = filter_plate_scripts(_template_payload_relative_paths(template_root), platform)
    if not rel_paths:
        raise RuntimeError(f"No template payload files found under {template_root}")

    for rel in rel_paths:
        source = template_root / rel
        if not source.is_file():
            raise RuntimeError(f"Template payload file missing: {source}")

        endpoint = f"repos/{repo}/contents/{quote(rel, safe='/')}"
        remote_payload: Any | None = None
        try:
            remote_payload = gh.api(endpoint)
        except GhApiError as error:
            if not _is_missing_content_error(error) and not _is_empty_repository_error(error):
                raise
        else:
            local_digest = hashlib.sha256(_local_template_file_bytes(rel, source, platform)).hexdigest()
            remote_digest = _remote_file_digest(remote_payload)
            if remote_digest is None:
                skipped_stale.append(rel)
                continue
            if remote_digest == local_digest:
                skipped_identical.append(rel)
                continue
            skipped_stale.append(rel)
            continue

        if not write_missing:
            copied_or_would += 1
            continue

        encoded = _local_template_file_bytes(rel, source, platform)
        try:
            _put_repository_file(
                gh,
                repo,
                rel,
                message=f"Bootstrap: initialize {rel} from PLATE template payload",
                encoded_bytes=encoded,
                branch=default_branch,
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
        copied_or_would += 1

    return copied_or_would, skipped_identical, skipped_stale


def _validate_bootstrap_preconditions(repo: str, repo_obj: dict, default_branch: str, gh: GhClient) -> None:
    permissions = repo_obj.get("permissions")
    if isinstance(permissions, dict) and permissions.get("push") is False:
        raise RuntimeError(
            "Bootstrap requires repository contents write permission, but GitHub reports push=false "
            f"for {repo}. Authenticate with an account/token that can push to the repository."
        )

    _ensure_default_branch_ref(repo, default_branch, gh)


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
    local_checkout = Path(local_root) if local_root is not None else Path.cwd()
    health = get_health(target, gh, repo_root=str(local_checkout))
    repo_obj = gh.api(f"repos/{target}")
    default_branch = repo_obj.get("default_branch", "main")
    actions: list[BootstrapAction] = []

    adoption_mode, adoption_signals = detect_adoption_mode(
        health=health,
        repo_obj=repo_obj if isinstance(repo_obj, dict) else {},
        local_root=local_checkout,
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
    skipped_identical_paths: list[str] = []
    skipped_stale_paths: list[str] = []
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
        copied_count, skipped_identical_paths, skipped_stale_paths = _process_template_payload(
            target,
            default_branch,
            gh,
            template_root,
            platform=resolved_platform,
            write_missing=True,
        )
        if copied_count:
            state = "applied"
            detail = (
                f"Copied {copied_count} template payload files into the repository from {template_source}"
                f"{platform_suffix}"
            )
        else:
            state = "already-configured"
            detail = (
                f"Template payload already present from {template_source} "
                f"(no new files copied){platform_suffix}"
            )
        detail = _append_skip_phrases_to_detail(
            detail,
            identical=skipped_identical_paths,
            stale=skipped_stale_paths,
        )
    else:
        would_copy, skipped_identical_paths, skipped_stale_paths = _process_template_payload(
            target,
            default_branch,
            gh,
            template_root,
            platform=resolved_platform,
            write_missing=False,
        )
        state = "planned"
        if adoption_mode:
            detail = (
                f"Prefer local `gh plate import-payload --strategy conservative` for checkout files; "
                f"remote would copy {would_copy} missing template payload file(s) from {template_source}"
                f"{platform_suffix} (skips existing paths)"
            )
        else:
            detail = (
                f"Would copy {would_copy} missing template payload file(s) into the repository from "
                f"{template_source}{platform_suffix}"
            )
        detail = _append_skip_phrases_to_detail(
            detail,
            identical=skipped_identical_paths,
            stale=skipped_stale_paths,
        )
    actions.append(BootstrapAction(name="copy-template-payload", state=state, detail=detail))

    checkout_registry = local_checkout / ".github" / "labels.yml"
    bundled_registry = template_root / ".github" / "labels.yml"
    if checkout_registry.is_file():
        labels_registry = checkout_registry
    elif bundled_registry.is_file():
        labels_registry = bundled_registry
    else:
        labels_registry = None

    if labels_registry is not None:
        label_outcomes = sync_repository_labels_from_registry(
            gh,
            target,
            labels_registry,
            apply=apply_mode,
        )
        for outcome in label_outcomes:
            actions.append(
                BootstrapAction(
                    name="sync-label",
                    state=outcome.state,
                    detail=outcome.detail,
                )
            )
    else:
        for label in health.missing_labels:
            description, _desc_warning = prepare_label_description(f"PLATE label: {label}")
            if apply_mode:
                try:
                    gh.api(
                        f"repos/{target}/labels",
                        method="POST",
                        fields={
                            "name": label,
                            "color": DEFAULT_LABEL_COLOR,
                            "description": description,
                        },
                    )
                    state = "applied"
                    detail = label
                except GhApiError as exc:
                    state = "failed"
                    detail = f"{label}: {exc}"
            else:
                state = "planned"
                detail = label
            actions.append(BootstrapAction(name="sync-label", state=state, detail=detail))

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
            _put_repository_file(
                gh,
                target,
                ".plate",
                message="Bootstrap: initialize .plate baseline config",
                encoded_bytes=(json.dumps(seeded, indent=2) + "\n").encode("utf-8"),
                branch=default_branch,
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
            milestone_number = _resolve_bootstrap_epic_milestone_number(gh, target, apply=True)
            epic_fields: dict[str, Any] = {
                "title": _resolve_bootstrap_epic_title(
                    gh,
                    target,
                    plate_config_present=health.plate_config_present,
                ),
                "body": "Bootstrap-created initial Epic for project setup.",
                "labels": ["Epic"],
            }
            if milestone_number is not None:
                epic_fields["milestone"] = milestone_number
            gh.api(
                f"repos/{target}/issues",
                method="POST",
                fields=epic_fields,
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

    actions.append(
        BootstrapAction(
            name="pre-push-hook",
            state="manual-required",
            detail=(
                "Optional local checks: configure hooks.pre_push format/lint/typecheck in .plate, "
                "then run `gh plate hooks install` (docs/bootstrap/pre-push-hook.md). "
                "Passes silently when no commands are set (#1281)."
            ),
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
    if skipped_stale_paths:
        next_steps = list(next_steps) + [BOOTSTRAP_STALE_UPGRADE_POINTER]
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
