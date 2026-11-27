"""PR gate: changed tests must use stdlib unittest, not pytest (#1182)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from plate_core.pr_gates_test_policy import ScanFailure, scan_test_paths

FAILURE_HEADING = "stdlib unittest policy"
FAILURE_MARKER = "stdlib unittest policy"


def _default_reader(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def git_show_reader(head_sha: str, repo_root: Path) -> Callable[[str], str]:
    def read(path: str) -> str:
        ref = f"{head_sha}:{path}"
        result = subprocess.run(
            ["git", "show", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or f"git show failed for {ref}")
        return result.stdout

    return read


def format_violation_message(path: str, line_number: int, line: str) -> str:
    return f"{path}:{line_number}: {line.strip()}"


def run_gate(
    paths: list[str],
    *,
    read_text: Callable[[str], str] | None = None,
) -> int:
    reader = read_text or _default_reader
    violations, failures = scan_test_paths(paths, reader)
    if failures or violations:
        lines = [
            f"## ⚠️ {FAILURE_HEADING}",
            "",
            "PLATE tests use stdlib `unittest` (`python -m unittest discover`). "
            "Changed test files must not import or invoke pytest.",
            "",
        ]
        for item in failures:
            lines.append(f"{item.path}: unreadable: {item.message}")
        for item in violations:
            lines.append(format_violation_message(item.path, item.line_number, item.line))
        print("\n".join(lines), file=sys.stderr)
        return 1
    return 0


def _read_paths_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE unittest test-policy PR gate (#1182)")
    parser.add_argument(
        "--paths-file",
        type=Path,
        required=True,
        help="Newline-separated active (non-removed) paths from the PR",
    )
    parser.add_argument(
        "--head-sha",
        default="",
        help="When set, read test contents via git show HEAD_SHA:path from --repo-root",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Git repository root for git show reads",
    )
    args = parser.parse_args(argv)
    paths = _read_paths_file(args.paths_file)
    if args.head_sha.strip():
        return run_gate(paths, read_text=git_show_reader(args.head_sha.strip(), args.repo_root))
    return run_gate(paths)


if __name__ == "__main__":
    raise SystemExit(main())