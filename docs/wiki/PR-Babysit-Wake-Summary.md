# PR babysit wake summary (#1080)

When `gh plate pr babysit --watch` wakes on new activity, agents should act on the **wake summary** only. The summary is built from REST deltas plus lightweight fields (`head_sha`, `mergeable_state`, `ci_state`) — not a full GraphQL PR reload.

## On wake

1. Read `render_wake_summary(...)` output (or the structured dict from `build_wake_summary`).
2. If `is_actionable(summary)` is false, skip work for this tick.
3. Address new human review comments, reviews, and issue comments listed in the summary.
4. React to CI and merge-state transitions shown in the summary.
5. When the summary reports a new `head_commit`, assume the branch moved; re-run only the checks you need for that change.

## Do not reload full PR state by default

Avoid calling `_load_pr_data` / full babysit GraphQL on every poll. Use the summary unless you need detail the delta cannot provide, for example:

- Merge conflicts or ambiguous `mergeable_state` (`dirty`, `unknown`) that require line-level conflict inspection.
- A review comment excerpt is insufficient and you must fetch the full thread.

## Filtering

The builder drops known bot/agent authors, `ignore_logins`, and any body containing either trigger marker (`<!-- plate-pr-babysit -->` or `<!-- plate-pr-merge-trigger -->`) from issue-comment chatter. Review comments and formal reviews are retained according to the configured review scope (default `all`). Rendered comment excerpts flatten whitespace, and summaries preserve state transitions while shortening or identifying omitted comment content within the byte budget.

## API

- `build_wake_summary(delta, prev, cur, *, ignore_logins=frozenset(), review_scope=None, agent_logins=None) -> dict`
- `render_wake_summary(summary) -> str`
- `is_actionable(summary) -> bool`

Implemented in `plate_core.pr_watch_summary`.

## How the watcher uses this

Each `gh plate pr babysit --watch` tick loads persisted probe state, calls `probe_pr` (conditional GET on the pull request), and treats `304 Not Modified` or an unchanged snapshot as a quiet tick: no `babysit_pr`, no `record_wake`, and exponential backoff via `Backoff.next_interval(False)`.

On the first tick (no saved probe file), the loop always runs one full `babysit_pr` for a baseline, then saves probe state and continues probing.

When the probe reports a change, the watcher calls `fetch_delta`, builds a wake summary with `build_wake_summary`, and runs `babysit_pr` only when `is_actionable(summary)` is true (printing `render_wake_summary` unless `--json`). Non-actionable deltas (for example bot-only issue comments) are quiet ticks. Optional `--full-every N` forces a full babysit every N ticks as a safety net.

Merged or closed pull requests stop the loop when `should_stop` sees a `200` probe body; `304` skips that check because terminal states always change `updated_at`.
