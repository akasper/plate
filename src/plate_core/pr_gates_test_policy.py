"""Detect pytest runner/API use in PLATE test files (#1182)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

TEST_FILE_RE = re.compile(r"^tests/test_.*\.py$", re.IGNORECASE)

# Patterns match pytest as test runner/API — not incidental words (e.g. datetime).
_PYTEST_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bimport\s+pytest\b"),
    re.compile(r"\bfrom\s+pytest\b"),
    re.compile(r"@pytest\."),
    re.compile(
        r"\bpytest\.(?:main|fixture|raises|mark|parametrize|skip|warns|approx)\b"
    ),
)

_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')


@dataclass(frozen=True)
class PytestViolation:
    path: str
    line_number: int
    line: str


def is_plate_test_file(path: str) -> bool:
    normalized = (path or "").strip().replace("\\", "/")
    return bool(TEST_FILE_RE.match(normalized))


def _code_without_strings_and_comments(line: str) -> str:
    without_comment = line.split("#", 1)[0]
    return _STRING_LITERAL_RE.sub("", without_comment)


def find_pytest_violations_in_source(
    source: str, *, path: str = "tests/test_example.py"
) -> list[PytestViolation]:
    """Return violations in ``source`` (line-level, ignoring string literals)."""
    violations: list[PytestViolation] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        code = _code_without_strings_and_comments(raw_line)
        if not code.strip():
            continue
        for pattern in _PYTEST_LINE_PATTERNS:
            if pattern.search(code):
                violations.append(
                    PytestViolation(path=path, line_number=line_number, line=raw_line.rstrip())
                )
                break
    return violations


def filter_changed_test_paths(changed_paths: list[str]) -> list[str]:
    return sorted(
        {
            path.strip()
            for path in changed_paths
            if path.strip() and is_plate_test_file(path)
        }
    )


def scan_test_paths(
    paths: list[str],
    read_text: Callable[[str], str],
) -> list[PytestViolation]:
    """Scan added/changed test files for pytest use."""
    all_violations: list[PytestViolation] = []
    for path in filter_changed_test_paths(paths):
        try:
            source = read_text(path)
        except OSError:
            continue
        all_violations.extend(find_pytest_violations_in_source(source, path=path))
    return all_violations