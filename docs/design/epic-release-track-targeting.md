# Epic-to-Release Track Branch Targeting — Design Spec

- **Issue:** #438
- **Designed by:** GitHub Copilot CLI (autonomous session)
- **Date:** 2026-06-09
- **Status:** Draft

## Problem

Branch targeting for Epic work is ambiguous during release development. We need one deterministic model that:

1. assigns each Epic to one release track branch;
2. works with `release-major`, `release-minor`, `release-patch`;
3. handles repositories still on legacy single `release`; and
4. defines where warnings appear when track state is missing or inconsistent.

## Constraints

- Keep Epic routing simple: one Epic targets one track branch at a time.
- Preserve existing release-ceremony model and `Next Release` targeting.
- Reuse existing fragment-based semver inference precedence (`major > minor > patch`).
- Keep migration-safe behavior for legacy repositories with only `release`.
- Prefer explicit surfaced warnings over silent fallback.

## Design Decision

Use **single-track-per-Epic targeting** with deterministic fragment-based inference and explicit legacy fallback.

### 1. Canonical targeting rule

For each Epic, derive one target track from release fragments associated with that Epic:

- inferred `major` -> `release-major`
- inferred `minor` -> `release-minor`
- inferred `patch` -> `release-patch`

Inference precedence is deterministic and matches existing release bump logic:

`major > minor > patch`

### 2. Mixed-signal behavior

If an Epic has mixed fragment signals, select the highest-severity track:

- any `breaking: true` fragment -> `release-major`
- else any `change_type: feature` fragment -> `release-minor`
- else -> `release-patch`

No weighted voting or multi-track assignment is allowed in this model.

### 3. Legacy fallback behavior

If `release-major|release-minor|release-patch` branches are absent but legacy `release` exists:

1. still compute inferred track (`major|minor|patch`);
2. route work to `release`; and
3. emit migration warning that track branches are missing.

This preserves forward progress while signaling drift.

### 4. Warning and visibility surfaces

Warnings should appear in the following surfaces:

- `gh plate release status` output
- `plate_release_status` MCP output
- release-target guidance helpers for Epic targeting
- release-cut/finalization guidance text when branch state is inconsistent

Warnings must include:

- inferred track,
- expected branch,
- actual fallback branch (if any), and
- corrective action (`gh plate bootstrap --apply` + re-check status).

### 5. Epic lifecycle alignment

- During active development, Epic work lands on its inferred track branch (or legacy fallback).
- At packaging time, versioned release branch creation continues to combine tracks per release ceremony rules.
- This design does not change the final Release PR requirement (`release-vX.Y.Z` -> `main`).

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Multi-track-per-Epic | Increases planning complexity and creates ambiguous merge ownership. |
| Label-only track selection | Diverges from fragment-based release inference and allows drift between declared and actual change impact. |
| Hard-fail when track branches are missing | Blocks ongoing work in transitional repositories that still use legacy `release`. |
| Silent fallback to `release` | Hides migration debt and causes confusing branch behavior. |

## Artifact

- This design artifact: `docs/design/epic-release-track-targeting.md`
- Input research: `docs/research/branch-management-track-inference-from-fragments.md` (#437)
- Parent Epic: #436

## Open Questions

- Should explicit `Major|Minor|Patch` labels be allowed to override fragment inference for an Epic when they conflict?
- Should warning severity differ between missing-track-branches vs. inferred-track/label mismatch?
- Should there be a dedicated `gh plate release target-epic` validation mode that blocks invalid targeting before PR creation?

## Acceptance Evidence

- A follow-up implementation slice maps inferred track to the correct branch for Epic targeting.
- Status surfaces report inferred track and legacy fallback behavior when applicable.
- Regression tests cover:
  - mixed fragment precedence;
  - single-track assignment;
  - legacy fallback with warning emission.
