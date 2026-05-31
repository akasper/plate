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
    """Read release_checks from .agentic/extensions.yml if present."""
    extensions_file = agentic_dir / "extensions.yml"
    if not extensions_file.exists():
        return []
    try:
        import re
        text = extensions_file.read_text(encoding="utf-8")
        # Simple YAML parsing for release_checks arrays — avoids PyYAML dependency
        checks = []
        current_ext: str | None = None
        in_release_checks = False
        for line in text.splitlines():
            # Extension id detection
            id_match = re.match(r'^\s+-\s+id:\s+"?([^"]+)"?', line)
            if id_match:
                current_ext = id_match.group(1)
                in_release_checks = False
            # release_checks array start
            if re.match(r'^\s+release_checks:', line):
                in_release_checks = True
            # Item in release_checks
            elif in_release_checks and re.match(r'^\s+-', line):
                check_id_match = re.search(r'id:\s+"?([^"]+)"?', line)
                desc_match = re.search(r'description:\s+"?([^"]+)"?', line)
                req_match = re.search(r'required:\s+(true|false)', line)
                human_match = re.search(r'human_approval:\s+(true|false)', line)
                checks.append({
                    "extension_id": current_ext,
                    "id": check_id_match.group(1) if check_id_match else "",
                    "description": desc_match.group(1) if desc_match else line.strip(),
                    "required": req_match.group(1) == "true" if req_match else True,
                    "human_approval": human_match.group(1) == "true" if human_match else False,
                    "satisfied": None,  # unknown without runtime verification
                })
            elif in_release_checks and not line.strip().startswith("-") and line.strip() and not line.strip().startswith("#"):
                # Exited the array
                in_release_checks = False
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
