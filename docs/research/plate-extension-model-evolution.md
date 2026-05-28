# PLATE Extension Model Evolution for Tool-Owned Methodology

- **Issue:** #107 (Epic #89)
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-28
- **Status:** Completed

## Research Question

How should PLATE extensions evolve when the core methodology moves from `plate_template` to `akasper/plate` ownership?

## Sources

- Epic context in issue #89 and child issue #107
- Existing extension model tests in `tests/test_epic89_extensions.py`
- Existing catalog/discovery implementation in `src/plate_core/`

## Findings

### Current-model constraints

- Existing extension metadata and enablement are already modeled as structured config.
- Backward compatibility must preserve existing extension IDs and major-version API compatibility.
- Fork-local overrides are required to avoid forcing one-size-fits-all behavior.

### Target model

1. **Core-owned defaults in tool**
   - The `plate` tool ships default extension metadata/behavior.
2. **Config-driven enablement**
   - `.plate` controls `extensions.enabled`, `extensions.sources`, and per-extension settings.
3. **Deterministic resolution order**
   - `tool defaults -> extension metadata -> local override`.
4. **Compatibility contract**
   - Legacy format remains parseable.
   - Extension API compatibility uses explicit version checks.

## Recommendation

Formalize the extension contract in `.plate` schema docs (#108) and enforce it in future CLI commands (`init`, `configure`, `install`, `upgrade`) after migration design is finalized.
