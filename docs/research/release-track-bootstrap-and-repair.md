# Release-Track Bootstrap and Repair Lifecycle

- **Issue:** #319
- **Researched by:** GitHub Copilot CLI
- **Date:** 2026-06-03
- **Status:** Completed

## Research Question

Determine the canonical lifecycle for standing release-track artifacts in a new PLATE repository:

- when and where `release-major`, `release-minor`, `release-patch`, and legacy `release` should be created;
- whether standing release targets should exist as one `Next Release` issue, separate default Major/Minor/Patch release issues, or some other model;
- how to distinguish a never-initialized repository from corrupted or drifted release state; and
- what recovery flow should recreate missing issues/branches safely without duplicating release state.

## Sources

- Epic #306: release-ceremony refinement scope and acceptance criteria
- Question #319: required answer signal and current repository state
- `src/plate_core/bootstrap.py`
- `src/plate_core/release.py`
- `src/plate_core/cli.py`
- `.github/ISSUE_TEMPLATE/release.yml`
- `AGENTS.md`

## Findings

### Current implementation already implies a split ownership model

The repository now treats standing release-track **branches** and standing release-track **issues** as separate lifecycle concerns:

- `gh plate bootstrap --apply` creates `release-major`, `release-minor`, `release-patch`, and legacy `release` when they are absent.
- `gh plate release status` inspects open `Release` issues, active `Next Release` targeting, and on-hold Epics, but it does not create release issues.
- `gh plate release finalize` is explicitly documented as the place that should ensure the next standing `Next Release` issue after packaging/tagging, but that automation is still a stub.

That split is useful: bootstrap owns repository skeleton state, while finalize owns ceremony rollover after a concrete version is cut.

### One standing `Next Release` issue is the right source of truth

PLATE should use **one open `Release` issue titled `Next Release`** as the standing planning target for upcoming release negotiation.

Separate standing `Major Release`, `Minor Release`, and `Patch Release` issues would duplicate existing routing metadata:

- track intent already lives on work items through `Major` / `Minor` / `Patch` labels;
- integration flow already has corresponding branches (`release-major`, `release-minor`, `release-patch`);
- `gh plate release status` already models “targeted to active Next Release” versus “on hold”.

Adding three standing release issues would create a second planning taxonomy without adding a new decision point. The release question is not “which issue bucket exists?” but “which work should target the one upcoming release?”

### Healthy, never-initialized, and drifted state are distinguishable

#### Healthy standing state

A healthy repository in the refined model has:

1. `release-major`, `release-minor`, `release-patch`, and legacy `release` branches present.
2. Exactly one open `Release` issue representing the standing target (`Next Release` before packaging, renamed to a concrete version at packaging time).
3. No duplicate open `Next Release` issues.
4. `Major`, `Minor`, and `Patch` labels available for work routing.
5. After packaging, a newly spawned `Next Release` issue for subsequent work.

#### Never-initialized state

A repository should be treated as **never initialized** when **all** of the following are true:

1. None of the standing release-track branches exist.
2. There is no open or closed `Release` issue history.
3. There is no versioned release history (for example, no prior tags or versioned `.agentic/releases/vX.Y.Z/` directories).
4. There is no work already using the refined release-track labels and targeting model.

This is the “fresh repo bootstrap” case.

#### Drifted or corrupted state

A repository should be treated as **drifted** when only part of the standing state exists, or when release history proves the system has already been initialized. Examples:

- one or more release-track branches are missing but others exist;
- more than one open `Next Release` issue exists;
- a concrete release issue was created during packaging, but no fresh `Next Release` issue was spawned afterward;
- release tags/history exist but no standing release issue remains open;
- track labels or targeted Epics exist, but the standing release issue is missing.

This is not a bootstrap case; it is a repair case.

## Recommendation

### Canonical lifecycle

1. **Initial creation is owned by `gh plate bootstrap --apply`.**
   - It should ensure standing release-track branches and labels exist for a new repository.
   - It should also evolve to ensure a single open `Next Release` issue exists when the repository is first initialized.
2. **Packaging/finalization is owned by `gh plate release finalize`.**
   - It should rename or replace the active `Next Release` issue with the concrete versioned release issue as part of packaging.
   - It should immediately create the next standing `Next Release` issue so negotiation can continue without a gap.
3. **Repair is owned by a dedicated idempotent command rather than ad hoc manual recreation.**
   - The repository currently lacks this automation.
   - A follow-up command should detect missing branches/issues, distinguish bootstrap from repair, and recreate only the missing artifacts without duplicating healthy state.

### Artifact model

- **Branches:** `release-major`, `release-minor`, `release-patch`, and legacy `release`.
- **Labels:** `Major`, `Minor`, `Patch` on change-driving issues.
- **Standing release issue:** exactly one open `Release` issue titled `Next Release`.
- **No separate default Major/Minor/Patch release issues.**

### Recovery flow until dedicated automation exists

Until init/repair automation lands, the safe manual recovery flow is:

1. Run `gh plate bootstrap --apply` to recreate missing release-track branches and labels.
2. Inspect current state with `gh plate release status`.
3. If no active `Next Release` issue exists, create exactly one from `.github/ISSUE_TEMPLATE/release.yml` with title `Next Release`.
4. If duplicate open `Next Release` issues exist, consolidate manually and leave only one canonical target.
5. Re-run `gh plate release status` and verify that Epics now appear as targeted or on-hold against a single active release target.

### Follow-up implementation work

The repository still needs a dedicated automation slice for standing release artifact creation and repair. That work is now tracked as follow-up Feature issue #320 under Epic #306.
