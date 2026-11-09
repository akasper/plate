#!/usr/bin/env python3
"""Generate plate-pr-gates.yml for plate repo and template payload (#1209)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _plate_core_pip_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"(?P<ver>[^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("could not read project version from pyproject.toml")
    return match.group("ver")


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
  # Review events use a separate group so they never cancel in-flight pull_request gate runs (#1258).
  group: plate-pr-gates-${{ github.event.pull_request.number || github.ref }}-${{ (github.event_name == 'pull_request_review' || github.event_name == 'pull_request_review_comment') && 'review' || github.event_name == 'pull_request' && contains(fromJSON('["labeled","unlabeled"]'), github.event.action) && !contains(fromJSON('["Feature","Bug","Documentation","Feedback Response","no-issue","Release","main-source-override","release-window-override","release-window:open"]'), github.event.label.name) && 'label-noop' || 'gate' }}
  cancel-in-progress: ${{ (github.event_name == 'pull_request_review' || github.event_name == 'pull_request_review_comment') || !(github.event_name == 'pull_request' && contains(fromJSON('["labeled","unlabeled"]'), github.event.action) && !contains(fromJSON('["Feature","Bug","Documentation","Feedback Response","no-issue","Release","main-source-override","release-window-override","release-window:open"]'), github.event.label.name)) }}

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

@@TRUSTED_RUNTIME_PREP@@

      - name: Gate — PR title
        if: |
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment' ||
          (github.event_name == 'pull_request' &&
          contains(fromJSON('["opened","edited","synchronize","reopened","labeled","unlabeled","milestoned","demilestoned","ready_for_review"]'), github.event.action))
        uses: actions/github-script@v8
        with:
@@TITLE_SCRIPT@@

      - name: Gate — issue links
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        uses: actions/github-script@v8
        with:
@@ISSUE_LINK_SCRIPT@@

@@MAIN_SOURCE_RUN@@

@@REVIEWER_MODEL_RUN@@

      - name: Gate — Feature release fragment (labels)
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        id: feature_labels
        uses: actions/github-script@v8
        with:
@@FEATURE_LABELS_SCRIPT@@

      - name: Gate — Feature release fragment
        if: |
          (github.event_name == 'pull_request' ||
           github.event_name == 'pull_request_review' ||
           github.event_name == 'pull_request_review_comment') &&
          steps.feature_labels.outputs.is_feature == 'true'
        uses: actions/github-script@v8
        with:
@@FEATURE_FRAGMENT_SCRIPT@@

      - name: Gate — Feature release fragment (skip notice)
        if: |
          (github.event_name == 'pull_request' ||
           github.event_name == 'pull_request_review' ||
           github.event_name == 'pull_request_review_comment') &&
          steps.feature_labels.outputs.is_feature != 'true'
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
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment' ||
          (github.event_name == 'pull_request' &&
          contains(fromJSON('["opened","synchronize","reopened","edited","labeled","unlabeled","milestoned","demilestoned","ready_for_review"]'), github.event.action))
        run: echo "Audit workflow context loaded (checkout complete)."

      - name: Gate — validate release PR (detect)
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        id: release_gate_detect
        uses: actions/github-script@v8
        with:
@@RELEASE_DETECT_SCRIPT@@

@@VALIDATE_RELEASE_RUN@@
"""

TRUSTED_RUNTIME_PREP = """
      - name: Prepare trusted policy runtime
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          default_branch="$(gh api "repos/${GITHUB_REPOSITORY}" --jq .default_branch)"
          git fetch --no-tags --depth=1 origin "${default_branch}"
          trusted="${RUNNER_TEMP}/plate-policy-trusted"
          verify_cwd="${RUNNER_TEMP}/plate-policy-verify-cwd"
          rm -rf "${trusted}" "${verify_cwd}" && mkdir -p "${trusted}" "${verify_cwd}"
          if ! git archive "origin/${default_branch}" src/plate_core .agentic/policy-runtime.json | tar -x -C "${trusted}"; then
            echo "::error title=policy-runtime::Could not archive policy runtime from origin/${default_branch}."
            exit 1
          fi
          if [ ! -d "${trusted}/src/plate_core" ] || [ ! -f "${trusted}/.agentic/policy-runtime.json" ]; then
            echo "::error title=policy-runtime::Default-branch archive missing src/plate_core or .agentic/policy-runtime.json (deploy policy to default branch before merge-authoritative gates)."
            exit 1
          fi
          if ! (
            cd "${verify_cwd}"
            export PYTHONPATH="${trusted}/src"
            export PYTHONNOUSERSITE=1
            python3 -m plate_core.policy_runtime_verify --root "${trusted}" --require-provenance "${trusted}/src"
          ); then
            echo "::error title=policy-runtime::Default-branch policy runtime failed manifest/provenance verification."
            exit 1
          fi
          echo "PLATE_POLICY_PYTHONPATH=${trusted}/src" >> "${GITHUB_ENV}"
          echo "PLATE_POLICY_RUN_DIR=${RUNNER_TEMP}/plate-policy-exec-isolated" >> "${GITHUB_ENV}"
"""

