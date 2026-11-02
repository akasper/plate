# Autonomous Mode

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Autonomous Mode

Autonomous mode is an opt-in operating posture for unattended sessions (overnight runs, long-running autopilot, `/delegate` tasks) where no human reviewer is available interactively. It selectively lifts the self-merge prohibition for lightweight, low-risk PRs.

**Toggle:** Create `.github/AUTONOMOUS_MODE` on the default branch to enable. Delete it to return to normal human-in-the-loop operation. The file content is ignored; its presence is the signal.

**When autonomous mode is active:**

| Rule | Normal Mode | Autonomous Mode |
|---|---|---|
| Agent may merge own PRs | Never | Permitted for eligible `risk:low` PRs only |
| Must wait for human merge | Always | May call `gh pr merge --auto --squash` on eligible PRs |
| May add `auto-merge` label | No | Yes, for eligible PRs |

**Eligibility criteria — all must be true for a PR to qualify:**

- Labeled `risk:low` (see §Risk Assessment and Labeling above)
- Does not modify `AGENTS.md`, `SPEC.md`, `.github/CODEOWNERS`, or any workflow file
- Does not add, remove, or alter credential handling, payment logic, authentication, or security controls
- Does not carry `need:human-review` or `need:security-review`
- Does not change public-facing claims in `README.md` or marketing documentation

**How to auto-merge an eligible PR in autonomous mode:**

```bash
# First: gh plate release status  (discover --base: release or release-*)
gh pr create --base <base> --label "risk:low" --label "auto-merge" [other required labels] ...
gh pr merge --auto --squash <PR_NUMBER>
```

For `Feedback Response` PRs, the `.github/workflows/auto-label-feedback-responses.yml` workflow applies both `risk:low` and `auto-merge` labels automatically, so the above workflow call is sufficient.

The `.github/workflows/auto-merge.yml` workflow also triggers on the `auto-merge` label and verifies the marker file before proceeding — providing a second gate.

**GitHub settings required** (one-time per repository):

```bash
# Allow the repo to use auto-merge
gh api -X PATCH repos/OWNER/REPO -f allow_auto_merge=true

# Allow Actions to write PRs and contents (needed by the workflow)
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false
```

**Security posture:** Autonomous mode intentionally cannot self-escalate. An agent operating in autonomous mode may not create, modify, or delete `.github/AUTONOMOUS_MODE` itself, and may not relax branch protection rules or modify the eligibility criteria in this file.
