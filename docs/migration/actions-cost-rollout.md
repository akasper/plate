# Rolling out PLATE Actions cost controls to private adopters

This note supports rolling out workflow changes that reduce GitHub Actions minutes and Copilot spend (issue-event guards, `PLATE_COPILOT_AUTOSTART`, PR concurrency, push-to-`main` only for Pages/E2E) from `akasper/plate` into private repositories that copied the PLATE template.

**Also treat `akasper/plate_template` as a source of copies.** That separate template repository still ships the pre-cost-control workflows, so new repos created from it inherit the old behavior. Apply the same workflow changes there **first or in parallel with `akasper/plate`**, or retire `plate_template` as the bootstrap source so it stops re-seeding expensive automation.

Account-level **Copilot auto-review** is a separate control: check [github.com/settings/copilot](https://github.com/settings/copilot) manually during rollout (independent of `PLATE_COPILOT_AUTOSTART`).

## How adopters receive the update

1. **Upgrade path (preferred):** From the adopter repo, run `gh plate import-payload` (or your established `gh plate bootstrap` / upgrade procedure) after pinning to a `plate-core` release that includes these workflow changes. Review the diff under `.github/workflows/` before merge.
2. **Manual path:** Cherry-pick or copy the updated workflow YAML from `src/plate_core/template_payload/.github/workflows/` in the PLATE repo into the adopter's `.github/workflows/`, preserving any local customizations.

## What to verify after import

| Check | Why |
|---|---|
| Issue workflows still enforce labels/milestones | `label-check.yml` behavior must remain intact |
| Feature kickoff still works | `status:ready-to-work` on a `Feature` issue should comment or dispatch orchestrator |
| Copilot is off by default | Do **not** set `PLATE_COPILOT_AUTOSTART` until you intend to pay for agent wakes |
| PR gates (merged #1209) | Replace separate gate contexts with **`pr-gates`** plus existing **`labels`** and **`test`**. Remove deprecated contexts: `check-pr-title`, `check-issue-links`, `feature-change-files`, `feedback-resolution`, `audit`, `validate-release-pr`. Run `gh plate health` to flag stale names. |
| Release/publish not cancelled mid-flight | `release.yml` and publish workflows use `cancel-in-progress: false` |

Optional: set repository variable `PLATE_COPILOT_AUTOSTART=true` only on repos that explicitly want automatic `@copilot` kickoff comments and Copilot coding-agent assignment from platform monitor.

### `discussion-monitoring.yml` (not in plate payload)

`.github/workflows/discussion-monitoring.yml` (with `@copilot` comments) is **not** in `akasper/plate`'s template payload but exists in **akasper/AlpacaAgent**, **akasper/sketchbook**, **akasper/flashbang.ai**, and **akasper/plate_template**. During rollout, each of those repos needs the `PLATE_COPILOT_AUTOSTART` gate added to that workflow locally, or the workflow removed—`gh plate import-payload` alone will not fix it.

## Suggested rollout order (highest burn first)

Prioritize repos with the heaviest issue and PR event volume (typical private PLATE adopters):

0. **akasper/plate_template** — update or retire before new repos copy stale workflows.
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

## Merged PR gates (#1209) — branch protection

After importing `plate-pr-gates.yml` and removing the legacy gate workflows, update default-branch protection **required status checks**:

| Remove (deprecated job contexts) | Add / keep |
|---|---|
| `check-pr-title`, `check-issue-links`, `feature-change-files`, `feedback-resolution`, `audit`, `validate-release-pr` | **`pr-gates`** (single merged job) |
| (unchanged) | **`labels`**, **`test`**, release/publish workflows as before |

`gh plate health` (and `plate_health` MCP) reports `stale_required_check_contexts` when deprecated names remain. Planned #1195 may add a separate **`ai-review`** required check; that is independent of `pr-gates`.

### Before / after job count (sample PR)

On a typical PR synchronize event, GitHub previously scheduled **six** billable gate jobs (`check-pr-title`, `check-issue-links`, `feature-change-files`, `feedback-resolution`, `audit`, and `validate-release-pr` when applicable), each incurring at least one billed minute. The merged workflow schedules **one** `pr-gates` job that runs the same gates sequentially (~one billed minute per workflow run, plus the separate `test` / `labels` workflows).

## Related PLATE artifacts

- Migration fragment: `.agentic/releases/unreleased/actions-cost-controls.json`
- Merged gates fragment: `.agentic/releases/unreleased/actions-pr-gates-merge.json`
- Operator guidance: `AGENTS.md` (Copilot review and Actions cost sections)
- Epic context: Copilot triage and wake gating (#1136, #1137 under Epic #1129)
