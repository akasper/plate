"""PR gate: changed tests must use stdlib unittest, not pytest (#1182)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from plate_core.pr_gates_test_policy import scan_test_paths

FAILURE_HEADING = "stdlib unittest policy"
FAILURE_MARKER = "stdlib unittest policy"


def _default_reader(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def format_violation_message(path: str, line_number: int, line: str) -> str:
    return f"{path}:{line_number}: {line.strip()}"


def run_gate(
    paths: list[str], *, read_text: Callable[[str], str] | None = None
) -> int:
    reader = read_text or _default_reader
    violations = scan_test_paths(paths, reader)
    if not violations:
        return 0
    print(
        "\n".join(
            [
                f"## ⚠️ {FAILURE_HEADING}",
                "",
                "PLATE tests use stdlib `unittest` (`python -m unittest discover`). "
                "Changed test files must not import or invoke pytest.",
                "",
                *(format_violation_message(v.path, v.line_number, v.line) for v in violations),
            ]
        ),
        file=sys.stderr,
    )
    return 1


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
        help="Newline-separated changed file paths from the PR",
    )
    args = parser.parse_args(argv)
    return run_gate(_read_paths_file(args.paths_file))


if __name__ == "__main__":
    raise SystemExit(main())