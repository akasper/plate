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


def confined(
    path: str | Path | None,
    root: Path | None = None,
    *,
    cwd_relative: bool = False,
) -> Path:
    """Resolve ``path`` inside repository ``root``; reject escapes (including symlinks).

    When ``cwd_relative`` is true, relative segments and ``"."`` resolve from the server
    working directory, while the allowed boundary remains ``root`` (the session git root).
    """
    boundary = (root or session_repo_root()).resolve()
    resolve_base = Path.cwd().resolve() if cwd_relative else boundary
    if path is None or str(path).strip() in ("", "."):
        candidate = resolve_base if cwd_relative else boundary
    else:
        raw = Path(path)
        if raw.is_absolute():
            candidate = raw.resolve()
        else:
            candidate = (resolve_base / raw).resolve()
    try:
        candidate.relative_to(boundary)
    except ValueError as exc:
        raise PathConfinementError(
            "Path escapes the repository root"
        ) from exc
    return candidate


def confined_write_path(path: Path, boundary: Path | None = None) -> Path:
    """Ensure a write target resolves inside the boundary after following symlinks."""
    base = (boundary or session_repo_root()).resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathConfinementError(
            "Path escapes the repository root"
        ) from exc
    return resolved


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
    home = Path.home()
    home_s = str(home.resolve())
    if home_s:
        redacted = redacted.replace(home_s, "<home>")
    redacted = re.sub(r"~(?:/[^\s\"']*)?", "<home>", redacted)
    redacted = re.sub(r"/(?:agent|tmp|var|home|Users)/[^\s\"']+", "<path>", redacted)
    redacted = _ABSOLUTE_PATH_PATTERN.sub("<path>", redacted)
    return redacted


def client_safe_error_message(exc: BaseException, root: Path | None = None) -> str:
    """Format an exception for tools/call error payloads without leaking host paths."""
    if isinstance(exc, PathConfinementError):
        return str(exc) or "Path escapes the repository root"
    return redact_absolute_paths(str(exc), root)