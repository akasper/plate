"""Load ``.agentic/process.yml`` and merge documented defaults (leases, etc.)."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

# Issue lifecycle / Lull contract defaults (#1427); merged under top-level ``leases:``.
DEFAULT_LEASES_CONFIG: dict[str, Any] = {
    "adapter": "local",
    "ttl_s": 600,
    "grace_s": 60,
    "no_capacity_deadline": "6h",
    "revocations_before_human": 3,
}

_DURATION_SUFFIX = re.compile(r"^\s*(\d+)\s*([hms])\s*$", re.I)


def parse_duration_value(value: Any) -> int:
    """Parse a duration for lease policy into seconds.

    Accepts a non-negative int (seconds) or strings like ``6h``, ``90m``, ``30s``.
    """

    if value is None:
        raise ValueError("duration must not be None")
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid duration")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("duration seconds must be non-negative")
        return value
    if isinstance(value, float) and value.is_integer():
        return parse_duration_value(int(value))
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return parse_duration_value(int(s))
        m = _DURATION_SUFFIX.match(s)
        if not m:
            raise ValueError(f"unrecognized duration format: {value!r}")
        n = int(m.group(1))
        unit = m.group(2).lower()
        mult = {"s": 1, "m": 60, "h": 3600}.get(unit)
        if mult is None:
            raise ValueError(f"unsupported duration unit in {value!r}")
        return n * mult
    raise TypeError(f"duration must be int or str, got {type(value).__name__}")


def normalize_leases_config(raw: Any) -> dict[str, Any]:
    """Return a full leases block with defaults applied and normalized."""

    if raw is None:
        base: dict[str, Any] = {}
    elif isinstance(raw, dict):
        base = copy.deepcopy(raw)
    else:
        raise TypeError("leases must be a mapping if present")

    merged = {**DEFAULT_LEASES_CONFIG, **base}

    adapter = merged.get("adapter", "local")
    if not isinstance(adapter, str) or not adapter.strip():
        raise ValueError("leases.adapter must be a non-empty string")
    merged["adapter"] = adapter.strip()

    ttl_s = merged.get("ttl_s", DEFAULT_LEASES_CONFIG["ttl_s"])
    if not isinstance(ttl_s, int) or ttl_s <= 0:
        raise ValueError("leases.ttl_s must be a positive integer")
    merged["ttl_s"] = ttl_s

    grace_s = merged.get("grace_s", DEFAULT_LEASES_CONFIG["grace_s"])
    if not isinstance(grace_s, int) or grace_s < 0:
        raise ValueError("leases.grace_s must be a non-negative integer")
    merged["grace_s"] = grace_s

    merged["no_capacity_deadline"] = merged.get(
        "no_capacity_deadline", DEFAULT_LEASES_CONFIG["no_capacity_deadline"]
    )
    merged["no_capacity_deadline_s"] = parse_duration_value(merged["no_capacity_deadline"])

    rbh = merged.get("revocations_before_human", DEFAULT_LEASES_CONFIG["revocations_before_human"])
    if not isinstance(rbh, int) or rbh <= 0:
        raise ValueError("leases.revocations_before_human must be a positive integer")
    merged["revocations_before_human"] = rbh

    return merged


def load_process_yaml_dict(path: Path | str) -> dict[str, Any]:
    """Parse a process YAML file into a dict (empty document → {})."""

    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: expected a mapping at the top level")
    return raw


def merge_process_config_with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with defaulted/normalized keys."""

    out = copy.deepcopy(data)
    out["leases"] = normalize_leases_config(out.get("leases"))
    return out


def load_merged_process_config(path: Path | str) -> dict[str, Any]:
    """Load ``.agentic/process.yml``-style YAML merged with supported defaults."""

    return merge_process_config_with_defaults(load_process_yaml_dict(path))
