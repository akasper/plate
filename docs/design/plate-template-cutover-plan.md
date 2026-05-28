# Phased Cutover Plan: `plate_template` -> `plate` Methodology Ownership

- **Issue:** #110 (Epic #89)
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

The methodology/tooling split across `plate_template` and `plate` creates ownership ambiguity and drift risk.

## Constraints

- No risky big-bang migration.
- Preserve existing user forks.
- Keep rollback options until plate is clearly proven as canonical.

## Design Decision

### Phase model

1. **Phase 1 — Soft Fork**
   - `plate` publishes complete methodology artifacts; template still canonical for users.
2. **Phase 2 — Parallel Adoption**
   - Users can onboard via either source while tooling supports both.
3. **Phase 3 — Plate Primary**
   - `plate` becomes canonical source of truth; template is reference-only.
4. **Phase 4 — Template Deprecation**
   - template archived/read-only with migration guidance.

### Required workstreams

- CLI workstream (`gh plate init/integrate/configure/install/upgrade`)
- Asset packaging/distribution workstream
- Migration execution/support workstream

### Risk + validation gates

- Track adoption resistance, compatibility regressions, and support-load spikes.
- Use explicit entry/exit criteria for each phase.
- Maintain rollback points through Phase 2.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Immediate hard cutover | High breakage risk for existing forks |
| Indefinite dual ownership | Perpetuates ambiguity and drift |

## Acceptance Evidence

- `tests/test_epic89_cutover.py` captures phase, rollback, workstream, risk, and validation checklist expectations.
