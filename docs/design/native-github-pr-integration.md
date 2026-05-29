# Native GitHub PR Integration — Design Spec

- **Issue:** #100
- **Designed by:** @copilot
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

PLATE still relies on custom `Epic: short-name` labels and PR-body-only linking guidance even though GitHub already provides Milestones, Development sidebar issue links, and automatic branch deletion on merge. That creates extra maintenance burden and weakens native GitHub traceability.

## Constraints

- Keep changes lightweight and repository-local.
- Preserve existing required issue and PR type labels.
- Prefer native GitHub features over new bots or heavy automation.
- Leave an explicit escape hatch for repositories that should not auto-delete merged branches.

## Design Decision

Milestones are the canonical Epic container. New Epic work should be represented by a GitHub milestone, and any issue or pull request that belongs to that Epic should use the same milestone.

`Feature`, `Bug`, and issue-driven `Documentation` PRs must link at least one issue. Closing keywords remain the preferred path when merge should close the issue; Development sidebar links are acceptable when the issue should stay open after the PR lands.

Delete branch on merge is the PLATE bootstrap default. Repositories may opt out during bootstrap, but the default posture is on.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Keep `Epic: short-name` labels as the canonical Epic identifier | Duplicates native milestone behavior and keeps extra routing metadata alive without enough value. |
| Require closing keywords only | Prevents valid Development sidebar links for work that should remain open after merge. |
| Leave delete-branch-on-merge as an explicit opt-in flag | Misses the desired default for clean repositories and makes the safer default easier to forget. |

## Artifact

- `AGENTS.md` and `.agentic/process.yml` define milestones as the Epic source of truth.
- `.github/workflows/label-check.yml` requires milestones for Feature and Epic issues.
- `.github/workflows/pr-issue-link-check.yml` accepts Development sidebar links in addition to closing keywords.
- `scripts/bootstrap_github.sh` and `scripts/BootstrapGitHub.ps1` enable Delete branch on merge by default, with skip flags for exceptions.

## Open Questions

- Whether legacy `Epic` issues should remain common practice or become rare companion artifacts beside milestones.
- Whether downstream PLATE repositories should eventually delete legacy `Epic:` labels after migration.

## Acceptance Evidence

- Feature intake guidance asks for Epic milestones instead of `Epic:` labels.
- PR guidance explains both closing-keyword and Development sidebar link paths.
- Bootstrap docs and scripts default to Delete branch on merge while keeping a clear override.