POLICY_RUN_SHELL = """
          if [ -z "${PLATE_POLICY_PYTHONPATH:-}" ]; then
            echo "::error title=policy-runtime::PLATE_POLICY_PYTHONPATH unset; trusted prepare step must succeed before branch-policy gates."
            exit 1
          fi
          _policy_run_dir="${PLATE_POLICY_RUN_DIR:-${RUNNER_TEMP}/plate-policy-exec-isolated}"
          mkdir -p "${_policy_run_dir}"
          run_policy_module() {
            (
              cd "${_policy_run_dir}"
              export PYTHONPATH="${PLATE_POLICY_PYTHONPATH}"
              export PYTHONNOUSERSITE=1
              python3 "$@"
            )
          }
"""

VALIDATE_PLATE = """
      - name: Gate — validate release PR
        if: steps.release_gate_detect.outputs.run == 'true'
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
        if: steps.release_gate_detect.outputs.run == 'true'
        env:
          BASE_SHA: ${{ steps.release_gate_detect.outputs.base_sha }}
          HEAD_SHA: ${{ steps.release_gate_detect.outputs.head_sha }}
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

MAIN_SOURCE_PLATE = """
      - name: Gate — main source
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: main-source
          set -euo pipefail
@@POLICY_RUN_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          head_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .head.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          run_policy_module -m plate_core.pr_main_source_gate --base "${base_ref}" --head "${head_ref}" --labels "${labels}"
"""

RELEASE_WINDOW_PLATE = """
      - name: Gate — release window
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GITHUB_REPOSITORY: ${{ github.repository }}
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: release-window
          set -euo pipefail
@@POLICY_RUN_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          run_policy_module -m plate_core.pr_release_window_gate --base "${base_ref}" --labels "${labels}"
"""

PLATE_CORE_ENSURE_SHELL = """
          ensure_plate_core() {
            if [ -n "${PLATE_POLICY_PYTHONPATH:-}" ]; then
              export PYTHONPATH="${PLATE_POLICY_PYTHONPATH}"
              return 0
            fi
            echo "::error title=plate-core required::PLATE_POLICY_PYTHONPATH unset; trusted prepare step must archive default-branch src/plate_core (PyPI plate-core==@@PLATE_CORE_VERSION@@ alone is insufficient)."
            exit 1
          }
"""

MAIN_SOURCE_TEMPLATE = """
      - name: Gate — main source
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: main-source
          set -euo pipefail
@@PLATE_CORE_ENSURE_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          head_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .head.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          ensure_plate_core
@@POLICY_RUN_SHELL@@
          run_policy_module -m plate_core.pr_main_source_gate --base "${base_ref}" --head "${head_ref}" --labels "${labels}"
"""

INTEGRATION_BASE_PLATE = """
      - name: Gate — integration base
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: integration-base
          set -euo pipefail
@@POLICY_RUN_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          head_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .head.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          body="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .body)"
          run_policy_module -m plate_core.pr_integration_base_gate \
            --base "${base_ref}" \
            --head "${head_ref}" \
            --labels "${labels}" \
            --body "${body}" \
            --repo "${GITHUB_REPOSITORY}" \
            --pr-number "${pr_number}"
"""

INTEGRATION_BASE_TEMPLATE = """
      - name: Gate — integration base
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: integration-base
          set -euo pipefail
@@PLATE_CORE_ENSURE_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          head_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .head.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          body="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .body)"
          ensure_plate_core
@@POLICY_RUN_SHELL@@
          run_policy_module -m plate_core.pr_integration_base_gate \
            --base "${base_ref}" \
            --head "${head_ref}" \
            --labels "${labels}" \
            --body "${body}" \
            --repo "${GITHUB_REPOSITORY}" \
            --pr-number "${pr_number}"
"""

RELEASE_WINDOW_TEMPLATE = """
      - name: Gate — release window
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GITHUB_REPOSITORY: ${{ github.repository }}
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: release-window
          set -euo pipefail
@@PLATE_CORE_ENSURE_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          base_ref="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .base.ref)"
          labels="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq '[.labels[].name] | join(",")')"
          ensure_plate_core
@@POLICY_RUN_SHELL@@
          run_policy_module -m plate_core.pr_release_window_gate --base "${base_ref}" --labels "${labels}" --repo "${GITHUB_REPOSITORY}"
"""

REVIEWER_MODEL_PLATE = """
      - name: Gate — reviewer model
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: Reviewer model must differ from author model
          set -euo pipefail
@@POLICY_RUN_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          body="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .body)"
          printf '%s' "${body}" | run_policy_module -m plate_core.pr_reviewer_model_gate --stdin
"""

REVIEWER_MODEL_TEMPLATE = """
      - name: Gate — reviewer model
        if: |
          github.event_name == 'pull_request' ||
          github.event_name == 'pull_request_review' ||
          github.event_name == 'pull_request_review_comment'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # pr-gates failure marker: Reviewer model must differ from author model
          set -euo pipefail
@@PLATE_CORE_ENSURE_SHELL@@
          pr_number="${{ github.event.pull_request.number }}"
          body="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}" --jq .body)"
          ensure_plate_core
