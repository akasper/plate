# PLATE Methodology Inventory and Ownership Classification

- **Issue:** #106 (Epic #89)
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-28
- **Status:** Completed

## Research Question

What PLATE methodology assets currently live in `akasper/plate_template`, which assets already exist in `akasper/plate`, and which should be tool-owned vs repo-owned after cutover?

## Sources

- Epic context in issue #89 and child issue #106
- Existing Epic #89 TDD artifacts in `tests/test_epic89_inventory.py`
- Current repository state in `akasper/plate`

## Findings

### Canonical inventory (48 missing-template assets from audit)

| Category | Count | Ownership target | Migration action |
|---|---:|---|---|
| `.github/workflows/*` | 5 | Tool-owned (core methodology automation) | Copy to `plate` main |
| `docs/*` | 15 | Tool-owned (canonical process/design/research docs) | Copy to `plate` main |
| `scripts/*` | 10 | Tool-owned (platform/bootstrap/validation helpers) | Copy to `plate` main |
| `tests/*` | 16 | Tool-owned (methodology validation + fixtures) | Copy to `plate` main |
| Root config (`package.json`, `playwright.config.ts`) | 2 | Tool-owned baseline + repo-local overrides via `.plate` | Integrate into existing layout |

### Ownership boundary (target state)

- **Tool-owned (`akasper/plate`)**
  - Core methodology assets (agents, skills, marker contracts, core workflows, baseline docs).
  - Enforcement patterns and default automation.
  - Packaging/distribution metadata for reusable PLATE assets.
- **Repo-owned (consumer fork/project)**
  - Lightweight root `.plate` file for configuration.
  - Optional local override sections and project-specific extensions.
  - Business/domain logic not part of PLATE core methodology.

## Recommendation

Adopt `akasper/plate` as canonical owner of methodology assets and treat `plate_template` as migration source/reference only during cutover. Use child design work (#108, #109, #110) to lock schema, sync contract, and phased migration gates.
