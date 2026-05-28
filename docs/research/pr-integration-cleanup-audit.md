# Research: PR Integration Cleanup Audit (Epic #100 / #101)

**Issue:** #101 (Research child of Epic #100)
**Date:** 2026-05-28
**Author:** Autonomous agent (Grok)

## Executive Summary
This audit inventories PLATE's current custom Epic/PR linking mechanisms against native GitHub features (Milestones, linked issues in Development sidebar, delete-on-merge). Gaps are mapped to the three locked requirements from the Epic. A minimal change set is recommended. Full migration is out of scope for this child.

## 1. Current State Inventory

### Epic Tracking
- **Primary mechanism:** `Epic` issue type label + `Epic: short-name` labels (e.g. `Epic: pr-feedback-babysitting`, `Epic: plate-methodology-ownership`, `Epic: pr-integration-cleanup`).
- **Enforcement points:**
  - `AGENTS.md` §Label Rules, §Issue Artifact Rules, §Epic readiness checklists: requires exactly one Epic: label on Epic/Feature issues.
  - `.github/workflows/label-check.yml` and new `labels.yml` (post #103): validates Epic labels on PRs/issues.
  - Bootstrap scripts and `docs/bootstrap/new-repository-checklist.md`.
  - `docs/wiki/Automatic-Epic-Creation.md` and `docs/research/automatic-epic-creation.md` (heavy prior research).
  - `src/plate_core/epics.py` + tests (test_epics.py, recent test_epic89_* suite added in #113 for methodology ownership).
- **Milestone usage:** Minimal/none in current open Epics (#89, #100, #112). GitHub Milestones exist in repo settings but not wired into PLATE processes or AGENTS guidance.
- **Recent related work:** Epic #89 (PLATE as Single Source of Truth) has spawned extensive TDD test suite (`tests/test_epic89_*.py`) and updates to workflows/CURRENT.md, but still uses custom Epic labels.

### PR → Issue Linking
- **Enforcement:** `.github/workflows/pr-issue-link-check.yml` (the "check-closing-keyword" job).
  - Requires `Closes #N` (or Fixes/Resolves) **only** for PRs labeled `Feature` or `Bug`.
  - Design/Research/Question PRs get only a *warning* if no keyword (allows `no-issue` escape hatch).
  - Feedback Response PRs are exempt.
  - Sidebar "Development" links are **not** checked or enforced.
- **Closing behavior:** Relies on GitHub's body keyword magic for auto-close. No use of GraphQL `linkedIssues` or transition rules.
- **Evidence in code:** AGENTS.md mandates `Closes #N` in every PR body for traceable artifacts. Recent PRs (e.g. #104, #113, #116) follow this.

### Branch Deletion
- **Repo setting:** `delete_branch_on_merge` is **not** enabled at akasper/plate org/repo level (confirmed via prior audit in planning session for Epic #100).
- **Guidance:** Bootstrap scripts (`scripts/bootstrap_github.sh`, BootstrapGitHub.ps1) and `docs/bootstrap/new-repository-checklist.md` do not mention or enforce the setting.
- **Per-PR:** No automation; relies on manual GitHub UI or `gh pr merge --delete-branch`.
- **AGENTS.md:** Recommends squash merges for clean history; no explicit "delete on merge as default" doctrine yet.

### Other References
- `CONTRIBUTING.md`, `CURRENT.md` (hygiene rows reference Epic labels).
- `.agentic/` (if present in template sync) and plugin agents reference Epic process.
- No heavy use of GitHub Projects for Epic burndown in this repo (planning state lives in issue bodies + labels).

## 2. Gap Analysis vs. Locked Requirements

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| 1. Milestones as primary Epic mechanism + child linkage | Custom `Epic` + `Epic: ` labels + heavyweight Epic issues | No Milestones used for Epics; no automatic child linkage or burndown from Milestones. `Epic` labels still required in many places. |
| 2. Mandatory linked issue for Feature/Bug/Design/Research PRs + reliable auto-close | Only Feature/Bug enforced via body keyword; others warning-only. Sidebar links ignored. | Design/Research PRs (common for Epic children) lack hard requirement. No sidebar enforcement. Auto-close works but fragile if keyword omitted. |
| 3. Automatic branch deletion on merge as default | Not enabled at repo level; no guidance or bootstrap support | Friction for rapid agent PRs; branches accumulate. Inconsistent with "easy revert as norm". |

## 3. Options & Trade-offs

- **Epic labels vs. Milestones:** Keep `Epic` type + `Epic: ` as *supplemental metadata* (for filtering, AGENTS checklists) while making Milestones the source of truth for roadmap/Epic identity. Or deprecate `Epic` labels entirely after migration (high risk for downstream template consumers).
- **Linking policy:** Strengthen `pr-issue-link-check.yml` to require closing keyword (or explicit sidebar link via API?) for *all four* PR types (Feature/Bug/Design/Research). Keep `no-issue` for chores.
- **Branch deletion:** Enable repo-level `delete_branch_on_merge=true` via API + document in bootstrap checklist + AGENTS as the expected default (with per-PR override note).
- **Escape hatches:** `no-issue` remains useful for label-only or doc-sync PRs.

**Recommended:** Phased — first enable delete-on-merge + expand linking requirement (low risk), then pilot Milestones on one Epic (#89 or #100), update AGENTS + bootstrap, deprecate labels only after template sync and downstream feedback.

## 4. Recommended Minimal Change Set

1. **Enable delete branch on merge** (repo setting + one-line note in bootstrap checklist and AGENTS §Autonomous Mode / PR discipline).
2. **Expand pr-issue-link-check.yml** to treat Design/Research like Feature/Bug (hard fail without keyword or `no-issue`).
3. **Inventory + update AGENTS.md** (Label Rules, Issue Artifact Rules, PR creation examples) + `docs/bootstrap/new-repository-checklist.md`.
4. **Create Design child** (follow-on) for Milestone adoption strategy + label taxonomy decision record.
5. **Lightweight test/docs PR** (this one) committing this audit + any immediate doc fixes.
6. (Later) Update label-check / other workflows if Epic labels become optional.

No changes to `.github/CODEOWNERS`, no security surface, low risk for autonomous merge.

## Evidence & Traceability
- Committed artifact: this file (`docs/research/pr-integration-cleanup-audit.md`).
- References: AGENTS.md (full read), `.github/workflows/pr-issue-link-check.yml`, `labels.yml`, `ci.yml`, `docs/bootstrap/...`, recent PR #113 (Epic #89 TDD), gh queries on open Epics (#89, #100, #112), repo settings audit (via planning context).
- Closes #101. Contributes to Epic #100.

## Next Steps (for Design child / Epic)
- Pilot Milestones on Epic #100 or #89.
- Decision record on future of `Epic` labels (ADR or update to this doc).
- Update downstream plate_template via PLATES-CORE blocks after consensus.

This audit is self-contained and ready for the Design phase.
