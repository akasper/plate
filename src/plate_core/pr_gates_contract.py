"""Contract for the merged PLATE PR gates workflow (#1209).

The GitHub required status check context is the job id ``pr-gates`` in
``.github/workflows/plate-pr-gates.yml``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Job id reported to branch protection / PR checks UI.
PLATE_PR_GATES_CHECK_NAME = "pr-gates"

# Status check contexts superseded by PLATE_PR_GATES_CHECK_NAME.
DEPRECATED_PR_GATE_CHECK_CONTEXTS: frozenset[str] = frozenset(
    {
        "check-pr-title",
        "check-issue-links",
        "feature-change-files",
        "feedback-resolution",
        "audit",
        "validate-release-pr",
    }
)

# Current recommended required contexts for PLATE repos (plus repo-specific checks).
RECOMMENDED_REQUIRED_CHECK_CONTEXTS: tuple[str, ...] = (
    "labels",
    PLATE_PR_GATES_CHECK_NAME,
    "test",
)

# Each gate must appear as a named workflow step and fail with a distinct message.
PR_GATE_STEP_CONTRACTS: tuple[dict[str, str], ...] = (
    {
        "step_name": "Gate — PR title",
        "failure_marker": "Invalid PR title format",
    },
    {
        "step_name": "Gate — issue links",
        "failure_marker": "No linked issue detected",
    },
    {
        "step_name": "Gate — Feature release fragment",
        "failure_marker": "per-feature change files",
    },
    {
        "step_name": "Gate — feedback resolution",
        "failure_marker": "CHANGES_REQUESTED",
    },
    {
        "step_name": "Gate — audit checkout",
        "failure_marker": "",  # placeholder gate; no failure path today
    },
    {
        "step_name": "Gate — validate release PR",
        "failure_marker": "already exists on origin",
    },
)


def workflow_paths(repo_root: Path | None = None) -> tuple[Path, Path]:
    root = repo_root or Path(__file__).resolve().parents[2]
    return (
        root / ".github" / "workflows" / "plate-pr-gates.yml",
        root
        / "src"
        / "plate_core"
        / "template_payload"
        / ".github"
        / "workflows"
        / "plate-pr-gates.yml",
    )


def find_stale_required_check_contexts(contexts: list[str]) -> list[str]:
    """Return deprecated gate contexts still present in branch protection."""
    present = {c.strip() for c in contexts if c and c.strip()}
    return sorted(present & DEPRECATED_PR_GATE_CHECK_CONTEXTS)


def validate_merged_pr_gates_workflow(text: str) -> list[str]:
    """Return human-readable errors when the merged workflow drifts from contract."""
    errors: list[str] = []
    if "jobs:" not in text or "pr-gates:" not in text:
        errors.append("missing pr-gates job")
    if f"name: {PLATE_PR_GATES_CHECK_NAME}" not in text and "pr-gates:" not in text:
        errors.append("missing pr-gates job id")
    for gate in PR_GATE_STEP_CONTRACTS:
        step = gate["step_name"]
        if f"name: {step}" not in text:
            errors.append(f"missing step: {step}")
        marker = gate.get("failure_marker") or ""
        if marker and marker not in text:
            errors.append(f"missing failure marker for {step}: {marker!r}")
    if "cancel-in-progress: true" not in text:
        errors.append("missing concurrency cancel-in-progress")
    return errors


def normalize_workflow_for_parity(text: str) -> str:
    """Drop variant-specific release validation blocks for template vs plate parity."""
    # Plate monorepo uses validate_release_workspace; template uses git diff on release.json.
    text = re.sub(
        r"\n      - name: Gate — validate release PR\n.*?(?=\n      - name: |\n  [a-z])",
        "\n",
        text,
        flags=re.DOTALL,
    )
    return text.strip()
