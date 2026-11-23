#!/usr/bin/env python3
"""Generate plates-on-issue-closed.yml for plate repo and template payload (#1472)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from plate_core.issue_closed_usage import workflow_github_script  # noqa: E402
from plate_core.workflow_runs_on import LINUX_RUNS_ON_VAR_EXPRESSION  # noqa: E402


def _yaml_script(script: str) -> str:
    indented = "".join(f"            {line}\n" for line in script.splitlines())
    return f"          script: |\n{indented}"


def build(*, github_script_version: str) -> str:
    extract_script = workflow_github_script()
    version = github_script_version
    extract_yaml = _yaml_script(extract_script)
    return (
        """name: PLATES Usage Report on Issue Closed

on:
  issues:
    types: [closed]

# One in-flight harvest per issue; parallel closes on different issues stay queued (#1480).
concurrency:
  group: plates-on-issue-closed-${{ github.repository }}-${{ github.event.issue.number }}
  cancel-in-progress: false

permissions:
  contents: read
  issues: write

jobs:
  capture-usage-report:
    if: |
      github.event.issue != null && !github.event.issue.pull_request && (
        contains(format(',{0},', join(github.event.issue.labels.*.name, ',')), ',Feature,') ||
        contains(format(',{0},', join(github.event.issue.labels.*.name, ',')), ',Question,')
      )
    runs-on: """
        + LINUX_RUNS_ON_VAR_EXPRESSION
        + """
    steps:
      - name: Extract trusted usage report from closing comment
        id: usage
        uses: actions/github-script@"""
        + version
        + """
        with:
"""
        + extract_yaml
        + """      - name: Record validated cost row on issue (no default-branch push)
        if: steps.usage.outputs.has_report == 'true' && steps.usage.outputs.already_recorded != 'true'
        uses: actions/github-script@"""
        + version
        + """
        env:
          RECORD_BODY: ${{ steps.usage.outputs.record_body }}
        with:
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              body: process.env.RECORD_BODY
            });

      - name: Optionally post to dashboard issue
        if: steps.usage.outputs.has_report == 'true' && vars.PLATE_COST_DASHBOARD_ISSUE != ''
        uses: actions/github-script@"""
        + version
        + """
        env:
          DASHBOARD_ISSUE: ${{ vars.PLATE_COST_DASHBOARD_ISSUE }}
          TOKENS: ${{ steps.usage.outputs.tokens }}
          COST: ${{ steps.usage.outputs.cost }}
          DURATION: ${{ steps.usage.outputs.duration }}
          COMMENT_URL: ${{ steps.usage.outputs.comment_url }}
        with:
          script: |
            const dashboardIssue = Number(process.env.DASHBOARD_ISSUE);
            if (!Number.isInteger(dashboardIssue) || dashboardIssue <= 0) {
              core.warning('PLATE_COST_DASHBOARD_ISSUE is set but not a valid issue number.');
              return;
            }

            const body = [
              `Usage recorded from issue #${context.payload.issue.number}:`,
              '',
              `- Tokens: ${process.env.TOKENS}`,
              `- Cost: ${process.env.COST}`,
              `- Duration: ${process.env.DURATION}`,
              `- Source: ${process.env.COMMENT_URL}`
            ].join('\\n');

            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: dashboardIssue,
              body
            });
"""
    )


def main() -> None:
    repo_path = ROOT / ".github" / "workflows" / "plates-on-issue-closed.yml"
    payload_path = (
        ROOT
        / "src"
        / "plate_core"
        / "template_payload"
        / ".github"
        / "workflows"
        / "plates-on-issue-closed.yml"
    )
    repo_path.write_text(build(github_script_version="v8"), encoding="utf-8")
    payload_path.write_text(build(github_script_version="v7"), encoding="utf-8")
    print(f"wrote {repo_path}")
    print(f"wrote {payload_path}")


if __name__ == "__main__":
    main()