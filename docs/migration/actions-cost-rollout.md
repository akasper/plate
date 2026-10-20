# Rolling out PLATE Actions cost controls to private adopters

This note supports rolling out workflow changes that reduce GitHub Actions minutes and Copilot spend (issue-event guards, `PLATE_COPILOT_AUTOSTART`, PR concurrency, push-to-`main` only for Pages/E2E) from `akasper/plate` into private repositories that copied the PLATE template.

## How adopters receive the update

1. **Upgrade path (preferred):** From the adopter repo, run `gh plate import-payload` (or your established `gh plate bootstrap` / upgrade procedure) after pinning to a `plate-core` release that includes these workflow changes. Review the diff under `.github/workflows/` before merge.
2. **Manual path:** Cherry-pick or copy the updated workflow YAML from `src/plate_core/template_payload/.github/workflows/` in the PLATE repo into the adopter's `.github/workflows/`, preserving any local customizations.

## What to verify after import

| Check | Why |
|---|---|
| Issue workflows still enforce labels/milestones | `label-check.yml` behavior must remain intact |
| Feature kickoff still works | `status:ready-to-work` on a `Feature` issue should comment or dispatch orchestrator |
| Copilot is off by default | Do **not** set `PLATE_COPILOT_AUTOSTART` until you intend to pay for agent wakes |
| PR gates unchanged | `ci`, `pr-issue-link-check`, `pr-title-check`, `feedback-resolution-check`, `auto-merge` still required in branch protection |
| Release/publish not cancelled mid-flight | `release.yml` and publish workflows use `cancel-in-progress: false` |

Optional: set repository variable `PLATE_COPILOT_AUTOSTART=true` only on repos that explicitly want automatic `@copilot` kickoff comments and Copilot coding-agent assignment from platform monitor.

## Suggested rollout order (highest burn first)

Prioritize repos with the heaviest issue and PR event volume (typical private PLATE adopters):

1. **u.ai** — high issue/PR churn; import workflow guards first.
2. **smakks_revenge**
3. **PaperTiger**
4. **AlpacaAgent / Tradespeak**
5. **the-happyhouses**
6. **bugflow-clone / Kittyflow**
7. Remaining private forks that copied PLATE workflows

For each repo:

1. Open a Documentation or Feature PR with the imported workflows (no need to touch application code).
2. Watch Actions usage for 48–72 hours; confirm minute count drops on issue label/edit noise.
3. Enable `PLATE_COPILOT_AUTOSTART=true` only if automatic agent kickoff is desired.

## Related PLATE artifacts

- Migration fragment: `.agentic/releases/unreleased/actions-cost-controls.json`
- Operator guidance: `AGENTS.md` (Copilot review and Actions cost sections)
- Epic context: Copilot triage and wake gating (#1136, #1137 under Epic #1129)
