#!/usr/bin/env python3
"""Generate plate-pr-gates.yml for plate repo and template payload (#1209)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _extract_script_block(workflow_path: Path, anchor: str) -> str:
    text = workflow_path.read_text(encoding="utf-8")
    anchor_idx = text.find(anchor)
    if anchor_idx < 0:
        raise SystemExit(f"anchor {anchor!r} not found in {workflow_path}")
    script_idx = text.find("script: |", anchor_idx)
    if script_idx < 0:
        raise SystemExit(f"script block not found after {anchor!r} in {workflow_path}")
    lines: list[str] = []
    for line in text[script_idx:].splitlines()[1:]:
        if line.startswith("            "):
            lines.append(line[12:])
        elif not line.strip():
            lines.append("")
        else:
            break
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def _yaml_script(script: str) -> str:
    indented = "".join(f"            {line}\n" for line in script.splitlines())
    return f"          script: |\n{indented}"


HEADER = """name: PLATE PR Gates

# Required status check context: pr-gates (this job id).
# Replaces separate workflows: pr-title-check, pr-issue-link-check,
# pr-documentation-check, feedback-resolution-check, audit, and ci validate-release-pr.

on:
  pull_request:
    types:
      - opened
      - edited
      - synchronize
      - reopened
      - labeled
      - unlabeled
      - milestoned
      - demilestoned
      - ready_for_review
      - closed
  pull_request_review:
    types: [submitted, edited, dismissed]
  pull_request_review_comment:
    types: [created, edited, deleted]
  push:
    branches: [release, 'release-*', 'release-v*']

concurrency:
  # Non-gating label events use an isolated group and must not cancel real gate runs (#1228).
  group: plate-pr-gates-${{ github.event.pull_request.number || github.ref }}-${{ github.event_name == 'pull_request' && contains(fromJSON('["labeled","unlabeled"]'), github.event.action) && !contains(fromJSON('["Feature","Bug","Documentation","Feedback Response","no-issue","Release"]'), github.event.label.name) && 'label-noop' || 'gate' }}
  cancel-in-progress: ${{ !(github.event_name == 'pull_request' && contains(fromJSON('["labeled","unlabeled"]'), github.event.action) && !contains(fromJSON('["Feature","Bug","Documentation","Feedback Response","no-issue","Release"]'), github.event.label.name)) }}

permissions:
  contents: read
  issues: read
  pull-requests: write
  actions: read

jobs:
  pr-gates:
    name: pr-gates
    if: |
      github.event_name == 'pull_request_review' ||
      github.event_name == 'pull_request_review_comment' ||
      (github.event_name == 'pull_request' && github.event.action != 'closed')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Select runs-on for heavy jobs
        id: plate_runs_on
        uses: ./.github/actions/plate-select-runs-on
        with:
          plate-runs-on: ${{ vars.PLATE_RUNS_ON }}

      - name: Gate — PR title
        if: |
          github.event_name == 'pull_request' &&
          contains(fromJSON('["opened","edited","synchronize","reopened","labeled","unlabeled","milestoned","demilestoned","ready_for_review"]'), github.event.action)
        uses: actions/github-script@v8
        with:
@@TITLE_SCRIPT@@

      - name: Gate — issue links
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v8
        with:
@@ISSUE_LINK_SCRIPT@@

      - name: Gate — Feature release fragment (labels)
        if: github.event_name == 'pull_request'
        id: feature_labels
        uses: actions/github-script@v8
        with:
          script: |
            const labels = (context.payload.pull_request?.labels || []).map((l) => l.name);
            const isFeature = labels.includes('Feature');
            core.setOutput('is_feature', String(isFeature));
            core.info(`Feature PR: ${isFeature}`);

      - name: Gate — Feature release fragment
        if: |
          github.event_name == 'pull_request' && steps.feature_labels.outputs.is_feature == 'true' && (
            contains(fromJSON('["opened","synchronize","reopened","edited"]'), github.event.action) ||
            (github.event.action == 'labeled' && github.event.label.name == 'Feature') ||
            (github.event.action == 'unlabeled' && github.event.label.name == 'Feature')
          )
        uses: actions/github-script@v8
        with:
@@FEATURE_FRAGMENT_SCRIPT@@

      - name: Gate — Feature release fragment (skip notice)
        if: |
          github.event_name == 'pull_request' && steps.feature_labels.outputs.is_feature != 'true'
        run: echo "Not a Feature PR; release fragment in .agentic/releases/unreleased/ is not required by this check."

      - name: Gate — feedback resolution
        if: |
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment' ||
          (github.event_name == 'pull_request' && contains(fromJSON('["opened","reopened","synchronize","ready_for_review","labeled","unlabeled","milestoned","demilestoned","edited"]'), github.event.action))
        uses: actions/github-script@v8
        env:
          PLATE_PR_FEEDBACK_AGENTS: ${{ vars.PLATE_PR_FEEDBACK_AGENTS }}
        with:
@@FEEDBACK_SCRIPT@@

      - name: Gate — audit checkout
        if: |
          github.event_name == 'pull_request' &&
          contains(fromJSON('["opened","synchronize","reopened","edited","labeled","unlabeled","milestoned","demilestoned","ready_for_review"]'), github.event.action)
        run: echo "Audit workflow context loaded (checkout complete)."

