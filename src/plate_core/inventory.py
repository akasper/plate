"""Canonical inventory runtime for PLATE methodology assets (supporting migration, health, etc.).

Provides get_inventory() for use by migration planner (#131), health checks, and future surfaces.
Data sourced from the maintained template_payload_inventory.json (produced by prior inventory work).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def get_inventory(repo_root: Path | None = None) -> Dict[str, Any]:
    """
    Return the canonical PLATE/template inventory as a dict.

    In normal use this loads the packaged data file. Callers can pass repo_root
    for testing against a different checkout.
    """
    if repo_root is None:
        # When running from src/ layout or installed package
        base = Path(__file__).parent
        data_path = base / "data" / "template_payload_inventory.json"
    else:
        data_path = Path(repo_root) / "src" / "plate_core" / "data" / "template_payload_inventory.json"

    if not data_path.exists():
        # Fallback for some dev layouts
        alt = Path(__file__).parent.parent / "data" / "template_payload_inventory.json"
        if alt.exists():
            data_path = alt
        else:
            return {
                "error": "inventory data file not found",
                "searched": str(data_path),
            }

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        # Light enrichment for consumers (migration planner etc.)
        if isinstance(data, dict):
            data.setdefault("source", "plate_core.inventory")
            data.setdefault("retrieved_for", "migration_dry_run")
        return data
    except Exception as exc:
        return {"error": f"failed to load inventory: {exc}"}
