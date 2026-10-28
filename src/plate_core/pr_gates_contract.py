"""Contract for the merged PLATE PR gates workflow (#1209).

The GitHub required status check context is the job id ``pr-gates`` in
``.github/workflows/plate-pr-gates.yml``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Job id reported to branch protection / PR checks UI.
PLATE_PR_GATES_CHECK_NAME = "pr-gates"

# PR type / process labels that should re-run merged gates on labeled/unlabeled events.
PLATE_PR_GATES_LABELS: frozenset[str] = frozenset(
    {
        "Feature",
        "Bug",
        "Documentation",
        "Feedback Response",
        "no-issue",
        "Release",
    }
)

PLATE_PR_GATES_LABELS_JSON = '["Feature","Bug","Documentation","Feedback Response","no-issue","Release"]'

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


def missing_recommended_check_contexts(contexts: list[str]) -> list[str]:
    """Return recommended contexts absent from branch protection (case-insensitive)."""
    present = {c.strip().lower() for c in contexts if c and c.strip()}
    return sorted(
        name
        for name in RECOMMENDED_REQUIRED_CHECK_CONTEXTS
        if name.lower() not in present
    )


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
    label_errors = validate_pr_gates_multi_label_event_safety(text)
    errors.extend(label_errors)
    errors.extend(validate_feature_fragment_gate_on_all_admitted_pr_events(text))
    return errors


_FEATURE_FRAGMENT_GATE_IF = re.compile(
    r"(?m)^      - name: Gate — Feature release fragment\n"
    r"        if: \|\n"
    r"((?:          .+\n)+?)"
    r"        uses: actions/github-script@v8\n"
)


def validate_feature_fragment_gate_on_all_admitted_pr_events(text: str) -> list[str]:
    """Feature fragment gate must run on every admitted pull_request when Feature (#1239).

    Non-gating labeled events (e.g. area:*, risk:*) admit the pr-gates job; skipping the
    fragment step would let the check pass without enforcing unreleased fragments.
    """
    errors: list[str] = []
    match = _FEATURE_FRAGMENT_GATE_IF.search(text)
    if not match:
        errors.append("missing Feature release fragment gate step with multiline if")
        return errors
    if_block = match.group(1)
    if "steps.feature_labels.outputs.is_feature == 'true'" not in if_block:
        errors.append(
            "Feature release fragment gate if must depend on steps.feature_labels.outputs.is_feature"
        )
    if "github.event.action" in if_block or "github.event.label" in if_block:
        errors.append(
            "Feature release fragment gate if must not restrict pull_request actions or "
            "label names (area:* / risk:* labeled events must still enforce fragments)"
        )
    return errors


def validate_pr_gates_multi_label_event_safety(text: str) -> list[str]:
    """Ensure non-gating label events cannot cancel gate runs or skip the pr-gates job (#1228)."""
    errors: list[str] = []
    if "concurrency:" not in text:
        errors.append("missing concurrency block")
        return errors
    if re.search(r"cancel-in-progress:\s*true\s*$", text, re.MULTILINE):
        errors.append(
            "concurrency cancel-in-progress must not be unconditionally true "
            "(non-gating labeled events must not cancel in-progress gate runs)"
        )
    if "label-noop" not in text:
        errors.append("missing label-noop concurrency group suffix for non-gating labels")
    if "cancel-in-progress: ${{" not in text:
        errors.append("missing conditional cancel-in-progress expression")
    skip_job_pattern = (
        r"contains\(fromJSON\('\[\"labeled\",\"unlabeled\"\]'\), github\.event\.action\)"
        r"\s*&&\s*contains\(fromJSON\('" + re.escape(PLATE_PR_GATES_LABELS_JSON) + r"'\)"
    )
    if re.search(skip_job_pattern, text):
        errors.append(
            "pr-gates job must not skip on non-gating labeled/unlabeled events "
            "(skipped checks satisfy required status)"
        )
    if "github.event.action != 'closed'" not in text:
        errors.append("pr-gates job should run for all pull_request actions except closed")
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
