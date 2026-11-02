#!/usr/bin/env python3
"""Report tiered CI jobs for changed paths and PR kind (#1332).

Usage:
  python scripts/plate/select_tiered_ci_jobs.py --paths src/a.py --pr-kind ordinary
  python scripts/plate/select_tiered_ci_jobs.py --base origin/main --pr-kind release_patch
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
    parser = argparse.ArgumentParser(description="Select tiered CI jobs for a PR")
    parser.add_argument("--repo-root", default=None, help="Repository root (default: auto)")
    parser.add_argument("--path-config", default=None, help="Path to ci-path-jobs.yml")
    parser.add_argument("--policy-config", default=None, help="Path to ci-policy.yml")
    parser.add_argument("--paths", default="", help="Comma-separated changed paths")
    parser.add_argument(
        "--added-paths",
        default="",
        help="Comma-separated newly added paths (optional)",
    )
    parser.add_argument("--base", default=None, help="Git base ref for diff")
    parser.add_argument("--head", default="HEAD", help="Git head ref")
    parser.add_argument(
        "--pr-kind",
        default="ordinary",
        choices=[
            "ordinary",
            "release_patch",
            "release_minor",
            "release_major",
            "nightly",
        ],
        help="PR classification for tier caps",
    )
    parser.add_argument(
        "--full-suite",
        action="store_true",
        help="Treat as nightly (all jobs)",
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="Path to GITHUB_OUTPUT file (also reads env GITHUB_OUTPUT)",
    )
    parser.add_argument(
        "--allow-unsafe",
        action="store_true",
        help="Do not exit 1 on unsafe path selection",
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
        )
        from plate_core.ci_tiered_policy import (  # noqa: WPS433
            CiTieredPolicyError,
            tiered_selection_for_repo,
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

    added: list[str] | None = None
    if args.added_paths.strip():
        added = [p.strip() for p in args.added_paths.split(",") if p.strip()]

    pr_kind = "nightly" if args.full_suite else args.pr_kind

    try:
        selection, meta = tiered_selection_for_repo(
            repo_root,
            changed_paths=paths if paths else None,
            added_paths=added,
            base_ref=args.base,
            head_ref=args.head,
            path_jobs_config_path=args.path_config,
            policy_config_path=args.policy_config,
            pr_kind=pr_kind,
            full_suite=args.full_suite,
        )
    except (CiPathJobsError, CiTieredPolicyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    payload = {
        "selection": selection.to_dict(),
        "tiered": meta.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    gh_out = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        out_path = Path(gh_out)
        outputs = format_github_outputs(selection)
        outputs["pr_kind"] = meta.pr_kind
        outputs["tiered_json"] = json.dumps(meta.to_dict())
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
