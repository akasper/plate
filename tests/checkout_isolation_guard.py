"""Repo-wide checkout isolation guard for the unittest suite (#1542)."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path

WATCH_TREE_PREFIXES = (
    ".agentic",
    "docs/curiosity",
)


class CheckoutIsolationError(Exception):
    """Raised when the test suite leaves new or modified files in guarded paths."""


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def _fingerprint_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_watched_paths(repo_root: Path | None = None) -> dict[str, str]:
    """Hash tracked and untracked files under guarded zones (including repo-root files)."""
    root = (repo_root or repo_root_from_here()).resolve()
    state: dict[str, str] = {}
    for prefix in WATCH_TREE_PREFIXES:
        base = root / prefix
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                state[rel] = _fingerprint_file(path)
    for path in root.iterdir():
        if path.is_file():
            state[path.name] = _fingerprint_file(path)
    return state


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    for rel in sorted(set(before) | set(after)):
        if before.get(rel) != after.get(rel):
            changed.append(rel)
    return changed


def format_leak_report(leaks: list[str]) -> str:
    lines = [
        "Test suite modified the checkout under guarded paths "
        "(repo root files, .agentic/**, docs/curiosity/**).",
        "Sandbox leaking tests with tempfile.TemporaryDirectory plus chdir, "
        "or pass explicit base_dir / state_dir.",
        "",
        "Leaked paths:",
    ]
    lines.extend(f"  - {p}" for p in leaks)
    return "\n".join(lines)


def run_unittest_suite(*, start_dir: str = "tests", pattern: str = "test_*.py") -> unittest.TestResult:
    repo_root = repo_root_from_here()
    src = repo_root / "src"
    tests = repo_root / "tests"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    if str(tests) not in sys.path:
        sys.path.insert(0, str(tests))
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir, pattern=pattern, top_level_dir=str(repo_root))
    return unittest.TextTestRunner(verbosity=2).run(suite)


def main() -> int:
    if os.environ.get("PLATE_SKIP_CHECKOUT_ISOLATION") == "1":
        result = run_unittest_suite()
        return 0 if result.wasSuccessful() else 1

    repo_root = repo_root_from_here()
    before = snapshot_watched_paths(repo_root)
    result = run_unittest_suite()
    after = snapshot_watched_paths(repo_root)
    leaks = diff_snapshots(before, after)

    exit_code = 0 if result.wasSuccessful() else 1
    if leaks:
        print(format_leak_report(leaks), file=sys.stderr)
        # Distinct exit when tests passed but checkout was polluted.
        if result.wasSuccessful():
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())