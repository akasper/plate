"""Confine MCP filesystem paths to a repository root (#1475)."""

from __future__ import annotations

import re
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
            "Path escapes the repository root"
        ) from exc
    return candidate


def confined_or_default(path: str | Path | None, root: Path | None = None) -> Path:
    return confined(path, root)


_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w.-])/(?:[\w.-]+/)+[\w.-]+")


def redact_absolute_paths(text: str, root: Path | None = None) -> str:
    """Remove or relativize absolute filesystem paths for JSON-RPC clients."""
    if not text:
        return text
    base = (root or session_repo_root()).resolve()
    base_s = str(base)
    redacted = text.replace(base_s, "<repo>")
    # Common temp / agent paths
    redacted = re.sub(r"/(?:agent|tmp|var|home|Users)/[^\s\"']+", "<path>", redacted)
    redacted = _ABSOLUTE_PATH_PATTERN.sub("<path>", redacted)
    return redacted


def client_safe_error_message(exc: BaseException, root: Path | None = None) -> str:
    """Format an exception for tools/call error payloads without leaking host paths."""
    if isinstance(exc, PathConfinementError):
        return str(exc) or "Path escapes the repository root"
    return redact_absolute_paths(str(exc), root)