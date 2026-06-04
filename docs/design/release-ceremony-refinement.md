# Release Ceremony Refinement — Design Spec

- **Issue:** TBD (Epic for refining the PLATE Release process per user query + interactive Q&A)
- **Designed by:** Agent planning session (with human Q&A input)
- **Date:** 2026-06-03
- **Status:** Draft (plan approved; implementation slices to follow)

## Problem

The current PLATE Release foundation (introduced via #194, #261, release-issue-type, release-cut, extensions-release-checks, bootstrap-release-branch, and documented in AGENTS.md §Release + Branch Model, .agentic/process.yml release_rules, .github/ISSUE_TEMPLATE/release.yml, gh plate release {status,cut,notes}, etc.) provides a solid MVP:

- `Release` as first-class issue type + template with versioned title, linked_epics (free text), pre-release checklist, extension release_checks.
- Three-tier branch model (`epic/<name>` → `release` (single persistent, protected) → `main`).
- Fragment-driven change tracking + `gh plate release cut` for aggregation + semver inference.
- `gh plate release status` surfaces pending fragments + extension checks + open Release issues.
- Manual ceremony for tag, GitHub Release, hard-reset.

However, per the initiating query and live Q&A clarifications, gaps remain that make the "upcoming release" hard to target, scope negotiation opaque, CI undifferentiated (risking either slow normal PRs or insufficient validation on releases), enforcement inconsistent (no milestone for Release issues or most behavior PRs), and the "big steps" (packaging/version freeze + finalization with downstream triggers) under-automated and under-documented. Epics can complete but have no formal "target release" association, leading to invisible "on hold" work. The single `release` branch + always-versioned-upfront Release issues do not support a standing "always available" target or explicit semver-track intent (Major/Minor/Patch) on work items.

The goal of this small Epic is a refinement that makes the next release a first-class, queryable, linkable target with clear tracks, appropriate CI cost, stronger native GitHub hygiene (milestones), and explicit phases + automation hooks for packaging and finalization (including spawning the next "Next Release" issue).

## Constraints

- Preserve existing required issue/PR type labels and "exactly one" enforcement.
- Prefer native GitHub features (labels, milestones, Development sidebar links, Projects fields for mutable planning state, Actions conditionals, GraphQL for linked issues) over new persistent bots.
- Stay consistent with .plate config convention (existing JSON file from Epic #89/#108; health + plate_config.py) while accommodating user request for release/finalization config "under .plate/".
- Follow PLATE rules strictly: atomic PRs (soft ≤10 files), fragments in `.agentic/releases/unreleased/` for every process/template/agent-surface change, update AGENTS.md + .agentic/process.yml together, human judgment at irreversible steps (tagging, public claims), Closes #N in PR bodies only, no self-merge unless autonomous + risk:low.
- Do not weaken existing checks (label exactly-one, issue links for Feature/Bug/Documentation PRs, fragment gate for Feature PRs, feedback-resolution, etc.).
- Support additive migration for existing single-`release`-branch PLATE repos (do not break current ceremony overnight).
- Keep CI cost in mind: heavy steps must have fast-fail "gateway" checks; normal development stays lightweight.
- GitHub limits: 0-1 milestone per issue/PR; branch protection is per-branch and often manual.

## Design Decision

**Evolve to a multi-track "Next" model with standing Release issue + explicit packaging/finalization phases, while extending native enforcement and tooling.**

### Key elements of the refined model (synthesized directly from query bullets + Q&A answers)

1. **Standing "Next Release" issue (always-present target)**:
   - Default title "Next Release" (template supports this; version field becomes optional or derived later).
   - Epics (and other work) explicitly link to it via native GitHub Development sidebar (accepted pattern from Epic #100 native PR integration).
   - `gh plate release status` (and MCP) queries the active Next Release issue (open `label:Release` whose title indicates "Next") and surfaces linked Epics + "on-hold" Epics (those carrying a semver track label but no link to an active Next Release).
   - Helper surfaces (new `gh plate release target-epic <N>` or equivalent MCP tool) to create the sidebar association.

2. **Major / Minor / Patch labels on changing issues + three permissive next- integration branches**:
   - New stable labels "Major", "Minor", "Patch" (added to .github/labels.yml + all enforcement arrays, docs, payload).
   - Every issue that changes repo behavior/docs (Feature, Bug, Documentation, possibly Epic) carries exactly one (enforced or strongly encouraged via label-check + checklist).
   - Three "next" branches: `release-major`, `release-minor`, `release-patch` (created by bootstrap; permissive "dumping ground" integration branches during active development toward the next release).
   - Work labeled with the matching semver track targets the corresponding next- branch (epic/* work still funnels in via the track label).
   - The standing Next Release issue is associated with the active track work.

3. **Packaging phase (the "big step" that locks the release)**:
   - Human + LLM negotiation (links, labels on work, fragments, gh plate release status, existing curiosity/Q&A) determines scope.
   - "Freeze non-bug merges" (initially ceremony + status + optional human-review label or protection tweak; full enforcement can evolve).
   - Version is generated/confirmed when entering the ceremony (cut_release inference from fragments + track labels + any direct declaration on the Release issue).
   - Create a concrete versioned branch (e.g. `release-v0.1.1` or `release-0.1.1`), typically by rebasing/combining the relevant next- branch(es):
     - Patch release: from `release-patch`.
     - Minor: from `release-minor` + `release-patch`.
     - Major: from all three.
   - Rename the standing "Next Release" issue title to the specific semver (e.g. "v0.1.1").
   - *Immediately* create a fresh "Next Release" issue (so targets always exist).
   - The "Release PR" is the (Documentation-labeled) PR from the versioned branch → `main`.

4. **Release PRs + differentiated heavy CI**:
   - PRs carrying the "Release" label or targeting a `release-v*` (or stabilization on next-*) branch run additional later-stage heavy jobs after common fast-fail gates: expanded e2e, security scans, architecture/code review, full recompilation + packaging, other "heavy lifting".
   - Normal PRs (including to the permissive next-* branches during integration) stay on the lightweight path.
   - Implemented via `if:` conditions in ci.yml (or a companion release-ci workflow) using `github.event.pull_request.labels` and `github.head_ref` / base ref. Emphasize gateway checks to avoid wasting minutes.

5. **Milestone hygiene**:
   - `label-check.yml`: Add "Release" to `requiresMilestone` (every Release issue gets its own GitHub milestone, like Epics).
   - Extend pr-issue-link-check.yml (or add a narrow companion check) to require a milestone on "documentation- or behavior-modifying PRs" (broad definition: most non-'no-issue' / non-Feedback-Response PRs that touch docs or code; exempt pure chores via the existing 'no-issue' escape hatch).
   - PRs for work inside an Epic naturally carry the Epic's milestone (satisfies "exactly one" for many cases). GitHub's 1-milestone limit is respected.

6. **Finalization phase (after CI green + nothing left to merge)**:
   - PLATE performs (or orchestrates) the actual `git tag vX.Y.Z && push --tags`.
   - Configurable downstream triggers are kicked off (declared in the project under `.plate/` — some common ones like "documentation update" built into PLATE core library; others provided by extensions and gated by their `release_checks` with `human_approval_required`).
   - This phase also ensures the next "Next Release" issue exists (if the rename step didn't already trigger it).
   - `gh plate release finalize` (new or extended surface) provides the command/MCP hook; initially can be a guided step printer + invocation of declared core triggers, with full pluggable execution evolving.
   - Existing hard-reset of the appropriate branch (the versioned one or the next- track) remains.

7. **Negotiation / on-hold visibility**:
   - Epics without a sidebar link to an active Next Release issue (or without a semver track label + target branch) are "on hold" — even if feature complete. They can remain so indefinitely.
   - `gh plate release status` (enhanced) + new target helper make the set of targeted vs. on-hold Epics visible and actionable.
   - The standing Next Release issue + its linked work + the per-issue Major/Minor/Patch labels + fragments become the living record for human + LLM negotiation of scope.

**Branch protection & lifecycle notes**:
- The next-* branches are more permissive (integration "dumping ground").
- Once a version is frozen and the issue renamed, the versioned `release-vX.Y.Z` branch is the tighter one for final stabilization + the Release PR.
- Protection guidance updated in AGENTS/process.yml/bootstrap output to cover the new branches (PRs required; appropriate source restrictions; status checks).
- Hard-reset targets the right branch post-tag.

**Config for triggers**:
- Project-specific release/finalization config lives under `.plate/` (reconciling with the existing root `.plate` JSON file from Epic #89: either a "release" key in the JSON, or `.plate/release.json` / directory support).
- Core library provides a few common triggers; extensions declare more via the existing `release_checks` pattern (already surfaced by status).

This model is a deliberate evolution (not a full rewrite) of the existing foundation. The single `release` + always-versioned-upfront issues become the "Next" + track + packaging/rename/spawn lifecycle + versioned release-v* + heavy Release PRs.

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Keep single `release` + always create versioned "[Release]: vX.Y.Z" upfront | Does not solve "always have a Next Release for Epics to target"; forces version decision too early; no natural place for track labels + combining logic. |
| Use only Projects fields for Major/Minor/Patch and "release target" (no new labels) | User explicitly wants labels on changing issues to drive branch targeting and the checklist. Pure Projects would be less visible in label lists and harder to use for branch protection / CI `if:` conditions. (We still respect the doctrine by noting the tension and allowing Projects "release target" as a complement.) |
| Single next-release branch + subdirectories or heavy scripting for tracks | Loses the clarity of explicit `release-major` etc. branches that Epics/PRs can target directly; makes protection and CI gating more complex. |
| Full automation of branch creation, combining, tagging, and all downstream triggers in first slice | Exceeds "small epic" + "include CI + milestones as core". Start with model + enforcement + visibility + helpers + design; leave full orchestration + freeze enforcement as follow-up slices. |
| Require exactly one of Major/Minor/Patch on *every* issue (including pure Questions/Research) | Overly broad; limit to issues that change the repo (Feature/Bug/Documentation etc.). Use checklist + label-check for the relevant types. |
| Heavy CI on every PR to next-* branches | User emphasized "dumping ground" during integration + "common gateway failure steps" + "only run when the release branch is stabilizing." Gate on the final Release context (label or versioned branch target). |

## Artifact

- Primary: `docs/design/release-ceremony-refinement.md` (this file) + the approved planning artifact in the session plan.md (for traceability during implementation).
- Updated doctrine: `AGENTS.md` (Branch Model table + ceremonies, Release work loop, Label Rules, Fragment authoring, new negotiation/on-hold guidance).
- Machine-readable: `.agentic/process.yml` (expanded `branch_model`, `release_rules`, labels).
- Template: `.github/ISSUE_TEMPLATE/release.yml` (Next Release title support, track declaration, updated checklists).
- Labels: `.github/labels.yml` (+ "Major", "Minor", "Patch").
- Enforcement: `.github/workflows/label-check.yml`, `pr-issue-link-check.yml` (or companion), `ci.yml` (heavy jobs).
- Bootstrap/tooling: `src/plate_core/bootstrap.py`, `src/plate_core/release.py` + cli.py + mcp_server.py (status enhancements, helpers), `src/plate_core/plate_config.py` / health.py (release config surface).
- Fragments: One or more in `.agentic/releases/unreleased/` for every process change (e.g. `release-ceremony-refinement.json`, `next-release-lifecycle.json`, `semver-track-branches.json`, `release-milestones-and-pr-enforcement.json`, `heavy-release-ci.json`, etc.).
- Payload: Updates under `src/plate_core/template_payload/` (labels, process.yml, workflows, bootstrap scripts, ISSUE_TEMPLATE, example .plate, docs) + inventory/manifest.
- Tests: Updates to `tests/test_native_github_pr_integration.py`, `tests/test_release.py`, `tests/test_bootstrap.py`, `tests/test_cut_release.py`, new assertions for milestone/branch/CI conditions.
- Supporting: Updates to `CONTRIBUTING.md`, `.github/copilot-instructions.md`, `docs/bootstrap/new-repository-checklist.md`, release-ceremony extension description in `.agentic/extensions.yml`, `scripts/...` notes.

See the approved plan.md (session artifact) for the detailed file-by-file delta list and atomic PR sequence.

## Open Questions

- Exact naming convention for the three next- branches and versioned ones (`release-major` vs. `next-major-release` etc.; `release-v0.1.1` vs. `release/0.1.1`)? (To be locked in the first doctrine PR.)
- Precise definition of "when the Release label is applied" (only the final release-v* → main PR, or also late stabilization PRs into the next-* branches)?
- Operationalization of "freeze non-bug merges" in the first cut (ceremony step + status + `need:human-review`, or actual branch protection / label-check extension)?
- Concrete JSON shape under `.plate` for triggers (and whether we evolve `.plate` to support directory children or keep a single file with a "release" key).
- Whether "Next Release" itself can/should carry a subtype (Next Major Release) or whether the track is carried only by the child work items' labels.
- Specific heavy CI steps that must ship in the first implementation (or are placeholders + comments acceptable)?
- Risk tolerance: Is the 3-track branch model + label-driven targeting in scope for this "small" epic, or should the multi-track be split to its own Epic after the standing Next Release + milestone/CI basics land?
- Links to prior work: Confirm Epic numbers / milestones to reference (user's #194, #261, Epic #89 for .plate, Epic #100 for native milestones/links, contemplation/curiosity Epics for negotiation).

## Acceptance Evidence

- Design doc committed and referenced from the Epic.
- Standing "Next Release" issue can be created; Epics link to it via sidebar; `gh plate release status` reports targeted + on-hold Epics (with Major/Minor/Patch labels visible).
- Bootstrap creates (or plans) `release-major`, `release-minor`, `release-patch`.
- PRs in a Release stabilization context run extra CI steps (observable in logs/runs) while normal PRs do not.
- label-check requires milestone for Release issues; behavior/doc PRs without a milestone are rejected (with 'no-issue' escape).
- Updated AGENTS.md + process.yml + ceremony checklist describe the full Next Release → label+branch → packaging (rename + spawn next + versioned branch + Release PR) → finalize (tag + triggers + next issue) flow.
- `gh plate release cut` / status / new helpers work for the model; fragments exist and would appear in rendered notes.
- All tests (including "workflow text contains" + new coverage) pass; `gh plate bootstrap --dry-run` and a manual dry-run of the ceremony succeed.
- Template payload updated so new repos inherit the model.
- No unresolved `need:*` or `status:blocked` on the Epic (or explicitly accepted by human).

---

**Implementation note**: This design will be realized via a series of atomic Documentation + Feature PRs per the approved plan (doctrine + design first, then labels/template, enforcement, bootstrap/tooling, payload/tests, fragments throughout). Each changing PR will carry the required fragment(s) under `.agentic/releases/unreleased/`. Human review is required for all process changes.