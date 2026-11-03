# Github Actions And Copilot

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## GitHub Actions and Copilot cost controls

PLATE template workflows avoid billing a full Actions minute for issue and comment events that do no work. Issue-triggered workflows use narrow `on:` types where safe and **job-level `if:`** guards so irrelevant events skip starting a runner. PR workflows use **concurrency** (`cancel-in-progress: true`) so rapid pushes do not stack redundant runs; **release** and **publish** workflows keep `cancel-in-progress: false` so packaging is not interrupted.

Automatic **Copilot coding-agent** kickoff (`@copilot start` comments, legacy feedback auto-triggers in adopters, platform-monitor assignment) is **opt-in** via repository variable `PLATE_COPILOT_AUTOSTART=true`. When unset or not `true`, kickoff comments are posted without `@copilot` mentions.

Downstream rollout for private adopters: `docs/migration/actions-cost-rollout.md`.

## Copilot code review (human and agent policy)

Nothing in this repository should **auto-request Copilot code review on every push**. Do **not** request Copilot review by default; use a local model or other first-pass review for routine PR work. Request Copilot review **once per PR when a human explicitly asks** (or when labels, scope, and gates are satisfied and a human has chosen Copilot for that PR). Request **re-review only when a human or process explicitly asks**—not on each `synchronize` event. This pairs with babysit guidance (#496), default `local-rebase` branch sync (#1300), and triage/wake work tracked in #1136 and #1137 (Epic #1129).

Agents must not loop `request review` / `@copilot` review triggers to chase green CI; work existing review threads first (`gh plate pr babysit`, `plate_resolve_review_thread`). Use `--branch-update-strategy copilot-request` only when a human opts into paid Copilot merge assistance.

## Copilot review effort (PLATE default: Lite)

GitHub’s built-in default Copilot review effort is **Balanced**, which uses more AI credits than **Lite**. PLATE repos should set the repository **Review effort level** to **Lite** for routine PR work (Settings → Copilot → Code review). Organization owners should set an org default of Lite when repositories inherit org policy. See [Configuring code review by GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review).

For pull requests labeled `risk:high` or `risk:critical`, a human may request Copilot review at **Balanced** (per review in the PR Reviewers menu) when deeper analysis is worth the spend. Do not leave the repository default on Balanced for all PRs.

**Verification:** `gh plate health` and `gh plate adopt --json` (optional checks) report `copilot_review_effort_*` when the GitHub API exposes the repository setting. When the API is unreadable, follow the manual step in the tool output and confirm Lite in repository settings.
