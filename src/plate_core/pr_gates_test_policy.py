"""Detect pytest runner/API use in PLATE test files (#1182)."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass

TEST_FILE_RE = re.compile(r"^tests/(?:test_.*\.py|conftest\.py)$", re.IGNORECASE)

_PYTEST_MODULE_NAMES = frozenset({"pytest"})


@dataclass(frozen=True)
class PytestViolation:
    path: str
    line_number: int
    line: str


@dataclass(frozen=True)
class ScanFailure:
    path: str
    message: str


def is_plate_test_file(path: str) -> bool:
    normalized = (path or "").strip().replace("\\", "/")
    return bool(TEST_FILE_RE.match(normalized))


def _line_snippet(source: str, lineno: int) -> str:
    lines = source.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].rstrip()
    return ""


def _is_pytest_module(module: str | None) -> bool:
    if not module:
        return False
    root = module.split(".", 1)[0]
    return root in _PYTEST_MODULE_NAMES


class _PytestVisitor(ast.NodeVisitor):
    def __init__(self, source: str, path: str) -> None:
        self.source = source
        self.path = path
        self.violations: list[PytestViolation] = []
        self._pytest_aliases: set[str] = {"pytest"}

    def _record(self, node: ast.AST, *, snippet: str | None = None) -> None:
        lineno = getattr(node, "lineno", 1) or 1
        line = snippet if snippet is not None else _line_snippet(self.source, lineno)
        self.violations.append(PytestViolation(self.path, lineno, line))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _is_pytest_module(alias.name):
                if alias.asname:
                    self._pytest_aliases.add(alias.asname)
                self._record(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if _is_pytest_module(node.module):
            self._record(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            if (
                isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and _is_pytest_module(node.args[0].value)
            ):
                self._record(node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in self._pytest_aliases:
            self._record(node)
        self.generic_visit(node)

def find_pytest_violations_in_source(
    source: str, *, path: str = "tests/test_example.py"
) -> list[PytestViolation]:
    """Return pytest policy violations using AST analysis."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        lineno = exc.lineno or 1
        return [
            PytestViolation(
                path=path,
                line_number=lineno,
                line=f"unparseable test file: {exc.msg}",
            )
        ]
    visitor = _PytestVisitor(source, path)
    visitor.visit(tree)
    return visitor.violations


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
) -> tuple[list[PytestViolation], list[ScanFailure]]:
    """Scan changed test files; unreadable files fail closed via ScanFailure."""
    all_violations: list[PytestViolation] = []
    failures: list[ScanFailure] = []
    for path in filter_changed_test_paths(paths):
        try:
            source = read_text(path)
        except OSError as exc:
            failures.append(ScanFailure(path=path, message=str(exc)))
            continue
        all_violations.extend(find_pytest_violations_in_source(source, path=path))
    return all_violations, failures


def find_pytest_violations_in_source_legacy_line_scan(
    source: str, *, path: str = "tests/test_example.py"
) -> list[PytestViolation]:
    """Backward-compatible export for tests that referenced the old helper name."""
    return find_pytest_violations_in_source(source, path=path)