#!/usr/bin/env python3
"""Aggregate unreleased fragments into a versioned release directory.

Usage:
    gh plate release cut vX.Y.Z [--releases-dir .agentic/releases] [--dry-run]

This script:
1. Reads all .json fragments from <releases-dir>/unreleased/
2. Produces <releases-dir>/vX.Y.Z/release.json (consolidated record)
3. Copies the contributing fragments into <releases-dir>/vX.Y.Z/fragments/
4. Moves (or --dry-run: shows) the unreleased fragments to the versioned dir.

The resulting directory layout supports per-version diffs by agents:
  gh plate release notes --from 0.1.3 --to 0.2.0
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone


def load_fragments(unreleased_dir: Path) -> list[dict]:
    fragments = []
    for file in sorted(unreleased_dir.glob("*.json")):
        with file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["_source_file"] = file.name
        fragments.append(data)
    return fragments


def fragment_to_entry(fragment: dict) -> dict:
    """Convert a fragment dict into the release entry format."""
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
    return {
        "version": version,
        "summary": f"PLATE {version} — {len(entries)} change(s): {', '.join(slugs[:5])}{'...' if len(slugs) > 5 else ''}.",
        "cut_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fragment_count": len(fragments),
        "fragment_slugs": [f.get("slug", f["_source_file"]) for f in fragments],
        "entries": entries,
    }


def cut_release(version: str, releases_dir: Path, dry_run: bool = False) -> int:
    version = version.lstrip("v")
    unreleased_dir = releases_dir / "unreleased"
    versioned_dir = releases_dir / f"v{version}"

    if not unreleased_dir.exists():
        print(f"No unreleased/ directory found at {unreleased_dir}. Nothing to cut.")
        return 1

    fragments = load_fragments(unreleased_dir)
    if not fragments:
        print(f"No fragments found in {unreleased_dir}. Nothing to cut.")
        return 1

    print(f"Found {len(fragments)} fragment(s) in {unreleased_dir}:")
    for f in fragments:
        print(f"  - {f.get('slug', f['_source_file'])}: {f.get('summary', '(no summary)')}")

    release_data = build_release(version, fragments)
    fragments_dir = versioned_dir / "fragments"

    if dry_run:
        print(f"\n[DRY RUN] Would create:")
        print(f"  {versioned_dir / 'release.json'}")
        for frag in fragments:
            print(f"  {fragments_dir / frag['_source_file']} (moved from unreleased/)")
        print(f"\n[DRY RUN] release.json preview:")
        print(json.dumps(release_data, indent=2))
        return 0

    versioned_dir.mkdir(parents=True, exist_ok=True)
    fragments_dir.mkdir(parents=True, exist_ok=True)

    # Write consolidated release
    release_file = versioned_dir / "release.json"
    with release_file.open("w", encoding="utf-8") as fh:
        json.dump(release_data, fh, indent=2)
        fh.write("\n")
    print(f"\nWrote {release_file}")

    # Move fragments
    for frag in fragments:
        src = unreleased_dir / frag["_source_file"]
        dst = fragments_dir / frag["_source_file"]
        shutil.move(str(src), str(dst))
        print(f"Moved {src.name} → {dst}")

    print(f"\nRelease v{version} cut successfully.")
    print(f"Next steps:")
    print(f"  1. Review {versioned_dir / 'release.json'} and adjust the summary.")
    print(f"  2. Commit the new {versioned_dir}/ directory.")
    print(f"  3. Open a PR: release → main.")
    print(f"  4. After merge: git tag v{version} && git push --tags")
    print(f"  5. Hard-reset release branch: git checkout release && git reset --hard v{version} && git push --force-with-lease")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Target version to cut (e.g. v0.2.0 or 0.2.0)")
    parser.add_argument(
        "--releases-dir",
        default=".agentic/releases",
        help="Path to the releases directory (default: .agentic/releases)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without writing any files",
    )
    args = parser.parse_args()

    releases_dir = Path(args.releases_dir)
    if not releases_dir.exists():
        raise SystemExit(f"Releases directory not found: {releases_dir}")

    return cut_release(args.version, releases_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
