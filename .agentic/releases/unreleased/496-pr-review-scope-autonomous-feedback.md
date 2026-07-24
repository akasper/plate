---
slug: 496-pr-review-scope-autonomous-feedback
change_type: feature
surface: gh-plate
summary: >
  Configurable PR review response scope (all|bot-only|human-only) so babysit treats
  Copilot and human threads as actionable by default, with suggestion metadata and
  high-risk path guards. Closes #496.
links:
  - https://github.com/akasper/plate/issues/496
---

# Fully autonomous PR review responses (#496)

## What changed
- `.plate` `autonomy.pr_review_scope` (default `all`) + validation
- Expanded bot patterns (Copilot, Dependabot, `[bot]`, …)
- `gh plate pr babysit --scope` and MCP `scope` on plate_pr_babysit / plate_get_actionable_review_threads
- Suggestion fence detection + prefer_apply / high-risk path flags on actionable threads
- BabysitReport fields: pr_review_scope, threads_with_suggestions, summaries
- Trigger comment + AGENTS babysit step for #496

## Downstream
- Default scope `all` may surface more actionable threads than older bot-only filtering.
- Conservative repos: set `autonomy.pr_review_scope: bot-only` in `.plate`.