@@VALIDATE_RELEASE_STEP@@
"""

VALIDATE_PLATE = """
      - name: Gate — validate release PR
        if: |
          github.event_name == 'pull_request' && (
            contains(github.event.pull_request.labels.*.name, 'Release') ||
            github.head_ref == 'release' ||
            startsWith(github.head_ref, 'release-v')
          )
        run: |
          set -euo pipefail
          export PYTHONPATH="$GITHUB_WORKSPACE/src"
          python - <<'PY'
          import json
          import os
          import sys
          from pathlib import Path
          from plate_core.release import validate_release_workspace

          report = validate_release_workspace(Path(os.environ["GITHUB_WORKSPACE"]))
          print(json.dumps(report.to_dict(), indent=2))
          if report.errors:
              print("\\n".join(report.errors), file=sys.stderr)
              raise SystemExit(1)
          PY
          RELEASE_TAG="$(python - <<'PY'
          import os
          from pathlib import Path
          from plate_core.release import validate_release_workspace
          report = validate_release_workspace(Path(os.environ["GITHUB_WORKSPACE"]))
          print(report.release_tag)
          PY
          )"
          if git ls-remote --tags origin "refs/tags/${RELEASE_TAG}" | grep -q .; then
            echo "Release tag ${RELEASE_TAG} already exists on origin."
            exit 1
          fi
"""

VALIDATE_TEMPLATE = """
      - name: Gate — validate release PR
        if: |
          github.event_name == 'pull_request' && (
            contains(github.event.pull_request.labels.*.name, 'Release') ||
            github.head_ref == 'release' ||
            startsWith(github.head_ref, 'release-v')
          )
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.sha }}
        run: |
          set -euo pipefail
          release_files="$(git diff --name-only "${BASE_SHA}" "${HEAD_SHA}" | grep -E '^\\.agentic/releases/v[0-9]+\\.[0-9]+\\.[0-9]+/release\\.json$' || true)"
          release_file_count="$(printf '%s\\n' "${release_files}" | sed '/^$/d' | wc -l | tr -d ' ')"
          if [ "${release_file_count}" -ne 1 ]; then
            echo "Expected exactly one changed versioned release artifact in the PR, found ${release_file_count}."
            printf '%s\\n' "${release_files}"
            exit 1
          fi
          release_file="$(printf '%s\\n' "${release_files}" | sed -n '1p')"
          release_tag="$(python - "${release_file}" <<'PY'
          import json
          import sys
          with open(sys.argv[1], encoding="utf-8") as fh:
              data = json.load(fh)
          version = data.get("version")
          if not isinstance(version, str) or not version:
              raise SystemExit("release.json must include a non-empty string version")
          print(f"v{version}")
          PY
          )"
          if git ls-remote --tags origin "refs/tags/${release_tag}" | grep -q .; then
            echo "Release tag ${release_tag} already exists on origin."
            exit 1
          fi
"""

MARK_IMPLEMENTED = """
  mark-implemented-on-release-merge:
    if: |
      (github.event_name == 'pull_request' &&
       github.event.action == 'closed' &&
       github.event.pull_request.merged == true &&
       (startsWith(github.event.pull_request.base.ref, 'release') ||
        github.event.pull_request.base.ref == 'release' ||
        startsWith(github.event.pull_request.base.ref, 'epic/'))) ||
      (github.event_name == 'push' &&
       (startsWith(github.ref, 'refs/heads/release') || startsWith(github.ref, 'refs/heads/epic/')))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: read
    steps:
      - name: Mark implemented + auto-close linked issues (integration merge)
        uses: actions/github-script@v8
        with:
@@MARK_SCRIPT@@
"""


def build(variant: str) -> str:
    gates_src = ROOT / ".github/workflows/plate-pr-gates.yml"
    title_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — PR title")
    )
    issue_link_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — issue links")
    )
    feature_fragment_script = _yaml_script(
        _extract_script_block(
            gates_src,
            "Gate — Feature release fragment\n        if: |\n          github.event_name == 'pull_request' && steps.feature_labels",
        )
    )
    feedback_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — feedback resolution")
    )
    mark_script = _yaml_script(
        _extract_script_block(gates_src, "Mark implemented")
    )
    validate = VALIDATE_PLATE if variant == "plate" else VALIDATE_TEMPLATE
    body = HEADER.replace("@@TITLE_SCRIPT@@", title_script)
    body = body.replace("@@ISSUE_LINK_SCRIPT@@", issue_link_script)
    body = body.replace("@@FEATURE_FRAGMENT_SCRIPT@@", feature_fragment_script)
    body = body.replace("@@FEEDBACK_SCRIPT@@", feedback_script)
    body = body.replace("@@VALIDATE_RELEASE_STEP@@", validate.lstrip("\n").rstrip() + "\n")
    body += MARK_IMPLEMENTED.replace("@@MARK_SCRIPT@@", mark_script)
    return body


def main() -> None:
    targets = {
        "plate": ROOT / ".github/workflows/plate-pr-gates.yml",
        "template": ROOT
        / "src/plate_core/template_payload/.github/workflows/plate-pr-gates.yml",
    }
    for variant, path in targets.items():
        path.write_text(build(variant), encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
