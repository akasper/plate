"""Optional tier:* label rules shared by label-check workflows (#1328)."""

from __future__ import annotations

ALLOWED_TIER_LABELS: tuple[str, ...] = ("tier:T0", "tier:T1", "tier:T2", "tier:T3")


def tier_label_validation_error(labels: list[str]) -> str | None:
    """Return a failure message when tier labels violate PLATE rules, else None."""
    tier_matches = [label for label in labels if label in ALLOWED_TIER_LABELS]
    invalid_tier = [
        label
        for label in labels
        if label.startswith("tier:") and label not in ALLOWED_TIER_LABELS
    ]
    if invalid_tier:
        allowed = ", ".join(ALLOWED_TIER_LABELS)
        return (
            f"Unsupported tier labels ({', '.join(invalid_tier)}). "
            f"Allowed optional tier labels: {allowed}."
        )
    if len(tier_matches) > 1:
        allowed = ", ".join(ALLOWED_TIER_LABELS)
        return (
            f"At most one optional tier label is allowed ({allowed}). "
            f"Found: {', '.join(tier_matches)}."
        )
    return None
