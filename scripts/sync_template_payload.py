"""Sync reusable scaffolding files from plate_template into plate template payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess

from plate_core.template_payload import (
    classify_template_file,
    load_template_payload_manifest,
    normalize_rel_path,
    payload_root,
    should_include_template_file,
)


def _default_template_repo(repo_root: Path) -> Path:
    return (repo_root.parent / "plate_template").resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _list_tracked_files(template_repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(template_repo), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _remove_stale_files(payload_dir: Path, expected: set[str]) -> list[str]:
    removed: list[str] = []
    if not payload_dir.exists():
        return removed
    for path in sorted(payload_dir.rglob("*"), reverse=True):
        if path.is_dir():
            continue
        rel = path.relative_to(payload_dir).as_posix()
        if rel not in expected:
            path.unlink()
            removed.append(rel)
    for path in sorted(payload_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed


def main() -> int:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description="Sync template payload from plate_template")
    parser.add_argument(
        "--template-repo",
        default=str(_default_template_repo(repo_root)),
        help="Path to plate_template repository clone",
    )
    parser.add_argument(
        "--payload-root",
        default=str(payload_root()),
        help="Destination payload directory (defaults to src/plate_core/template_payload)",
    )
    parser.add_argument(
        "--inventory-file",
        default=str(repo_root / "src" / "plate_core" / "data" / "template_payload_inventory.json"),
        help="Inventory output file path",
    )
    args = parser.parse_args()

    template_repo = Path(args.template_repo).resolve()
    payload_dir = Path(args.payload_root).resolve()
    inventory_file = Path(args.inventory_file).resolve()

    if not template_repo.exists():
        raise RuntimeError(f"Template repository not found: {template_repo}")

    manifest = load_template_payload_manifest()
    tracked = _list_tracked_files(template_repo)
    selected: list[str] = []
    for rel in tracked:
        normalized = normalize_rel_path(rel)
        if should_include_template_file(normalized, manifest):
            selected.append(normalized)
    selected.sort()

    payload_dir.mkdir(parents=True, exist_ok=True)
    removed = _remove_stale_files(payload_dir, set(selected))
    copied: list[str] = []
    for rel in selected:
        src = template_repo / PurePosixPath(rel)
        dst = payload_dir / PurePosixPath(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    inventory = {
        "schema_version": 1,
        "source_repository": "akasper/plate_template",
        "selection_manifest": "src/plate_core/data/template_payload_manifest.yml",
        "files": [
            {
                "path": rel,
                "classification": classify_template_file(rel, manifest),
            }
            for rel in copied
        ],
    }
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "success",
                "copied_count": len(copied),
                "removed_count": len(removed),
                "payload_root": str(payload_dir),
                "inventory_file": str(inventory_file),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
