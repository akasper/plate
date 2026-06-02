#!/usr/bin/env python3
"""Aggregate unreleased fragments into a versioned release directory.

Usage:
    # Auto-detect next version from fragment types + current baseline:
    python scripts/cut_release.py [--releases-dir .agentic/releases] [--dry-run]

    # Explicit version (overrides auto-detection):
    python scripts/cut_release.py vX.Y.Z [--releases-dir .agentic/releases] [--dry-run]

    # Override bump type while keeping auto-detected base:
    python scripts/cut_release.py --version-type minor [--dry-run]

Fragment sources (aggregated in order):
  1. <releases-dir>/unreleased/*.json          (fragments not tied to a specific epic)
  2. <releases-dir>/epic-<NNN>-<slug>/*.json   (per-epic fragment directories)

Version auto-detection:
  The current baseline is the highest semver found in:
    * flat files    <releases-dir>/vX.Y.Z.json
    * versioned dirs  <releases-dir>/vX.Y.Z/release.json
    * git tags      vX.Y.Z  (if git is available)
  The bump type is inferred from the pending fragments:
    * any  breaking: true          ->  major
    * any  change_type: "feature"  ->  minor  (when no breaking changes)
    * otherwise                    ->  patch

Output layout:
    <releases-dir>/vX.Y.Z/
        release.json     consolidated record
        fragments/       contributing fragments (moved from their source dirs)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(v: str) -> tuple[int, int, int] | None:
    m = _SEMVER_RE.match(v.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def fmt_version(t: tuple[int, int, int]) -> str:
    return f"{t[0]}.{t[1]}.{t[2]}"


def bump_version(base: tuple[int, int, int], bump_type: str) -> tuple[int, int, int]:
    major, minor, patch = base
    if bump_type == "major":
        return (major + 1, 0, 0)
    if bump_type == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


# ---------------------------------------------------------------------------
# Baseline detection
# ---------------------------------------------------------------------------


def _git_versions(repo_root: Path) -> list[tuple[int, int, int]]:
    """Return semver tuples from git tags (best-effort; silent on failure)."""
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(repo_root),
        )
        versions = []
        for line in result.stdout.splitlines():
            t = parse_version(line.strip())
            if t:
                versions.append(t)
        return versions
    except Exception:
        return []


def detect_latest_version(releases_dir: Path) -> tuple[int, int, int] | None:
    """Find the highest released semver from flat files, versioned dirs, and git tags."""
    candidates: list[tuple[int, int, int]] = []

    # Legacy flat files: vX.Y.Z.json
    for f in releases_dir.glob("v*.json"):
        t = parse_version(f.stem)
        if t:
            candidates.append(t)

    # Versioned directories: vX.Y.Z/release.json
    for d in releases_dir.iterdir():
        if d.is_dir() and _SEMVER_RE.match(d.name):
            t = parse_version(d.name)
            if t and (d / "release.json").exists():
                candidates.append(t)

    # Git tags (walk up from releases_dir to find repo root)
    repo_root = releases_dir
    for _ in range(6):
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    candidates.extend(_git_versions(repo_root))

    return max(candidates) if candidates else None


# ---------------------------------------------------------------------------
# Fragment collection
# ---------------------------------------------------------------------------


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
    """Load fragments from unreleased/ and all epic-NNN-slug/ directories."""
    all_fragments: list[dict] = []

    # 1. unreleased/
    unreleased = releases_dir / "unreleased"
    if unreleased.is_dir():
        all_fragments.extend(_load_json_fragments_from_dir(unreleased, "unreleased"))

    # 2. epic-* directories (sorted for deterministic ordering)
    for d in sorted(releases_dir.iterdir()):
        if d.is_dir() and re.match(r"^epic-", d.name):
            all_fragments.extend(_load_json_fragments_from_dir(d, d.name))

    return all_fragments


# ---------------------------------------------------------------------------
# Bump type inference
# ---------------------------------------------------------------------------


def infer_bump_type(fragments: list[dict]) -> str:
    """Return 'major', 'minor', or 'patch' based on fragment metadata."""
    if any(f.get("breaking") for f in fragments):
        return "major"
    if any(f.get("change_type") == "feature" for f in fragments):
        return "minor"
    return "patch"


# ---------------------------------------------------------------------------
# Release record construction
# ---------------------------------------------------------------------------


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
    summary_slugs = ", ".join(slugs[:5]) + ("..." if len(slugs) > 5 else "")
    return {
        "version": version,
        "summary": f"PLATE {version} -- {len(entries)} change(s): {summary_slugs}.",
        "cut_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fragment_count": len(fragments),
        "fragment_slugs": [f.get("slug", f["_source_file"]) for f in fragments],
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Main cut logic
# ---------------------------------------------------------------------------


def cut_release(
    version: str | None,
    releases_dir: Path,
    version_type: str | None = None,
    dry_run: bool = False,
) -> int:
    # --- Collect fragments ---------------------------------------------------
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

    # --- Resolve target version ---------------------------------------------
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

    # Guard against writing over an existing release
    versioned_dir = releases_dir / f"v{version}"
    if versioned_dir.exists():
        print(f"ERROR: {versioned_dir} already exists. Choose a different version or remove it first.")
        return 1

    # Warn if proposed version is not strictly greater than current baseline
    current = detect_latest_version(releases_dir)
    proposed = parse_version(version)
    if current and proposed and proposed <= current:
        print(
            f"WARNING: v{version} is not greater than the current baseline "
            f"v{fmt_version(current)}. Proceed with caution."
        )

    fragments_dir = versioned_dir / "fragments"
    release_data = build_release(version, fragments)

    # --- Dry run preview ----------------------------------------------------
    if dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  {versioned_dir / 'release.json'}")
        for frag in fragments:
            src_dir = Path(frag["_source_dir"])
            print(f"  {fragments_dir / frag['_source_file']}  (moved from {src_dir.name}/)")
        print("\n[DRY RUN] release.json preview:")
        print(json.dumps(release_data, indent=2))
        return 0

    # --- Write output -------------------------------------------------------
    versioned_dir.mkdir(parents=True, exist_ok=True)
    fragments_dir.mkdir(parents=True, exist_ok=True)

    release_file = versioned_dir / "release.json"
    release_file.write_text(json.dumps(release_data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {release_file}")

    # Move fragments and clean up emptied epic directories
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
    print( "  3. Open a PR: release -> main.")
    print(f"  4. After merge: git tag v{version} && git push --tags")
    print(
        f"  5. Hard-reset release branch: "
        f"git checkout release && git reset --hard v{version} && git push --force-with-lease"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "version",
        nargs="?",
        help=(
            "Version to cut (e.g. v0.2.0 or 0.2.0). "
            "Omit to auto-detect from current baseline and fragment types."
        ),
    )
    parser.add_argument(
        "--releases-dir",
        default=".agentic/releases",
        help="Path to the releases directory (default: .agentic/releases)",
    )
    parser.add_argument(
        "--version-type",
        choices=["major", "minor", "patch"],
        help=(
            "Override the inferred bump type when auto-detecting the version. "
            "Ignored when an explicit version is supplied."
        ),
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

    return cut_release(
        version=args.version,
        releases_dir=releases_dir,
        version_type=args.version_type,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
