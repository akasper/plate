#!/usr/bin/env python3
"""Report CI jobs to run for changed paths (#1270).

Usage:
  python scripts/plate/select_ci_jobs.py --paths src/a.py,docs/b.md
  python scripts/plate/select_ci_jobs.py --base origin/main --repo-root .
  PLATE_CI_FULL_SUITE=1 python scripts/plate/select_ci_jobs.py --base origin/main

Writes JSON to stdout; with --github-output writes workflow outputs.
Exits non-zero when selection is unsafe (fail policy or hidden changes).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root_from_script() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").is_dir():
            return parent
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select CI jobs for changed paths")
    parser.add_argument("--repo-root", default=None, help="Repository root (default: auto)")
    parser.add_argument("--config", default=None, help="Path to ci-path-jobs.yml")
    parser.add_argument("--paths", default="", help="Comma-separated changed paths")
    parser.add_argument("--base", default=None, help="Git base ref for diff (e.g. origin/main)")
    parser.add_argument("--head", default="HEAD", help="Git head ref (default HEAD)")
    parser.add_argument(
        "--full-suite",
        action="store_true",
        help="Run full job list (same as PLATE_CI_FULL_SUITE=1)",
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="Path to GITHUB_OUTPUT file (also reads env GITHUB_OUTPUT)",
    )
    parser.add_argument(
        "--allow-unsafe",
        action="store_true",
        help="Do not exit 1 on unsafe selection",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else _repo_root_from_script()
    src = repo_root / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    try:
        from plate_core.ci_path_jobs import (  # noqa: WPS433
            CiPathJobsError,
            assert_selection_safe_for_merge,
            format_github_outputs,
            selection_for_repo,
        )
    except ImportError:
        print(
            json.dumps(
                {
                    "error": "plate_core not importable; pip install plate-core or set PYTHONPATH to src",
                }
            ),
            file=sys.stderr,
        )
        return 2

    paths: list[str] = []
    if args.paths.strip():
        paths = [p.strip() for p in args.paths.split(",") if p.strip()]

    try:
        selection = selection_for_repo(
            repo_root,
            changed_paths=paths if paths else None,
            base_ref=args.base,
            head_ref=args.head,
            config_path=args.config,
            full_suite=args.full_suite,
        )
    except CiPathJobsError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    payload = selection.to_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))

    gh_out = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        out_path = Path(gh_out)
        outputs = format_github_outputs(selection)
        with out_path.open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")

    if not args.allow_unsafe:
        try:
            assert_selection_safe_for_merge(selection)
        except CiPathJobsError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
