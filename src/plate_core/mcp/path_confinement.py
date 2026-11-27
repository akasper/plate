"""Confine MCP filesystem paths to a repository root (#1475)."""

from __future__ import annotations

import os
from pathlib import Path


class PathConfinementError(ValueError):
    """Raised when a path escapes the allowed repository root."""


def session_repo_root() -> Path:
    """Best-effort repository root for this MCP server process."""
    cwd = Path.cwd().resolve()
    for start in (cwd, *cwd.parents):
        if (start / ".git").exists():
            return start
    return cwd


def confined(path: str | Path | None, root: Path | None = None) -> Path:
    """Resolve ``path`` under ``root``; reject escapes (including symlinks)."""
    base = (root or session_repo_root()).resolve()
    if path is None or str(path).strip() in ("", "."):
        candidate = base
    else:
        raw = Path(path)
        candidate = (base / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise PathConfinementError(
            f"Path {candidate!s} is outside confined root {base!s}"
        ) from exc
    return candidate


def confined_or_default(path: str | Path | None, root: Path | None = None) -> Path:
    return confined(path, root)