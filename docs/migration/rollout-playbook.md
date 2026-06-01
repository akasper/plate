# PLATE Methodology Ownership Rollout Playbook and Adoption Guide

**Issue:** #128 (child of closed Epic #126 / post #89)

**Status:** Complete (autonomous implementation cycle)

This playbook documents the phased cutover from `plate_template` to `akasper/plate` as the canonical, single source of truth for the PLATE methodology. It incorporates evidence from prior children of Epic #126 (#127 inventory, #129 .plate schema, #130 markers, #131 migration primitives) and the foundational design in `docs/design/plate-template-cutover-plan.md`.

## Phased Rollout Model

### Phase 1: Soft Fork (Current state post #129–#131)
- **Entry Criteria** (achieved):
  - `akasper/plate` repo exists with complete methodology assets (AGENTS.md, .agentic/ fragments, workflows, baseline catalog, runtime engines for inventory/config/markers/migration).
  - All PLATES-CORE marker syntax and contract defined and implemented (#130).
  - .plate root config schema + resolution engine live (#129).
  - Migration dry-run/apply primitives with checkpoints available (#131).
- **Guardrails**:
  - `plate` publishes artifacts but `plate_template` remains the "canonical" for existing users during transition.
  - No forced changes to user forks.
  - Full backward compatibility for existing PLATES-CORE markers and templates.
- **Activities**:
  - Users can begin experimenting with `gh plate` commands (migrate plan/apply, health, etc.).
  - Pilot projects (internal + friendly forks) validate the flow.
- **Exit Criteria** (target for next cycle):
  - Pilot adoption metrics positive.
  - Zero critical bugs in core engines.
  - Documentation (this playbook + wiki) reviewed and published.
  - Extension model hardened.

### Phase 2: Parallel Adoption
- **Scope**:
  - Both `plate` (primary for new users) and `plate_template` (reference) coexist.
  - `gh plate init/integrate/configure` support both sources.
  - Marker sync and migration tooling fully exercised.
- **Compatibility Matrix** (high-level; see full inventory in #127 artifacts):
  | Asset Category | Plate (new canonical) | Template (reference) | Compatibility Notes |
  |----------------|-----------------------|----------------------|---------------------|
  | AGENTS.md + .agentic/ | Full PLATES-CORE sections + fragments | Legacy flat files | Markers enable safe partial sync |
  | Workflows & labels | Enforced via plate runtime | Mirrored for transition | Risk:low for low-complexity repos |
  | CLI/MCP surfaces | Native `gh plate` + MCP tools (migrate, health, etc.) | N/A (reference only) | Full parity targeted in #132 |
  | Baseline agents/skills | Catalog-driven in plate | Static in template | Delegation works cross-source |
- **Rollback Guidance**:
  - At any point before Phase 3: `git checkout template-branch` or disable plate features via env vars.
  - MigrationApplier checkpoints allow `gh plate migrate apply --rollback <checkpoint>`.
  - Full fork restore via `plate_template` archive (maintained read-only).
- **Guardrails**:
  - Adoption threshold < 50% before advancing (monitor via health/epic tools).
  - Support load tracked; pause if > acceptable.
- **Exit Criteria**:
  - Majority adoption (>75% of new projects).
  - 6-month stability window with positive community feedback.
  - Template issues/PRs redirected to plate.

### Phase 3: Plate Primary
- **Scope**:
  - `akasper/plate` is the unambiguous single source of truth.
  - `plate_template` becomes read-only reference fork + archive.
  - All new users directed to plate via docs, GitHub templates, and `gh plate` bootstrap.
- **Activities**:
  - Deprecation notices in template repo.
  - CI downgraded on template (reference only).
  - Full migration of historical artifacts complete.
- **Rollback** (limited):
  - Possible only for individual forks via local .plate overrides or manual marker edits.
  - No global rollback; plate is canonical.
- **Guardrails**:
  - Zero open critical issues in plate.
  - Extension sign-off complete for all core extensions.
- **Exit Criteria**:
  - Template repo archived or marked "reference only".
  - 6-month notice period observed.
  - All pilot success criteria met and documented.

### Phase 4: Template Deprecation (Final)
- **Scope**:
  - `plate_template` archived (read-only, with migration guide pointing to plate).
  - All methodology evolution happens exclusively in `akasper/plate`.
- **Guardrails**:
  - Exception process via plate issues only.
  - Historical reference preserved in git + wiki.
- **Completion Signal**:
  - This playbook marked complete.
  - Epic #126 children all closed with artifacts.
  - Community announcement + wiki update.

## Pilot Migration Checklist (for early adopters / #128 validation)

- [ ] Run `gh plate health` and `gh plate epic status` on target repo.
- [ ] Review `gh plate migrate plan` output (dry-run).
- [ ] Execute `gh plate migrate apply --dry-run` and inspect checkpoints.
- [ ] Perform marker sync / integrate for any custom AGENTS.md or workflows (using PLATES-CORE boundaries).
- [ ] Validate .plate config resolution (defaults < extensions < local).
- [ ] Run full test suite + any E2E (playwright if applicable).
- [ ] Document deviations in repo's own migration notes or .agentic/ fragment.
- [ ] Open feedback issue on akasper/plate with pilot results.
- [ ] (Optional) Request extension sign-off if custom extensions used.

## Risks & Validation

- **Adoption Resistance**: Mitigated by parallel phase + excellent tooling (migrate primitives, markers for safe edits).
- **Compatibility Regressions**: Addressed by inventory (#127), schema (#129), and conservative merge rules (#130).
- **Support Load Spikes**: Tracked via health/epic tools; guardrails include pause thresholds.
- **Rollback Safety**: Explicit checkpoints and per-fork overrides until Phase 3.

## Traceability & Ceremony

- All phases informed by closed children of Epic #126.
- Per-feature change fragments added for each implementation child.
- This playbook itself is the primary artifact for #128.
- Full Epic completion ceremony (final comments with usage reports, wiki updates) to be completed upon closure of #128 and confirmation of pilot success.

**Ready for community adoption and final validation.**

*Autonomous implementation complete for #128 deliverable.*
