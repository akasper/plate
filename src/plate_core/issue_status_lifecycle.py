"""Canonical PLATE ``status:*`` label lifecycle (#1385 / #1440).

GitHub issue **open/closed** state is orthogonal to these labels; this module
only models the four documented ``status:*`` labels and workflow events that
mutate them.

Workflows that cannot run Python (for example ``label-check``) mirror the
predicates here; parity is covered by repository tests.
"""

from __future__ import annotations

from typing import Iterable, Literal

# Every allowed ``status:*`` value for issues (must match ``.github/labels.yml``).
ALLOWED_STATUS_LABELS: frozenset[str] = frozenset(
    (
        "status:stub",
        "status:blocked",
        "status:ready-to-work",
        "status:implemented",
    )
)

# Issue *type* labels that must not receive ``status:implemented`` from the
# integration-branch merge job (Epic/Task/Release stay open until their own
# ceremony) — see #1385 transition table.
IMPLEMENTATION_SKIP_ISSUE_TYPES: frozenset[str] = frozenset({"Epic", "Task", "Release"})

TransitionEvent = Literal["mark_ready", "block", "unblock", "integrate_merge"]


class MultipleStatusLabelsError(ValueError):
    """More than one allowed ``status:*`` label on the same issue."""


def status_labels_present(labels: Iterable[str]) -> list[str]:
    """Return ``status:*`` labels from ``labels`` that are in ``ALLOWED_STATUS_LABELS``."""
    return [str(x) for x in labels if str(x) in ALLOWED_STATUS_LABELS]


def forbidden_planning_labels(labels: Iterable[str]) -> list[str]:
    """``priority:*`` labels and unknown ``status:*`` labels (illegal planning labels)."""
    out: list[str] = []
    for label in labels:
        s = str(label)
        if s.startswith("priority:"):
            out.append(s)
        elif s.startswith("status:") and s not in ALLOWED_STATUS_LABELS:
            out.append(s)
    return out


def multiple_status_labels_message(labels: Iterable[str]) -> str | None:
    """Return a failure message when more than one allowed ``status:*`` is present."""
    present = status_labels_present(labels)
    if len(present) <= 1:
        return None
    uniq = ", ".join(sorted(set(present)))
    allowed = ", ".join(sorted(ALLOWED_STATUS_LABELS))
    return (
        f"At most one PLATE status label is allowed ({allowed}). "
        f"Found: {uniq}."
    )


def validate_status_label_uniqueness(labels: Iterable[str]) -> None:
    """Raise ``MultipleStatusLabelsError`` when two+ allowed status labels are set."""
    present = status_labels_present(labels)
    if len(present) > 1:
        raise MultipleStatusLabelsError(multiple_status_labels_message(labels) or repr(present))


def sole_status_label(labels: Iterable[str]) -> str | None:
    """The single allowed status label, or ``None``; raises if count > 1."""
    validate_status_label_uniqueness(labels)
    present = status_labels_present(labels)
    return present[0] if present else None


def planning_labels_validation_error(labels: Iterable[str]) -> str | None:
    """Combined illegal planning + multi-status check; message for CI or agents."""
    bad = forbidden_planning_labels(labels)
    if bad:
        return (
            "PLATE repositories should use GitHub Projects fields for planning state, "
            f"not labels: {', '.join(bad)}."
        )
    return multiple_status_labels_message(labels)


def should_apply_status_implemented(issue_type_labels: Iterable[str]) -> bool:
    """True when integration merge may add ``status:implemented`` (#1385)."""
    labs = {str(x) for x in issue_type_labels}
    return not (labs & IMPLEMENTATION_SKIP_ISSUE_TYPES)


def transition_label_deltas(
    current_labels: Iterable[str],
    event: TransitionEvent,
) -> tuple[set[str], set[str]]:
    """Return ``(remove, add)`` label name sets for a logical lifecycle event.

    Callers apply with add/remove APIs (not full ``setLabels`` replace) when
    enforcing additive transitions.

    Events (from #1385):

    - ``mark_ready``: stub → ready-to-work
    - ``block``: stub → blocked
    - ``unblock``: blocked → ready-to-work (also strips stub if present)
    - ``integrate_merge``: * → implemented (removes any allowed status, adds implemented)
    """
    cur = {str(x) for x in current_labels}
    validate_status_label_uniqueness(cur)

    if event == "mark_ready":
        return (cur & ALLOWED_STATUS_LABELS) - {"status:ready-to-work"}, {"status:ready-to-work"}
    if event == "block":
        return (cur & ALLOWED_STATUS_LABELS) - {"status:blocked"}, {"status:blocked"}
    if event == "unblock":
        remove = cur & ALLOWED_STATUS_LABELS
        return remove, {"status:ready-to-work"}
    if event == "integrate_merge":
        return cur & ALLOWED_STATUS_LABELS, {"status:implemented"}
    raise ValueError(f"unknown transition event: {event!r}")


def apply_transition(
    current_labels: Iterable[str],
    event: TransitionEvent,
) -> set[str]:
    """Return the full next label set after ``event`` (deduped)."""
    cur = {str(x) for x in current_labels}
    remove, add = transition_label_deltas(cur, event)
    return (cur - remove) | add


def promote_unblocked_feature_labels(existing_labels: Iterable[str]) -> set[str]:
    """Label set after ``plates-unblock-features`` promotes a Feature (``unblock`` event)."""
    return apply_transition(existing_labels, "unblock")
