# Autonomous Mode

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Autonomous Mode

Autonomous mode is the default operating posture for unattended sessions (overnight runs, long-running autopilot via `/loop` or scheduler, `/delegate` tasks) where no human reviewer is available interactively. It is driven by `.plate` config rather than a marker file.

**Configuration (single source of truth):** Use the `autonomy` section in `.plate`:

- `risk_tolerance`: `"off"` (fully manual), `"low"`, `"medium"`, or `"high"`. Higher tolerance enables broader autonomous progress (e.g., auto-merge up to that risk level). `risk:critical` is never auto-merge eligible.
- `enabled`, `token_budget`, `schedules_enabled`, `pr_review_scope`, etc.
- Legacy `.github/AUTONOMOUS_MODE` is supported only when `.plate` has **no** `autonomy` section (marker implies low tolerance with a migration warning). When `autonomy` is present, it is authoritative; delete the marker after configuring `.plate`.

**When autonomous mode is active (`enabled: true` and `risk_tolerance` not `off`):**

| Rule | Normal Mode | Autonomous Mode |
|---|---|---|
| Agent may merge own PRs | Never | Permitted for eligible PRs per tolerance |
| Must wait for human merge | Always | May call `gh pr merge --auto --squash` on eligible PRs |
| May add `auto-merge` label | No | Yes, for eligible PRs |

**Eligibility criteria — all must be true for a PR to qualify:**

- Effective risk (exactly one `risk:*` label) is allowed by configured tolerance (e.g., `risk:low` only when tolerance is `low`)
- Does not modify `AGENTS.md`, `SPEC.md`, `.github/CODEOWNERS`, `.plate`, or any workflow file
- Does not carry `need:human-review` or `need:security-review`
- Does not change public-facing claims in `README.md`
- The `auto-merge` label was applied by a trusted bot or a collaborator with write access

**How to auto-merge an eligible PR in autonomous mode:**

```bash
# First: gh plate release status  (discover --base: release or release-*)
gh pr create --base <base> --label "risk:low" --label "auto-merge" [other required labels] ...
gh pr merge --auto --squash <PR_NUMBER>
```

For `Feedback Response` PRs, `.github/workflows/auto-label-feedback-responses.yml` may apply `risk:low` and `auto-merge` when policy allows.

The `.github/workflows/auto-merge.yml` workflow triggers on the `auto-merge` label and enforces these gates before calling `gh pr merge --auto --squash`.

**GitHub settings required** (one-time per repository):

```bash
# Allow the repo to use auto-merge
gh api -X PATCH repos/OWNER/REPO -f allow_auto_merge=true

# Allow Actions to write PRs (contents read is sufficient for the eligibility check)
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false
```

**Security posture:** Autonomous mode intentionally cannot self-escalate. Agents may not relax branch protection rules or modify the eligibility criteria. Use `risk_tolerance: "off"` or `enabled: false` for full manual control.