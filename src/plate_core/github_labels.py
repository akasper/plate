"""GitHub label registry helpers (description limits, shipped labels.yml validation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

GITHUB_LABEL_DESCRIPTION_MAX_LENGTH = 100

SHIPPED_LABELS_YML_RELATIVE_PATHS = (
    ".github/labels.yml",
    "src/plate_core/template_payload/.github/labels.yml",
)


def load_labels_from_yaml(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a YAML list of label entries")
    return data


def prepare_label_description(description: str) -> tuple[str, str | None]:
    """Return ``(description_for_api, warning)``; truncate when over GitHub's limit."""
    desc = description or ""
    if len(desc) <= GITHUB_LABEL_DESCRIPTION_MAX_LENGTH:
        return desc, None
    truncated = desc[:GITHUB_LABEL_DESCRIPTION_MAX_LENGTH]
    warning = (
        f"Label description length {len(desc)} exceeds GitHub limit "
        f"({GITHUB_LABEL_DESCRIPTION_MAX_LENGTH}); truncated to {len(truncated)} characters."
    )
    return truncated, warning


def find_overlong_shipped_label_descriptions(repo_root: Path) -> list[tuple[str, str, int]]:
    """Return ``(relative_path, label_name, length)`` for descriptions over the GitHub limit."""
    violations: list[tuple[str, str, int]] = []
    for rel in SHIPPED_LABELS_YML_RELATIVE_PATHS:
        path = repo_root / rel
        for entry in load_labels_from_yaml(path):
            name = str(entry.get("name") or "")
            desc = str(entry.get("description") or "")
            length = len(desc)
            if length > GITHUB_LABEL_DESCRIPTION_MAX_LENGTH:
                violations.append((rel, name, length))
    return violations
