"""Release status and notes diff surfaces shared across CLI and MCP."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .version_sync import find_repo_root, read_repository_versions, sync_repository_version


@dataclass
class FragmentSummary:
    slug: str
    change_type: str
    surface: str
    summary: str
    links: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReleaseStatusReport:
    repo: str
    release_branch_exists: bool
    release_track_branches: dict
    release_branch_mode: str
    release_branch_reset_target: str
    warnings: list[str]
    open_release_issues: list[dict]
    current_version: str | None
    latest_version: str | None
    pending_fragment_count: int
    pending_fragments: list[FragmentSummary]
    extension_release_checks: list[dict]
    # Refined ceremony (Epic #306): standing Next Release + track visibility + on-hold Epics via native links.
    active_next_release: dict | None = None
    linked_epics: list[dict] = field(default_factory=list)
    on_hold_epics: list[dict] = field(default_factory=list)
    release_track_summary: dict = field(default_factory=dict)  # e.g. {"Major": 3, "Minor": 5, "Patch": 2}

    def to_dict(self) -> dict:
        d = {
            "repo": self.repo,
            "release_branch_exists": self.release_branch_exists,
            "release_track_branches": self.release_track_branches,
            "release_branch_mode": self.release_branch_mode,
            "release_branch_reset_target": self.release_branch_reset_target,
            "warnings": self.warnings,
            "open_release_issues": self.open_release_issues,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "pending_fragment_count": self.pending_fragment_count,
            "pending_fragments": [f.to_dict() for f in self.pending_fragments],
            "extension_release_checks": self.extension_release_checks,
            "active_next_release": self.active_next_release,
            "linked_epics": self.linked_epics,
            "on_hold_epics": self.on_hold_epics,
            "release_track_summary": self.release_track_summary,
        }
        return d


@dataclass
class ReleaseTargetEpicGuidance:
    repo: str
    epic: dict | None
    active_next_release: dict | None
    can_target: bool
    api_write_supported: bool
    message: str
    manual_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReleaseNotesDiffReport:
    from_version: str | None
    to_version: str | None
    releases_found: list[str]
    entries: list[dict]
    migration_steps: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeadBranchCleanupReport:
    repo: str
    base_branch: str
    apply: bool
    scanned_branches: int
    candidates: list[str]
    deleted: list[str]
    failed: list[dict]
    skipped_open_pr: list[str]
    skipped_not_merged: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReleaseWorkspaceValidationReport:
    repo_root: str
    release_version: str | None
    release_tag: str | None
    version_files: dict[str, str]
    release_file: str | None
    release_file_version: str | None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _list_versions(releases_dir: Path) -> list[str]:
    """Return sorted list of version strings from the releases directory."""
    versions = []

    # Legacy flat files: v0.1.0.json
    for f in releases_dir.glob("v*.json"):
        v = f.stem.lstrip("v")
        try:
            tuple(int(x) for x in v.split("."))
            versions.append(v)
        except ValueError:
            pass

    # New versioned dirs: v0.1.0/release.json
    for d in releases_dir.iterdir():
        if d.is_dir() and d.name.startswith("v"):
            release_file = d / "release.json"
            if release_file.exists():
                v = d.name.lstrip("v")
                try:
                    tuple(int(x) for x in v.split("."))
                    if v not in versions:
                        versions.append(v)
                except ValueError:
                    pass

    def _ver_key(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0,)

    return sorted(versions, key=_ver_key)


def _load_release(releases_dir: Path, version: str) -> dict | None:
    """Load a release dict from either flat file or versioned directory."""
    versioned_dir = releases_dir / f"v{version}"
    if versioned_dir.is_dir():
        release_file = versioned_dir / "release.json"
        if release_file.exists():
            return json.loads(release_file.read_text(encoding="utf-8"))
    flat = releases_dir / f"v{version}.json"
    if flat.exists():
        return json.loads(flat.read_text(encoding="utf-8"))
    return None


def _load_pending_fragments(releases_dir: Path) -> list[FragmentSummary]:
    unreleased = releases_dir / "unreleased"
    if not unreleased.exists():
        return []
    fragments = []
    for f in sorted(unreleased.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            fragments.append(
                FragmentSummary(
                    slug=data.get("slug", f.stem),
                    change_type=data.get("change_type", ""),
                    surface=data.get("surface", ""),
                    summary=data.get("summary", ""),
                    links=data.get("links", []),
                )
            )
        except Exception:
            pass
    return fragments


def validate_release_workspace(
    repo_root: Path,
    releases_dir: Path | None = None,
) -> ReleaseWorkspaceValidationReport:
    """Validate that the repository and release artifact agree on a single release version."""
    root = find_repo_root(repo_root)
    version_files = read_repository_versions(root)
    errors: list[str] = []

    discovered_versions = sorted(set(version_files.values()))
    release_version: str | None = None
    if len(discovered_versions) == 1:
        release_version = discovered_versions[0]
    else:
        mismatch_summary = ", ".join(f"{path}={version}" for path, version in version_files.items())
        errors.append(f"Repository version files are not in sync: {mismatch_summary}.")

    release_file_path: Path | None = None
    release_file_version: str | None = None
    effective_releases_dir = releases_dir or root / ".agentic" / "releases"

    if release_version is not None:
        parsed_release_version = parse_version(release_version)
        if parsed_release_version is None:
            errors.append(f"Repository version {release_version!r} is not valid semver.")
        else:
            release_data = _load_release(effective_releases_dir, release_version)
            versioned_release_file = effective_releases_dir / f"v{release_version}" / "release.json"
            legacy_release_file = effective_releases_dir / f"v{release_version}.json"
            if versioned_release_file.exists():
                release_file_path = versioned_release_file
            elif legacy_release_file.exists():
                release_file_path = legacy_release_file

            if release_data is None:
                errors.append(
                    f"Expected release artifact for v{release_version} at "
                    f"{(effective_releases_dir / f'v{release_version}' / 'release.json').relative_to(root).as_posix()} "
                    f"or {(effective_releases_dir / f'v{release_version}.json').relative_to(root).as_posix()}."
                )
            else:
                candidate_version = release_data.get("version")
                if isinstance(candidate_version, str):
                    release_file_version = candidate_version
                else:
                    errors.append(f"Release artifact for v{release_version} is missing a string 'version' field.")
                if release_file_version is not None and release_file_version != release_version:
                    errors.append(
                        f"Release artifact version {release_file_version!r} does not match synced repository version {release_version!r}."
                    )

    return ReleaseWorkspaceValidationReport(
        repo_root=str(root),
        release_version=release_version,
        release_tag=f"v{release_version}" if release_version is not None else None,
        version_files=version_files,
        release_file=release_file_path.relative_to(root).as_posix() if release_file_path is not None else None,
        release_file_version=release_file_version,
        errors=errors,
    )


def _load_extension_release_checks(agentic_dir: Path) -> list[dict]:
    """Read release_checks from .agentic/extensions.yml if present.

    Uses indent-aware state machine (not regex-only) to correctly distinguish
    extension-level '- id:' from nested release_checks '- id:' items.
    """
    extensions_file = agentic_dir / "extensions.yml"
    if not extensions_file.exists():
        return []
    try:
        import re
        text = extensions_file.read_text(encoding="utf-8")
        checks = []
        current_ext: str | None = None
        in_release_checks = False
        release_checks_indent: int | None = None
        current_check: dict | None = None

        def _finish_check():
            nonlocal current_check
            if current_check is not None:
                checks.append(current_check)
            current_check = None

        for raw_line in text.splitlines():
            line = raw_line
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            leading = len(line) - len(line.lstrip(" "))
            if "\t" in line[:leading]:
                leading = len(line) - len(line.lstrip())

            # Extension id at shallow level (not inside a release_checks block)
            id_match = re.match(r'^\s+-\s+id:\s+"?([^"]+)"?', line)
            if id_match and (release_checks_indent is None or leading < (release_checks_indent or 999)):
                _finish_check()
                current_ext = id_match.group(1)
                in_release_checks = False
                release_checks_indent = None
                continue

            # Start of release_checks array under current ext
            if re.match(r'^\s+release_checks:', line):
                _finish_check()
                in_release_checks = True
                release_checks_indent = leading + 2
                continue

            # Deep in release_checks block - collect fields leniently
            if in_release_checks:
                # New check item (look for - id: at reasonable depth)
                if (stripped.startswith("- id:") or (stripped.startswith("-") and re.search(r"id:\s", stripped))) and (release_checks_indent is None or leading >= release_checks_indent - 2):
                    _finish_check()
                    check_id_match = re.search(r'id:\s+"?([^"]+)"?', line)
                    current_check = {
                        "extension_id": current_ext,
                        "id": check_id_match.group(1) if check_id_match else "",
                        "description": "",
                        "required": True,
                        "human_approval_required": False,
                        "satisfied": None,
                    }
                    # Parse any fields on the starter line
                    dm = re.search(r'description:\s+"?([^"]+)"?', line)
                    if dm: current_check["description"] = dm.group(1)
                    rm = re.search(r'^\s*required:\s+(true|false)', line)
                    if rm: current_check["required"] = rm.group(1) == "true"
                    hm = re.search(r'human_approval_required:\s+(true|false)', line)
                    if hm: current_check["human_approval_required"] = hm.group(1) == "true"
                    hml = re.search(r'human_approval:\s+(true|false)', line)
                    if hml and not hm: current_check["human_approval_required"] = hml.group(1) == "true"
                    continue

                # Field lines for the open current check (lenient, as long as we are in block)
                if current_check is not None:
                    dm = re.search(r'description:\s+"?([^"]+)"?', line)
                    if dm and not current_check.get("description"):
                        current_check["description"] = dm.group(1)
                    rm = re.search(r'^\s*required:\s+(true|false)', line)
                    if rm:
                        current_check["required"] = rm.group(1) == "true"
                    hm = re.search(r'human_approval_required:\s+(true|false)', line)
                    if hm:
                        current_check["human_approval_required"] = hm.group(1) == "true"
                    hml = re.search(r'human_approval:\s+(true|false)', line)
                    if hml and not hm:
                        current_check["human_approval_required"] = hml.group(1) == "true"
                    continue

            # Exiting the block
            if in_release_checks and release_checks_indent is not None and leading < release_checks_indent and stripped.startswith(("-", "extensions", "  - id:")):
                _finish_check()
                in_release_checks = False
                release_checks_indent = None
                # allow reprocessing id if it was an ext id
                if id_match:
                    current_ext = id_match.group(1)
                continue

        _finish_check()
        return checks
    except Exception:
        return []


def get_release_status(
    repo: str | None = None,
    releases_dir: Path | None = None,
    client: GhClient | None = None,
) -> ReleaseStatusReport:
    """Return the current release status for a repository."""
    gh = client or GhClient()
    target = resolve_repo(repo)

    def _branch_exists(branch_name: str) -> bool:
        try:
            gh.api(f"repos/{target}/branches/{branch_name}")
            return True
        except GhApiError:
            return False

    release_track_branches = {
        "release": _branch_exists("release"),
        "release-major": _branch_exists("release-major"),
        "release-minor": _branch_exists("release-minor"),
        "release-patch": _branch_exists("release-patch"),
    }
    release_branch_exists = release_track_branches["release"]
    tracks_present = [b for b in ["release-major", "release-minor", "release-patch"] if release_track_branches[b]]
    warnings: list[str] = []
    if len(tracks_present) == 3:
        release_branch_mode = "multi-track"
    elif release_branch_exists and len(tracks_present) == 0:
        release_branch_mode = "legacy"
        warnings.append(
            "Legacy release mode detected: track branches release-major/release-minor/release-patch are missing; "
            "feature work falls back to release. Run 'gh plate bootstrap --apply' to repair standing track branches."
        )
    elif release_branch_exists and 0 < len(tracks_present) < 3:
        release_branch_mode = "hybrid"
        missing = [b for b in ["release-major", "release-minor", "release-patch"] if b not in tracks_present]
        warnings.append(
            "Hybrid release mode detected: partial track branch state; missing "
            + ", ".join(missing)
            + ". Run 'gh plate bootstrap --apply' to repair standing track branches."
        )
    elif not release_branch_exists and len(tracks_present) > 0:
        release_branch_mode = "track-only"
        warnings.append(
            "Track branches exist but legacy release is missing. Verify whether migration is complete "
            "or recreate release as needed for compatibility."
        )
    else:
        release_branch_mode = "none"
        warnings.append(
            "No release integration branches detected. Run 'gh plate bootstrap --apply' to initialize standing release branches."
        )

    # Find open Release issues
    search = gh.api(
        f"search/issues?q={quote_plus(f'repo:{target} is:issue is:open label:Release')}"
    )
    open_release_issues = [
        {"number": i["number"], "title": i["title"], "html_url": i["html_url"]}
        for i in (search.get("items") or [])
    ]

    # Refined ceremony support (Epic #306): detect standing "Next Release" and its linked Epics (via native sidebar/connected events).
    # Also compute basic track summary from open Epics/Features with Major/Minor/Patch labels, and on-hold (track label but no link to active Next).
    active_next_release = None
    linked_epics: list[dict] = []
    on_hold_epics: list[dict] = []
    release_track_summary: dict = {"Major": 0, "Minor": 0, "Patch": 0}

    active_next = next((i for i in open_release_issues if "next" in (i.get("title") or "").lower()), None)
    if active_next:
        active_next_release = active_next
        # Use GraphQL to get connected Epics (adapted from pr-issue-link-check and epics.py patterns).
        try:
            owner, repo_name = target.split("/", 1) if "/" in target else (target, target)
            gquery = """
            query($owner: String!, $repo: String!, $number: Int!) {
              repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                  closingIssuesReferences(first: 20) {
                    nodes { number title url labels(first:5){nodes{name}} }
                  }
                  timelineItems(first: 50, itemTypes: [CONNECTED_EVENT]) {
                    nodes {
                      ... on ConnectedEvent {
                        subject { __typename ... on Issue { number title url labels(first:5){nodes{name}} } }
                      }
                    }
                  }
                }
              }
            }
            """
            # gh.api("graphql") via helper style
            gfields = {"query": gquery, "owner": owner, "repo": repo_name, "number": active_next["number"]}
            gdata = gh.api("graphql", method="POST", fields=gfields)
            nodes = []
            issue_data = (gdata.get("data") or {}).get("repository", {}).get("issue", {})
            for n in (issue_data.get("closingIssuesReferences", {}) or {}).get("nodes", []) or []:
                nodes.append(n)
            for n in (issue_data.get("timelineItems", {}) or {}).get("nodes", []) or []:
                subj = (n or {}).get("subject") or {}
                if subj.get("__typename") == "Issue":
                    nodes.append(subj)
            seen = set()
            for n in nodes:
                num = n.get("number")
                if num and num not in seen:
                    seen.add(num)
                    labels = [l["name"] for l in ((n.get("labels") or {}).get("nodes") or [])]
                    if "Epic" in labels:
                        linked_epics.append(
                            {"number": num, "title": n.get("title"), "html_url": n.get("url"), "labels": labels}
                        )
        except Exception:
            pass  # degrade gracefully

    # Basic track summary + on-hold detection (search open Epics/Features with track labels).
    try:
        track_search = gh.api(
            f"search/issues?q={quote_plus(f'repo:{target} is:issue is:open (label:Major OR label:Minor OR label:Patch) (label:Epic OR label:Feature)')}"
        )
        for item in (track_search.get("items") or []):
            labels = [l["name"] for l in item.get("labels", [])]
            for t in ["Major", "Minor", "Patch"]:
                if t in labels:
                    release_track_summary[t] += 1
            is_epic = "Epic" in labels
            if not is_epic:
                continue
            # On-hold heuristic:
            # - with active Next Release: Epic has track label but is not linked to Next
            # - without active Next Release: all open track-labeled Epics are on hold
            if active_next_release:
                linked_nums = {e["number"] for e in linked_epics}
                if item["number"] not in linked_nums:
                    on_hold_epics.append(
                        {"number": item["number"], "title": item["title"], "html_url": item["html_url"], "labels": labels}
                    )
            else:
                on_hold_epics.append(
                    {"number": item["number"], "title": item["title"], "html_url": item["html_url"], "labels": labels}
                )
    except Exception:
        pass

    # Discover versions from local releases dir if available
    pending_fragments: list[FragmentSummary] = []
    current_version: str | None = None
    latest_version: str | None = None
    extension_release_checks: list[dict] = []

    effective_releases_dir = releases_dir or Path(".agentic/releases")
    if effective_releases_dir.exists():
        versions = _list_versions(effective_releases_dir)
        if versions:
            latest_version = versions[-1]
            current_version = versions[-1]
        pending_fragments = _load_pending_fragments(effective_releases_dir)

    agentic_dir = (releases_dir.parent if releases_dir else Path(".agentic"))
    extension_release_checks = _load_extension_release_checks(agentic_dir)

    return ReleaseStatusReport(
        repo=target,
        release_branch_exists=release_branch_exists,
        release_track_branches=release_track_branches,
        release_branch_mode=release_branch_mode,
        release_branch_reset_target="main",
        warnings=warnings,
        open_release_issues=open_release_issues,
        current_version=current_version,
        latest_version=latest_version,
        pending_fragment_count=len(pending_fragments),
        pending_fragments=pending_fragments,
        extension_release_checks=extension_release_checks,
        active_next_release=active_next_release,
        linked_epics=linked_epics,
        on_hold_epics=on_hold_epics,
        release_track_summary=release_track_summary,
    )


def get_release_target_epic_guidance(
    epic_number: int,
    repo: str | None = None,
    client: GhClient | None = None,
) -> ReleaseTargetEpicGuidance:
    """Return validated guidance for targeting an Epic to the active Next Release.

    GitHub exposes read APIs for connected issue events, but it does not expose a public
    write API for creating the issue-to-issue sidebar link itself. This helper therefore
    validates the target state and returns precise manual steps instead of pretending to
    create an unsupported link.
    """
    gh = client or GhClient()
    target = resolve_repo(repo)
    issue = gh.api(f"repos/{target}/issues/{epic_number}")
    labels = [label["name"] for label in issue.get("labels", [])]
    epic = {
        "number": issue["number"],
        "title": issue["title"],
        "html_url": issue["html_url"],
        "labels": labels,
    }
    if issue.get("pull_request"):
        return ReleaseTargetEpicGuidance(
            repo=target,
            epic=epic,
            active_next_release=None,
            can_target=False,
            api_write_supported=False,
            message=f"#{epic_number} is a pull request, not an Epic issue.",
            manual_steps=[],
        )
    if "Epic" not in labels:
        return ReleaseTargetEpicGuidance(
            repo=target,
            epic=epic,
            active_next_release=None,
            can_target=False,
            api_write_supported=False,
            message=f"Issue #{epic_number} is not labeled Epic, so it cannot be targeted as an Epic.",
            manual_steps=[],
        )

    status = get_release_status(repo=target, client=gh)
    next_release = status.active_next_release
    if not next_release:
        return ReleaseTargetEpicGuidance(
            repo=target,
            epic=epic,
            active_next_release=None,
            can_target=False,
            api_write_supported=False,
            message="No active 'Next Release' issue is open, so there is nothing to target yet.",
            manual_steps=[
                "1. Open or identify the standing Release issue whose title includes 'Next Release'.",
                "2. Re-run `gh plate release target-epic <epic-number>` after that issue exists.",
            ],
        )

    return ReleaseTargetEpicGuidance(
        repo=target,
        epic=epic,
        active_next_release=next_release,
        can_target=True,
        api_write_supported=False,
        message=(
            "GitHub's public API does not support creating the issue-to-issue sidebar link directly, "
            "so the final targeting action must still be completed in the GitHub UI."
        ),
        manual_steps=[
            f"1. Open the Epic: {epic['html_url']}",
            f"2. Open the active Next Release issue: {next_release['html_url']}",
            "3. In the GitHub UI, create the issue-to-issue link between them.",
            "4. Re-run `gh plate release status` to verify the Epic moves into Linked Epics instead of On-hold Epics.",
        ],
    )


def get_release_notes_diff(
    from_version: str | None = None,
    to_version: str | None = None,
    releases_dir: Path | None = None,
) -> ReleaseNotesDiffReport:
    """Return a structured diff of release notes between two versions."""
    effective_dir = releases_dir or Path(".agentic/releases")
    if not effective_dir.exists():
        return ReleaseNotesDiffReport(
            from_version=from_version,
            to_version=to_version,
            releases_found=[],
            entries=[],
            migration_steps=[],
        )

    def _ver_key(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0,)

    all_versions = _list_versions(effective_dir)
    from_key = _ver_key(from_version) if from_version else None
    to_key = _ver_key(to_version) if to_version else None

    selected = [
        v for v in all_versions
        if (from_key is None or _ver_key(v) > from_key)
        and (to_key is None or _ver_key(v) <= to_key)
    ]

    all_entries: list[dict] = []
    all_migration_steps: list[str] = []

    for version in selected:
        data = _load_release(effective_dir, version)
        if not data:
            continue
        for entry in data.get("entries", []):
            all_entries.append({"version": version, **entry})
            mg = entry.get("migration_guidance")
            if mg:
                steps = mg if isinstance(mg, list) else [mg]
                all_migration_steps.extend(steps)

    return ReleaseNotesDiffReport(
        from_version=from_version,
        to_version=to_version,
        releases_found=selected,
        entries=all_entries,
        migration_steps=all_migration_steps,
    )


def cleanup_dead_branches(
    repo: str | None = None,
    base_branch: str | None = None,
    apply: bool = False,
    limit: int | None = None,
    client: GhClient | None = None,
) -> DeadBranchCleanupReport:
    """Find and optionally delete dead remote branches."""
    gh = client or GhClient()
    target = resolve_repo(repo)
    owner, _repo_name = target.split("/", 1) if "/" in target else (target, target)

    repo_info = gh.api(f"repos/{target}")
    default_branch = repo_info.get("default_branch", "main")
    effective_base = base_branch or default_branch

    reserved = {
        effective_base,
        default_branch,
        "release",
        "release-major",
        "release-minor",
        "release-patch",
    }

    def _is_reserved(name: str) -> bool:
        if name in reserved:
            return True
        return (
            name.startswith("release-")
            or name.startswith("release/")
            or name.startswith("release-v")
        )

    branches: list[dict] = []
    page = 1
    while True:
        batch = gh.api(f"repos/{target}/branches?per_page=100&page={page}") or []
        if not batch:
            break
        branches.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    candidates: list[str] = []
    deleted: list[str] = []
    failed: list[dict] = []
    skipped_open_pr: list[str] = []
    skipped_not_merged: list[str] = []
    warnings: list[str] = []

    for branch in branches:
        name = branch.get("name")
        if not name:
            continue
        if branch.get("protected"):
            continue
        if _is_reserved(name):
            continue

        open_prs = gh.api(
            f"repos/{target}/pulls?state=open&head={owner}:{quote(name, safe='')}&per_page=1"
        ) or []
        if open_prs:
            skipped_open_pr.append(name)
            continue

        cmp = gh.api(
            f"repos/{target}/compare/{quote(effective_base, safe='')}...{quote(name, safe='')}"
        )
        ahead_by = int(cmp.get("ahead_by", 0))
        status = (cmp.get("status") or "").lower()
        merged_into_base = ahead_by == 0 and status in {"behind", "identical"}
        if not merged_into_base:
            skipped_not_merged.append(name)
            continue

        candidates.append(name)

    if limit is not None and limit > 0 and len(candidates) > limit:
        warnings.append(
            f"Candidate set truncated by --limit: showing {limit} of {len(candidates)} merged branch candidates."
        )
        candidates = candidates[:limit]

    if apply:
        for name in candidates:
            try:
                gh.api(
                    f"repos/{target}/git/refs/heads/{quote(name, safe='')}",
                    method="DELETE",
                )
                deleted.append(name)
            except GhApiError as exc:
                failed.append({"branch": name, "error": str(exc)})

    return DeadBranchCleanupReport(
        repo=target,
        base_branch=effective_base,
        apply=apply,
        scanned_branches=len(branches),
        candidates=candidates,
        deleted=deleted,
        failed=failed,
        skipped_open_pr=skipped_open_pr,
        skipped_not_merged=skipped_not_merged,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Release cut logic (ported from scripts/cut_release.py for #261 first-class cut)
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(v: str | None) -> tuple[int, int, int] | None:
    if not v:
        return None
    m = _SEMVER_RE.match(v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def fmt_version(t: tuple[int, int, int]) -> str:
    return f"{t[0]}.{t[1]}.{t[2]}"


def bump_version(current: tuple[int, int, int], bump: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if bump == "major":
        return (major + 1, 0, 0)
    if bump == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def _git_versions(repo_root: Path) -> list[tuple[int, int, int]]:
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "tag", "--list", "v*"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        vers = []
        for line in out.splitlines():
            t = parse_version(line.strip())
            if t:
                vers.append(t)
        return vers
    except Exception:
        return []


def detect_latest_version(releases_dir: Path) -> tuple[int, int, int] | None:
    candidates: list[tuple[int, int, int]] = []
    # Legacy flat
    for f in releases_dir.glob("v*.json"):
        t = parse_version(f.stem)
        if t:
            candidates.append(t)
    # Versioned dirs
    for d in releases_dir.iterdir():
        if d.is_dir() and _SEMVER_RE.match(d.name):
            t = parse_version(d.name)
            if t and (d / "release.json").exists():
                candidates.append(t)
    # Git tags
    repo_root = releases_dir
    for _ in range(6):
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    candidates.extend(_git_versions(repo_root))
    return max(candidates) if candidates else None


def _load_json_fragments_from_dir(source_dir: Path, source_label: str) -> list[dict]:
    fragments = []
    for f in sorted(source_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  WARNING: could not parse {f}: {exc}")
            continue
        data["_source_file"] = f.name
        data["_source_dir"] = str(source_dir)
        data["_source_label"] = source_label
        fragments.append(data)
    return fragments


def collect_fragments(releases_dir: Path) -> list[dict]:
    all_fragments: list[dict] = []
    unreleased = releases_dir / "unreleased"
    if unreleased.is_dir():
        all_fragments.extend(_load_json_fragments_from_dir(unreleased, "unreleased"))
    for d in sorted(releases_dir.iterdir()):
        if d.is_dir() and re.match(r"^epic-", d.name):
            all_fragments.extend(_load_json_fragments_from_dir(d, d.name))
    return all_fragments


def infer_bump_type(fragments: list[dict]) -> str:
    if any(f.get("breaking") for f in fragments):
        return "major"
    if any(f.get("change_type") == "feature" for f in fragments):
        return "minor"
    return "patch"


def fragment_to_entry(fragment: dict) -> dict:
    entry: dict = {
        "change_type": fragment.get("change_type", "docs"),
        "surface": fragment.get("surface", ""),
        "migration_impact": fragment.get("migration_impact", ""),
        "agent_notes": fragment.get("agent_notes", ""),
    }
    if "migration_guidance" in fragment:
        entry["migration_guidance"] = fragment["migration_guidance"]
    if fragment.get("breaking"):
        entry["breaking"] = True
    if fragment.get("links"):
        entry["links"] = fragment["links"]
    if fragment.get("requires"):
        entry["requires"] = fragment["requires"]
    return entry


def build_release(version: str, fragments: list[dict]) -> dict:
    entries = [fragment_to_entry(f) for f in fragments]
    slugs = [f.get("slug", f.get("_source_file", "")) for f in fragments]
    summary_slugs = ", ".join(slugs[:5]) + ("..." if len(slugs) > 5 else "")
    return {
        "version": version,
        "summary": f"PLATE {version} -- {len(entries)} change(s): {summary_slugs}.",
        "cut_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fragment_count": len(fragments),
        "fragment_slugs": [f.get("slug", f["_source_file"]) for f in fragments],
        "entries": entries,
    }


def collect_closes_block(fragments: list[dict]) -> str:
    """Collect unique Closes links from fragment 'links' arrays for Release PR body.
    Enables one merge-to-main to auto-close the addressed issues (fixes GitHub Closes limitation
    for work landed on release branches). Part of #569 Closes auto-collection.
    """
    seen = []
    for f in fragments:
        for link in (f.get("links") or []):
            if link and isinstance(link, str) and link.startswith("#") and link not in seen:
                seen.append(link)
    if not seen:
        return ""
    return "Closes " + ", ".join(seen)


def cut_release(
    version: str | None,
    releases_dir: Path,
    version_type: str | None = None,
    dry_run: bool = False,
) -> int:
    fragments = collect_fragments(releases_dir)
    if not fragments:
        print("No pending fragments found. Nothing to cut.")
        return 1

    print(f"Found {len(fragments)} pending fragment(s):")
    for f in fragments:
        label = f.get("_source_label", "?")
        slug = f.get("slug", f["_source_file"])
        summary = f.get("summary", "(no summary)")
        print(f"  [{label}] {slug}: {summary}")

    if version:
        version = version.lstrip("v")
        if version_type:
            print("NOTE: --version-type is ignored when an explicit version is supplied.")
    else:
        latest = detect_latest_version(releases_dir)
        if latest is None:
            print(
                "ERROR: Could not detect the current PLATE baseline.\n"
                "No versioned release files or git tags found.\n"
                "Supply an explicit version: cut_release.py vX.Y.Z"
            )
            return 1
        bump_type = version_type or infer_bump_type(fragments)
        next_ver = bump_version(latest, bump_type)
        version = fmt_version(next_ver)
        override_note = "  (overridden via --version-type)" if version_type else ""
        print(
            f"\nCurrent baseline : v{fmt_version(latest)}"
            f"\nInferred bump    : {bump_type}{override_note}"
            f"\nProposed version : v{version}"
        )

    versioned_dir = releases_dir / f"v{version}"
    if versioned_dir.exists():
        print(f"ERROR: {versioned_dir} already exists. Choose a different version or remove it first.")
        return 1

    current = detect_latest_version(releases_dir)
    proposed = parse_version(version)
    if current and proposed and proposed <= current:
        print(
            f"WARNING: v{version} is not greater than the current baseline "
            f"v{fmt_version(current)}. Proceed with caution."
        )

    repo_root = find_repo_root(releases_dir)
    version_files = sync_repository_version(version, repo_root, dry_run=True)
    fragments_dir = versioned_dir / "fragments"
    release_data = build_release(version, fragments)

    # #569: auto-collect Closes block from fragment links so Release PR merge to main
    # auto-closes the addressed Bugs/Features (one merge closes everything).
    closes_block = collect_closes_block(fragments)
    if closes_block:
        release_data["closes_block"] = closes_block

    if dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  {versioned_dir / 'release.json'}")
        for frag in fragments:
            src_dir = Path(frag["_source_dir"])
            print(f"  {fragments_dir / frag['_source_file']}  (moved from {src_dir.name}/)")
        print("\n[DRY RUN] Would sync version files:")
        for path in version_files:
            print(f"  {path.relative_to(repo_root)} -> {version}")
        print("\n[DRY RUN] release.json preview:")
        print(json.dumps(release_data, indent=2))
        if closes_block:
            print(f"\n[DRY RUN] Recommended Closes block for Release PR body:\n{closes_block}")
        return 0

    versioned_dir.mkdir(parents=True, exist_ok=True)
    fragments_dir.mkdir(parents=True, exist_ok=True)

    release_file = versioned_dir / "release.json"
    release_file.write_text(json.dumps(release_data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {release_file}")
    sync_repository_version(version, repo_root)
    print("Synced version files:")
    for path in version_files:
        print(f"  {path.relative_to(repo_root)} -> {version}")

    seen_epic_dirs: set[Path] = set()
    for frag in fragments:
        src = Path(frag["_source_dir"]) / frag["_source_file"]
        dst = fragments_dir / frag["_source_file"]
        shutil.move(str(src), str(dst))
        label = frag.get("_source_label", "?")
        print(f"  Moved [{label}] {frag['_source_file']} -> fragments/")
        if frag.get("_source_label", "").startswith("epic-"):
            seen_epic_dirs.add(Path(frag["_source_dir"]))

    for epic_dir in seen_epic_dirs:
        remaining = [f for f in epic_dir.iterdir() if not f.name.startswith(".")]
        if not remaining:
            epic_dir.rmdir()
            print(f"  Removed empty epic dir: {epic_dir.name}/")

    print(f"\nRelease v{version} cut successfully.")
    print("Next steps:")
    print(f"  1. Review {versioned_dir / 'release.json'} and adjust the summary if needed.")
    print(f"  2. Commit the new {versioned_dir}/ directory.")
    print("  3. Open a PR: release -> main (use the 'Closes' block below in the body if present).")
    if closes_block:
        print(f"\nRecommended Closes block for Release PR body (enables one merge to main closing addressed issues):\n{closes_block}\n")
    print(f"  4. Ensure the Release PR passes version-sync and remote tag-conflict validation for v{version}.")
    print(f"  5. After merge, the release workflow will create/push tag v{version} from the merged Release PR commit.")
    print(f"  6. Run `gh plate release finalize {version}` (or equivalent) for hard-reset + gh release create + next-Release spawn.")
    print(
        f"  7. (Legacy) Hard-reset release branch: "
        f"git checkout release && git fetch origin && git reset --hard origin/main && git push --force-with-lease"
    )
    return 0
