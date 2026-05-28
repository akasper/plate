# PR Integration Practices vs. Native GitHub Features

- **Issue:** #101 (child of Epic #100)
- **Researched by:** Autonomous agent (Grok)
- **Date:** 2026-05-28
- **Status:** Complete

## Research Question

Inventory current PLATE PR/Epic integration practices (custom labels, body-based closing keywords, Epic issues) against native GitHub capabilities (Milestones for Epics, linked issues in Development sidebar with auto-transition, repository-level delete branch on merge). Identify gaps against the three locked requirements from Epic #100 and produce a gap analysis + recommended minimal change set to feed the Design phase.

## Sources

- AGENTS.md (Label Rules, Issue Artifact Rules, PR creation, Research work loop, Epic readiness)
- `.github/workflows/pr-issue-link-check.yml` (full read)
- `.github/workflows/labels.yml` and related CI/label workflows (post #103 changes)
- `docs/bootstrap/new-repository-checklist.md` and bootstrap scripts (`scripts/bootstrap_github.sh`, `BootstrapGitHub.ps1`)
- `src/plate_core/epics.py` + `tests/test_epics.py` and the new `tests/test_epic89_*.py` suite (from #113)
- `docs/wiki/Automatic-Epic-Creation.md` and `docs/research/automatic-epic-creation.md`
- GitHub API queries (open Epics #89, #100, #112, repo settings for delete_branch_on_merge and milestones)
- Planning session artifacts and PLATE_SESSION_STATE in Epic #100 body
- Existing research docs for format reference (`docs/research/stack-selection.md`, `docs/research/automatic-epic-creation.md`)
- `docs/research/README.md` (required template)

## Findings

### Current State
- Epics are tracked primarily via `Epic` type label + `Epic: short-name` labels. No meaningful use of GitHub Milestones for roadmap/Epic grouping or child linkage.
- PR → issue linking enforcement (in `pr-issue-link-check.yml`) is limited to Feature/Bug PRs requiring a closing keyword in the body. Design/Research PRs receive only warnings. Sidebar "Development" links are not inspected.
- `delete_branch_on_merge` is not enabled at the repository level. Bootstrap guidance and AGENTS.md do not treat it as the default.
- Enforcement is scattered across AGENTS.md, multiple workflow files, bootstrap docs, and custom Python code (`epics.py`).

### Gaps vs. Locked Requirements (from Epic #100)
1. Milestones as primary Epic mechanism + child linkage: Not used. Custom labels still required in many places.
2. Mandatory linked issue for Feature/Bug/Design/Research PRs + reliable auto-close: Only partially enforced (Feature/Bug only via body keyword). No sidebar support.
3. Automatic branch deletion on merge as default: Not configured or documented as expected behavior.

### Options & Trade-offs
- Keep `Epic:` labels as supplemental metadata while adopting Milestones as source of truth.
- Expand the closing-keyword check to all four PR types (or require sidebar linkage).
- Enable repo-level delete-on-merge + update bootstrap/AGENTS.
- `no-issue` escape hatch remains useful for non-resolving PRs.

## Recommendation

Phased adoption:
1. Quick wins (low risk): Enable `delete_branch_on_merge` at repo level, expand `pr-issue-link-check.yml` to cover Design/Research PRs, update AGENTS.md + bootstrap checklist.
2. Pilot Milestones on one active Epic (e.g. #100 or #89).
3. Decision record on future of `Epic` type/`Epic: ` labels (potential deprecation after template consumers are updated).
4. Follow-on Design child issue to detail the migration and any workflow/AGENTS changes.

This research artifact (plus any follow-on Design work) provides the required traceable commit for closing #101 and advances Epic #100.

