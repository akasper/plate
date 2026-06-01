#!/usr/bin/env python3
"""Render PLATE release notes into ordered migration guidance."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable


def version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _ver_key(p: Path) -> tuple[int, ...]:
    if p.is_file() and p.name == "release.json":
        stem = p.parent.name.lstrip("v")
    elif p.is_file():
        stem = p.stem.lstrip("v")
    else:
        stem = p.name.lstrip("v")
    try:
        return tuple(int(x) for x in stem.split("."))
    except ValueError:
        return (0,)


def load_release_files(path: Path) -> list[dict]:
    if path.is_file():
        files = [path]
    else:
        # Legacy flat files
        root_files = sorted(path.glob("v*.json"), key=_ver_key)
        # New versioned dirs
        versioned_dirs = sorted(
            [d for d in path.iterdir() if d.is_dir() and d.name.startswith("v")],
            key=_ver_key,
        )
        dir_releases = []
        for vdir in versioned_dirs:
            release_file = vdir / "release.json"
            if release_file.exists():
                dir_releases.append(release_file)
        dir_versions = {f.parent.name for f in dir_releases}
        flat_only = [f for f in root_files if f.stem not in dir_versions]
        files = sorted(flat_only + dir_releases, key=_ver_key)

    releases = []
    for file in files:
        with file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["_source"] = file.name
        releases.append(data)
    return releases


def select_releases(releases: list[dict], from_version: str | None, to_version: str | None) -> list[dict]:
    start = version_key(from_version) if from_version else None
    end = version_key(to_version) if to_version else None

    selected = []
    for release in releases:
        key = version_key(release["version"])
        if start and key <= start:
            continue
        if end and key > end:
            continue
        selected.append(release)
    return selected


def topo_sort(releases: list[dict]) -> list[dict]:
    by_version = {release["version"]: release for release in releases}
    incoming = defaultdict(set)
    outgoing = defaultdict(set)

    for release in releases:
        for requirement in release.get("entries", []):
            for dependency in requirement.get("requires", []):
                if dependency in by_version:
                    incoming[release["version"]].add(dependency)
                    outgoing[dependency].add(release["version"])

    queue = deque(sorted([version for version in by_version if not incoming[version]], key=version_key))
    ordered = []
    seen = set()

    while queue:
        version = queue.popleft()
        if version in seen:
            continue
        seen.add(version)
        ordered.append(by_version[version])
        for child in sorted(outgoing[version], key=version_key):
            incoming[child].discard(version)
            if not incoming[child]:
                queue.append(child)

    if len(ordered) != len(releases):
        raise SystemExit("Release-note dependency cycle detected.")

    return ordered


def render_guidance(releases: list[dict], from_version: str | None, to_version: str | None) -> str:
    lines = ["# PLATE migration guidance", ""]
    if from_version or to_version:
        lines.append(f"**Upgrade range:** {from_version or 'earliest'} -> {to_version or 'latest'}")
        lines.append("")

    for release in releases:
        lines.append(f"## v{release['version']}")
        lines.append("")
        lines.append(release["summary"])
        lines.append("")
        for index, entry in enumerate(release["entries"], start=1):
            lines.append(f"{index}. **{entry['change_type']}** — {entry['surface']}")
            lines.append(f"   - What changed: {entry['migration_impact']}")
            lines.append(f"   - Why: {entry['agent_notes']}")
            migration_guidance = entry.get("migration_guidance")
            if migration_guidance:
                if isinstance(migration_guidance, list):
                    lines.append("   - **Migration steps:**")
                    for step in migration_guidance:
                        lines.append(f"     - {step}")
                else:
                    lines.append(f"   - **Migration steps:** {migration_guidance}")
            if entry.get("requires"):
                lines.append(f"   - Requires: {', '.join(entry['requires'])}")
            if entry.get("links"):
                lines.append(f"   - Links: {', '.join(entry['links'])}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Release JSON file or directory")
    parser.add_argument("--from-version", dest="from_version", help="Skip releases at or below this version")
    parser.add_argument("--to-version", dest="to_version", help="Stop at this version")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")

    releases = load_release_files(path)
    releases = select_releases(releases, args.from_version, args.to_version)
    releases = topo_sort(releases)
    print(render_guidance(releases, args.from_version, args.to_version), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
