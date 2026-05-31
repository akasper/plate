#!/usr/bin/env python3
"""Render PLATE release-note JSON into Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def render_release(data: dict) -> str:
    lines = [
        f"# PLATE release notes {data['version']}",
        "",
        data["summary"],
        "",
    ]

    for entry in data["entries"]:
        lines.extend(
            [
                f"## {entry['change_type']} — {entry['surface']}",
                "",
                f"- **Migration impact:** {entry['migration_impact']}",
                f"- **Agent notes:** {entry['agent_notes']}",
            ]
        )
        migration_guidance = entry.get("migration_guidance")
        if migration_guidance:
            if isinstance(migration_guidance, list):
                lines.append("- **Migration steps:**")
                for step in migration_guidance:
                    lines.append(f"  - {step}")
            else:
                lines.append(f"- **Migration steps:** {migration_guidance}")
        if entry.get("breaking"):
            lines.append("- **Breaking:** yes")
        if entry.get("links"):
            lines.append(f"- **Links:** {', '.join(entry['links'])}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def iter_release_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return

    # Legacy flat files at root
    root_files = sorted(path.glob("v*.json"))

    # New versioned dirs: vX.Y.Z/ containing release.json
    def _ver_key(p: Path) -> tuple[int, ...]:
        stem = p.stem.lstrip("v") if p.is_file() else p.name.lstrip("v")
        try:
            return tuple(int(x) for x in stem.split("."))
        except ValueError:
            return (0,)

    versioned_dirs = sorted(
        [d for d in path.iterdir() if d.is_dir() and d.name.startswith("v")],
        key=_ver_key,
    )
    dir_releases = []
    for vdir in versioned_dirs:
        release_file = vdir / "release.json"
        if release_file.exists():
            dir_releases.append(release_file)

    # Combine: prefer dir releases, fall back to flat files for versions not present as dirs
    dir_versions = {f.parent.name for f in dir_releases}
    flat_only = [f for f in root_files if f.stem not in dir_versions]

    all_files = sorted(flat_only + dir_releases, key=_ver_key)
    yield from all_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Release JSON file or directory")
    parser.add_argument("--all", action="store_true", help="Render all release files in a directory")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")

    files = iter_release_files(path) if args.all or path.is_dir() else [path]
    for file in files:
        with file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(render_release(data), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
