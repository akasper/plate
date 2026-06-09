# Branch Management: Track Inference from Release Fragments

- **Issue:** #437
- **Researched by:** GitHub Copilot CLI (autonomous session)
- **Date:** 2026-06-09
- **Status:** Completed

## Research Question

Define deterministic rules to infer `Major` / `Minor` / `Patch` release-track intent from release fragments, including tie-breakers, mixed-signal behavior, and legacy single-`release` fallback behavior.

## Sources

- `src/plate_core/release.py`
- `tests/test_cut_release.py`
- `docs/design/release-ceremony-refinement.md`
- `docs/research/release-track-bootstrap-and-repair.md`
- `AGENTS.md`

## Findings

### Current behavior already defines deterministic semver precedence from fragments

`infer_bump_type()` in `src/plate_core/release.py` is deterministic:

1. Any fragment with `breaking: true` -> `major`
2. Else any fragment with `change_type: "feature"` -> `minor`
3. Else -> `patch`

`tests/test_cut_release.py` already codifies this precedence and mixed-signal outcomes.

### Track inference can be defined directly from the same precedence

For single-track-per-Epic targeting, map inferred bump to track branch:

- `major` -> `release-major`
- `minor` -> `release-minor`
- `patch` -> `release-patch`

This preserves one deterministic rule-set for both version bump and track targeting, instead of maintaining separate competing heuristics.

### Mixed-signal tie-breaker should remain highest-severity-wins

For fragment sets containing multiple signal types (for example docs + feature, or feature + breaking), the deterministic tie-breaker is:

`major > minor > patch`

This is already validated in unit tests and avoids ambiguity during packaging and branch-target selection.

### Legacy fallback remains necessary during migration

When track branches are absent but legacy `release` exists, inferred track should still be computed, but landing should fall back to `release` with explicit warning/reporting (not silent branch substitution failure). This is aligned with current transition guidance in `AGENTS.md` and prior lifecycle research.

## Recommendation

Adopt the following canonical inference contract for Branch Management work:

1. **Inference source:** release fragments only (default path for automated targeting).
2. **Inference algorithm:** existing `infer_bump_type()` precedence (`major > minor > patch`).
3. **Track mapping:** inferred bump maps 1:1 to `release-{major|minor|patch}`.
4. **Mixed signals:** highest-severity-wins with no additional voting logic.
5. **No fragments:** block automated track inference and require explicit operator input.
6. **Legacy mode:** if track branches are missing, target legacy `release` and surface migration warning.

## Follow-up Implementation Targets

- #438 should codify this as branch-targeting design language.
- #439 should enforce and surface the mapping in CLI/MCP status and release flows.
- #440 should add regression coverage for mixed-signal and legacy-fallback cases.
