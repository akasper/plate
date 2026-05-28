# `.plate` Root Configuration Schema and Lifecycle — Design Spec

- **Issue:** #108 (Epic #89)
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

PLATE needs a single, explicit boundary between tool-owned methodology and repo-owned customization.

## Constraints

- Must support deterministic precedence.
- Must support extension enablement + per-extension overrides.
- Must support forward-compatible version migration.
- Must keep project config lightweight.

## Design Decision

### File contract

- Each PLATE project has a root `.plate` file.
- Initial top-level schema:
  - `version`
  - `methodology`
  - `extensions`
  - `overrides`

### Resolution semantics

- Effective config is resolved in strict order:
  1. Tool defaults (`akasper/plate`)
  2. Enabled extension-provided config
  3. Local `.plate` overrides (final precedence)

### Validation semantics

- `version` is required and semver-like (`major.minor` or `major.minor.patch`).
- Unknown top-level keys:
  - strict mode: reject
  - lenient mode: allow for forward compatibility

### Lifecycle

1. `gh plate init` creates baseline `.plate`.
2. `gh plate configure` mutates safe fields.
3. `gh plate upgrade` applies schema migration transforms by `version`.
4. Validation runs pre-apply and in CI checks.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Keep ownership split with no `.plate` boundary | Continues drift/duplication risk |
| Store all config in multiple files | Increases complexity and upgrade risk |

## Acceptance Evidence

- `tests/test_epic89_plate_config.py` captures schema, validation, and resolution expectations.