@@POLICY_RUN_SHELL@@
          printf '%s' "${body}" | run_policy_module -m plate_core.pr_reviewer_model_gate --stdin
"""

MARK_IMPLEMENTED_PLATE = """
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
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Mark implemented + auto-close linked issues (integration merge)
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          export PYTHONPATH="${GITHUB_WORKSPACE}/src"
          python3 -m plate_core.gh_actions_mark_implemented
"""

MARK_IMPLEMENTED_TEMPLATE = """
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
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Mark implemented + auto-close linked issues (integration merge)
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          run_mark_implemented() {
            export PYTHONPATH="${GITHUB_WORKSPACE}/src"
            python3 -m plate_core.gh_actions_mark_implemented
          }
          if [ -d "${GITHUB_WORKSPACE}/src/plate_core" ]; then
            run_mark_implemented
          elif python3 -c "import plate_core.gh_actions_mark_implemented" 2>/dev/null; then
            run_mark_implemented
          else
            python3 -m pip install --quiet --disable-pip-version-check "plate-core==@@PLATE_CORE_VERSION@@" || true
            if python3 -c "import plate_core.gh_actions_mark_implemented" 2>/dev/null; then
              run_mark_implemented
            else
              echo "::warning title=Integration merge (warn-only)::plate-core runtime unavailable; skipping mark-implemented until plate-core is installed."
            fi
          fi
"""


def build(variant: str) -> str:
    gates_src = ROOT / ".github/workflows/plate-pr-gates.yml"
    title_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — PR title")
    )
    issue_link_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — issue links")
    )
    feature_labels_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — Feature release fragment (labels)")
    )
    feature_fragment_script = _yaml_script(
        _extract_script_block(
            gates_src,
            "Gate — Feature release fragment\n        if: |\n          (github.event_name == 'pull_request' ||\n           github.event_name == 'pull_request_review' ||\n           github.event_name == 'pull_request_review_comment') &&\n          steps.feature_labels.outputs.is_feature == 'true'",
        )
    )
    release_detect_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — validate release PR (detect)")
    )
    feedback_script = _yaml_script(
        _extract_script_block(gates_src, "Gate — feedback resolution")
    )
    validate_run = VALIDATE_PLATE if variant == "plate" else VALIDATE_TEMPLATE
    plate_ver = _plate_core_pip_version()
    ensure_shell = PLATE_CORE_ENSURE_SHELL.replace("@@PLATE_CORE_VERSION@@", plate_ver)
    policy_run = POLICY_RUN_SHELL.rstrip()

    def _tpl(block: str) -> str:
        return (
            block.replace("@@PLATE_CORE_VERSION@@", plate_ver)
            .replace("@@PLATE_CORE_ENSURE_SHELL@@", ensure_shell.rstrip())
            .replace("@@POLICY_RUN_SHELL@@", policy_run)
        )

    plate_policy_run = policy_run

    def _plate(block: str) -> str:
        return block.replace("@@POLICY_RUN_SHELL@@", plate_policy_run)

    main_source_run = (
        (
            _plate(MAIN_SOURCE_PLATE)
            + _plate(INTEGRATION_BASE_PLATE)
            + _plate(RELEASE_WINDOW_PLATE)
        )
        if variant == "plate"
        else _tpl(MAIN_SOURCE_TEMPLATE + INTEGRATION_BASE_TEMPLATE + RELEASE_WINDOW_TEMPLATE)
    )
    reviewer_run = (
        _plate(REVIEWER_MODEL_PLATE) if variant == "plate" else _tpl(REVIEWER_MODEL_TEMPLATE)
    )
    trusted_prep = TRUSTED_RUNTIME_PREP.lstrip("\n").rstrip() + "\n"
    body = HEADER.replace("@@TRUSTED_RUNTIME_PREP@@", trusted_prep)
    body = body.replace("@@TITLE_SCRIPT@@", title_script)
    body = body.replace("@@ISSUE_LINK_SCRIPT@@", issue_link_script)
    body = body.replace("@@MAIN_SOURCE_RUN@@", main_source_run.lstrip("\n").rstrip())
    body = body.replace("@@REVIEWER_MODEL_RUN@@", reviewer_run.lstrip("\n").rstrip())
    body = body.replace("@@FEATURE_LABELS_SCRIPT@@", feature_labels_script)
    body = body.replace("@@FEATURE_FRAGMENT_SCRIPT@@", feature_fragment_script)
    body = body.replace("@@RELEASE_DETECT_SCRIPT@@", release_detect_script)
    body = body.replace("@@FEEDBACK_SCRIPT@@", feedback_script)
    body = body.replace(
        "@@VALIDATE_RELEASE_RUN@@", validate_run.lstrip("\n").rstrip() + "\n"
    )
    if variant == "plate":
        body += MARK_IMPLEMENTED_PLATE
    else:
        body += MARK_IMPLEMENTED_TEMPLATE.replace(
            "@@PLATE_CORE_VERSION@@", _plate_core_pip_version()
        )
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
