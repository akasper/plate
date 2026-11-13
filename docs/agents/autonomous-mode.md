# Autonomous Mode

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Autonomous Mode

Autonomous mode is the default operating posture for unattended sessions (overnight runs, long-running autopilot via `/loop` or scheduler, `/delegate` tasks) where no human reviewer is available interactively. It is driven by `.plate` config (see Epic #470) rather than a marker file. The engine (AutonomyEngine) introspects state and delegates/executes at the user's budgeted token rate and chosen `risk_tolerance` (off/low/medium/high), with scheduled/recurring procedures (`.agentic/procedures/`) for audits, drift detection, feedback integration, etc.

**Configuration (single source of truth):** Use the `autonomy` section in `.plate` (added in #473, engine in #474):
- `risk_tolerance`: "off" (fully manual), "low", "medium", or "high". Higher tolerance enables broader autonomous progress (e.g., auto-merge up to that risk level, apply-mode for procedures/audits, auto-stub generation in planning).
- `enabled`, `token_budget` (daily/per_cycle/action: throttle|pause|warn), `schedules_enabled`, `pr_review_scope` (#496), etc.
- Legacy `.github/AUTONOMOUS_MODE` (file presence) is supported for transition/compat but is sunset in favor of `.plate` (generalized in #476 PR; health/config surfaces emit migration guidance). Delete the marker file after configuring `.plate`.

**Agent routing for autonomy loops (#480):** When PLATE signals are present, the **plate** persona prefers AutonomyEngine thin surfaces for long-running work:
1. `plate_what_next` for the next *process* step (still first for ordinary "what should I do?").
2. `plate_autonomy_status` / `gh plate autonomy --status` **before** unsupervised cycles — honor risk, budget, due procedures.
3. `plate_autonomy_run_cycle` / `gh plate autonomy --run|--loop` (dry-run first when risk unknown); procedures via list/run tools.
4. Quiet rules: terminal = terse bullets only; GitHub comments only on progress or exempt markers (`PLATE-AUTONOMY-CYCLE`, `PLATE-PROCEDURE-RUN`, USAGE REPORT). Full protocol: `autonomy_loops` in `agent_guidance.py` + catalog skill `run-autonomy-cycle`.

**When autonomous mode is active (risk_tolerance != "off" and enabled):**

| Rule | Normal Mode | Autonomous Mode |
|---|---|---|
| Agent may merge own PRs | Never | Permitted for eligible `risk:low` (or higher per tolerance) PRs only |
| Must wait for human merge | Always | May call `gh pr merge --auto --squash` on eligible PRs |
| May add `auto-merge` label | No | Yes, for eligible PRs |

**Eligibility criteria — all must be true for a PR to qualify (generalized from legacy marker; see #476):**

- Effective risk (from label or config tolerance) allows it (e.g., `risk:low` for low tolerance; up to `risk:high` for high, never critical)
- Does not modify `AGENTS.md`, `SPEC.md`, `.github/CODEOWNERS`, or any workflow file
- Does not add, remove, or alter credential handling, payment logic, authentication, or security controls
- Does not carry `need:human-review` or `need:security-review`
- Does not change public-facing claims in `README.md` or marketing documentation
- Feedback-resolution check passes; base in sync (babysit handles via copilot-request/local-rebase/none)
- For Bug/Feature/Hardening/Documentation PRs: human review/approval is obtained (per the explicit requirement clarified in this fix; the check is separate from feedback-resolution for agent threads)

**How to auto-merge an eligible PR in autonomous mode:**

```bash
# First: gh plate release status  (to learn the correct --base: release or release-*)
gh pr create --base <base> --label "risk:low" --label "auto-merge" [other required labels] ...
gh pr merge --auto --squash <PR_NUMBER>
```

The `.github/workflows/auto-merge.yml` workflow triggers on `auto-merge` label and checks `.plate` autonomy.risk_tolerance (with legacy AUTONOMOUS_MODE fallback) — providing the gate (generalized in #487).

**GitHub settings required** (one-time per repository):

```bash
# Allow the repo to use auto-merge
gh api -X PATCH repos/OWNER/REPO -f allow_auto_merge=true

# Allow Actions to write PRs and contents (needed by the workflow)
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false
```

**Security posture:** Autonomous mode intentionally cannot self-escalate. An agent operating autonomously may not bypass `.plate` autonomy config (or create/modify/delete legacy `.github/AUTONOMOUS_MODE` during transition), and may not relax branch protection rules or modify the eligibility criteria. Use `risk:off` or remove permissive config for full manual control. The AutonomyEngine enforces budgets, risk, and quiet rules (terse bullets in loops; see quiet_operations guidance added in #480).

See `docs/design/autonomous-plate-engine.md`, the autonomy fragment in `.agentic/releases/unreleased/`, Epic #470 (and children #471–482), and the generalized auto-merge/babysit PRs for full details. The engine + scheduled procedures enable the "very long time" budgeted autonomous operation that is the heart of the PLATE vision.
