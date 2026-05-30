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

    yield from sorted(path.glob("v*.json"))


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
