# Github Actions And Copilot

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## GitHub Actions and Copilot cost controls

PLATE template workflows avoid billing a full Actions minute for issue and comment events that do no work. Issue-triggered workflows use narrow `on:` types where safe and **job-level `if:`** guards so irrelevant events skip starting a runner. PR workflows use **concurrency** (`cancel-in-progress: true`) so rapid pushes do not stack redundant runs; **release** and **publish** workflows keep `cancel-in-progress: false` so packaging is not interrupted.

Automatic **Copilot coding-agent** kickoff (`@copilot start` comments, legacy feedback auto-triggers in adopters, platform-monitor assignment) is **opt-in** via repository variable `PLATE_COPILOT_AUTOSTART=true`. When unset or not `true`, kickoff comments are posted without `@copilot` mentions.

Downstream rollout for private adopters: `docs/migration/actions-cost-rollout.md`.

## Copilot code review (human and agent policy)

Nothing in this repository should **auto-request Copilot code review on every push**. Do **not** request Copilot review by default; use a local model or other first-pass review for routine PR work. Request Copilot review **once per PR when a human explicitly asks** (or when labels, scope, and gates are satisfied and a human has chosen Copilot for that PR). Request **re-review only when a human or process explicitly asks**—not on each `synchronize` event. This pairs with babysit guidance (#496), default `local-rebase` branch sync (#1300), and triage/wake work tracked in #1136 and #1137 (Epic #1129).

Agents must not loop `request review` / `@copilot` review triggers to chase green CI; work existing review threads first (`gh plate pr babysit`, `plate_resolve_review_thread`). Use `--branch-update-strategy copilot-request` only when a human opts into paid Copilot merge assistance.
