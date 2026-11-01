"""PR comment attribution helpers (#1236).

Agents posting GitHub comments under a human account should prepend a short
attribution line. Configuration lives under ``.plate`` ``autonomy.comment_attribution``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_ATTRIBUTION_FORMAT = "🤖 {agent} on behalf of {on_behalf_of}"


def resolve_comment_attribution(
    repo_root: Path | str | None = None,
    *,
    autonomy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return effective ``comment_attribution`` settings (enabled + format template)."""
    from .plate_config import DEFAULT_CONFIG, load_plate_config

    if autonomy is None:
        autonomy = load_plate_config(repo_root).autonomy or {}
    defaults = (DEFAULT_CONFIG.get("autonomy") or {}).get("comment_attribution") or {}
    raw = autonomy.get("comment_attribution")
    if raw is None:
        raw = defaults
    if not isinstance(raw, dict):
        raw = {}

    enabled = raw.get("enabled", defaults.get("enabled", True))
    if not isinstance(enabled, bool):
        enabled = True

    fmt = raw.get("format") or defaults.get("format") or DEFAULT_ATTRIBUTION_FORMAT
    if not isinstance(fmt, str) or not fmt.strip():
        fmt = DEFAULT_ATTRIBUTION_FORMAT

    return {"enabled": enabled, "format": fmt}


def apply_comment_attribution(
    body: str,
    *,
    agent: str,
    on_behalf_of: str | None = None,
    repo_root: Path | str | None = None,
    enabled: bool | None = None,
    format_template: str | None = None,
) -> str:
    """Prepend a one-line attribution header when enabled.

    Intended for PR/issue comments and review-thread replies only — not PR
    descriptions or commit messages.
    """
    text = (body or "").strip()
    settings = resolve_comment_attribution(repo_root)
    use_enabled = settings["enabled"] if enabled is None else enabled
    if not use_enabled:
        return text

    agent_name = (agent or "").strip()
    if not agent_name:
        return text

    behalf = (on_behalf_of or "").strip() or "the account owner"
    tpl = format_template if format_template is not None else settings["format"]
    try:
        header = tpl.format(agent=agent_name, on_behalf_of=behalf)
    except (KeyError, ValueError):
        header = DEFAULT_ATTRIBUTION_FORMAT.format(agent=agent_name, on_behalf_of=behalf)
    header = header.strip()
    if not header:
        return text
    if text.startswith(header):
        return text
    return f"{header}\n\n{text}" if text else header
