"""Release status and notes diff surfaces shared across CLI and MCP."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote_plus

from .github_client import GhApiError, GhClient
from .health import resolve_repo


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
    open_release_issues: list[dict]
    current_version: str | None
    latest_version: str | None
    pending_fragment_count: int
    pending_fragments: list[FragmentSummary]
    extension_release_checks: list[dict]

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "release_branch_exists": self.release_branch_exists,
            "open_release_issues": self.open_release_issues,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "pending_fragment_count": self.pending_fragment_count,
            "pending_fragments": [f.to_dict() for f in self.pending_fragments],
            "extension_release_checks": self.extension_release_checks,
        }


@dataclass
class ReleaseNotesDiffReport:
    from_version: str | None
    to_version: str | None
    releases_found: list[str]
    entries: list[dict]
    migration_steps: list[str]

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

    # Check if release branch exists
    release_branch_exists = False
    try:
        gh.api(f"repos/{target}/branches/release")
        release_branch_exists = True
    except GhApiError:
        pass

    # Find open Release issues
    search = gh.api(
        f"search/issues?q={quote_plus(f'repo:{target} is:issue is:open label:Release')}"
    )
    open_release_issues = [
        {"number": i["number"], "title": i["title"], "html_url": i["html_url"]}
        for i in (search.get("items") or [])
    ]

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
        open_release_issues=open_release_issues,
        current_version=current_version,
        latest_version=latest_version,
        pending_fragment_count=len(pending_fragments),
        pending_fragments=pending_fragments,
        extension_release_checks=extension_release_checks,
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
