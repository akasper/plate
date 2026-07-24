---
slug: 605-auto-resolve-outdated-review-threads
change_type: fix
surface: gh-plate
summary: >
  gh plate pr babysit --act now auto-resolves outdated unresolved review threads
  so the feedback-resolution gate can pass after code fixes without a separate
  plate_resolve_review_thread pass (closes #605). Also restores truncated AGENTS.md.
links:
  - https://github.com/akasper/plate/issues/605
---

# Auto-resolve outdated review threads during babysit (#605)

## What changed
- `babysit_pr(act=True)` resolves unresolved+outdated review threads via GraphQL.
- BabysitReport gains `auto_resolved_threads`, `auto_resolved_thread_ids`, `auto_resolve_errors`.
- CLI prints auto-resolve counts.
- Tests cover extract + act path; FakeClient dispatches resolve vs load GraphQL.
- Restored full AGENTS.md (was accidentally truncated to 34 lines with a placeholder).

## Downstream impact
Agents running `gh plate pr babysit --act` after addressing feedback no longer need a manual
resolve pass for outdated threads. Non-outdated threads still require explicit resolve or code address.

## Follow-up (PR babysit / CI green)
- Silence pip auto-install stdout in `gh-plate` so `--json` stays parseable.
- E2E: set PYTHONPATH to in-tree `src` (CI + catalog-discovery runGhPlate) and tolerate non-JSON prefixes when parsing.
