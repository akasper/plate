"""GitHub label registry helpers (description limits, shipped labels.yml validation)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from .github_client import GhApiError, GhClient

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


def _normalize_label_color(color: str) -> str:
    return str(color or "").strip().lstrip("#").lower()


def _label_entry_from_api(raw: dict[str, Any]) -> dict[str, str]:
    name = str(raw.get("name") or "")
    color = _normalize_label_color(str(raw.get("color") or ""))
    description = str(raw.get("description") or "")
    return {"name": name, "color": color, "description": description}


def fetch_repository_labels(gh: GhClient, repo: str) -> list[dict[str, str]]:
    """Return label records from GitHub (handles simple pagination)."""
    collected: list[dict[str, str]] = []
    page = 1
    while True:
        batch = gh.api(f"repos/{repo}/labels?per_page=100&page={page}")
        if not batch:
            break
        if not isinstance(batch, list):
            break
        for item in batch:
            if isinstance(item, dict):
                collected.append(_label_entry_from_api(item))
        if len(batch) < 100:
            break
        page += 1
    return collected


def registry_label_case_mismatches(
    expected: list[str],
    remote_labels: list[dict[str, str]],
) -> list[str]:
    """Return messages when a registry label exists on GitHub with non-canonical casing."""
    by_lower: dict[str, str] = {}
    for item in remote_labels:
        by_lower[item["name"].lower()] = item["name"]
    messages: list[str] = []
    for canonical in expected:
        lower = canonical.lower()
        actual = by_lower.get(lower)
        if actual is not None and actual != canonical:
            messages.append(f"`{actual}` should be `{canonical}`")
    return messages


@dataclass
class LabelSyncOutcome:
    name: str
    state: str
    detail: str


def sync_repository_labels_from_registry(
    gh: GhClient,
    repo: str,
    registry_path: Path,
    *,
    apply: bool,
) -> list[LabelSyncOutcome]:
    """Ensure every label in ``registry_path`` exists with canonical name, color, and description.

    When a GitHub default label differs only by case (e.g. ``bug`` vs ``Bug``), rename it
    instead of creating a duplicate. Never deletes labels.
    """
    entries = load_labels_from_yaml(registry_path)
    existing = fetch_repository_labels(gh, repo)
    by_lower: dict[str, dict[str, str]] = {}
    for item in existing:
        by_lower[item["name"].lower()] = item

    outcomes: list[LabelSyncOutcome] = []
    for entry in entries:
        canonical_name = str(entry.get("name") or "").strip()
        if not canonical_name:
            continue
        target_color = _normalize_label_color(str(entry.get("color") or ""))
        target_description, _warn = prepare_label_description(str(entry.get("description") or ""))
        lower = canonical_name.lower()
        current = by_lower.get(lower)

        if current is None:
            if apply:
                try:
                    gh.api(
                        f"repos/{repo}/labels",
                        method="POST",
                        fields={
                            "name": canonical_name,
                            "color": target_color or "ededed",
                            "description": target_description,
                        },
                    )
                    state = "applied"
                    detail = f"created {canonical_name}"
                except GhApiError as exc:
                    state = "failed"
                    detail = f"{canonical_name}: {exc}"
            else:
                state = "planned"
                detail = f"create {canonical_name}"
            outcomes.append(LabelSyncOutcome(name=canonical_name, state=state, detail=detail))
            by_lower[lower] = {
                "name": canonical_name,
                "color": target_color,
                "description": target_description,
            }
            continue

        actual_name = current["name"]
        needs_rename = actual_name != canonical_name
        needs_update = (
            needs_rename
            or current["color"] != target_color
            or current["description"] != target_description
        )
        if not needs_update:
            outcomes.append(
                LabelSyncOutcome(
                    name=canonical_name,
                    state="already-configured",
                    detail=canonical_name,
                )
            )
            continue

        if apply:
            fields: dict[str, Any] = {
                "color": target_color or "ededed",
                "description": target_description,
            }
            if needs_rename:
                fields["new_name"] = canonical_name
            try:
                gh.api(
                    f"repos/{repo}/labels/{quote(actual_name, safe='')}",
                    method="PATCH",
                    fields=fields,
                )
                state = "applied"
                if needs_rename:
                    detail = f"renamed {actual_name} → {canonical_name}"
                else:
                    detail = f"updated {canonical_name}"
            except GhApiError as exc:
                state = "failed"
                detail = f"{canonical_name}: {exc}"
        else:
            state = "planned"
            if needs_rename:
                detail = f"rename {actual_name} → {canonical_name}"
            else:
                detail = f"update {canonical_name}"
        outcomes.append(LabelSyncOutcome(name=canonical_name, state=state, detail=detail))
        by_lower[lower] = {
            "name": canonical_name,
            "color": target_color,
            "description": target_description,
        }
    return outcomes


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
