# PLATES-CORE Marker Contract and Upstream Sync Behavior — Design Spec

- **Issue:** #109 (Epic #89)
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

As PLATE becomes canonical in `akasper/plate`, marker-based sync rules must be explicit so local forks can adopt upstream safely.

## Constraints

- Marker syntax must be machine-parseable.
- Nested markers are invalid.
- Section names must be unique per file.
- Local customization outside markers must remain fork-owned.

## Design Decision

### Marker syntax

- Start: `<!-- PLATES-CORE: section-name -->`
- End: `<!-- /PLATES-CORE -->`
- `section-name` uses kebab-case and is unique within each file.

### Ownership contract

- Inside marker: core/tool-managed content.
- Outside marker: fork-managed content.

### Sync and merge behavior

- Detect markers and validate structure (no nesting, no orphan end markers, no unclosed blocks).
- On sync conflict inside marker:
  - Preserve local edited content if base/local differ (conservative local-preservation rule).
  - Surface warning for user review.
- Outside markers, use normal merge behavior.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Full-file overwrite on sync | Destroys local customization |
| No markers, manual merge only | Too error-prone and non-scalable |

## Acceptance Evidence

- `tests/test_epic89_markers.py` defines parser, validation, and merge-behavior expectations.
