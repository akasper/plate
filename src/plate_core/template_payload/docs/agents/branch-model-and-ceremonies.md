# Branch Model And Ceremonies

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Branch Model and Ceremonies

PLATE uses a **multi-track release-oriented branch model** (refined in the Release Ceremony Refinement design, see `docs/design/release-ceremony-refinement.md`) to keep parallel epic work isolated while providing always-available "Next" targets for scope negotiation and explicit Major/Minor/Patch release tracks.

### Branch tiers (current refined model)

| Branch | Purpose | Who merges into it |
|---|---|---|
| `epic/<short-name>` | Owned by one Epic. Feature/Bug PRs for that Epic typically target a track-specific next- branch (see below) after receiving a Major/Minor/Patch label. | Feature/Bug PRs (squash), funneled by track label |
| `release-major`, `release-minor`, `release-patch` | Permissive "next" integration branches associated with the standing "Next Release" issue. Work labeled with the matching semver track targets the corresponding branch during active development / scope negotiation. These act as the "dumping ground" until packaging. | Work carrying the matching Major/Minor/Patch label (plus epic-close PRs for that track) |
| `release-vX.Y.Z` (or equivalent versioned) | Concrete, tighter integration branch created during the packaging phase for a specific release. Receives the final stabilization work and is the source of the Release PR to main. | Final stabilization changes for that versioned release |
| `main` | Stable, tagged history. Every commit on `main` is a semver release. | Release PRs only (**merge commit** or fast-forward; never squash/rebase) from a versioned release branch (#1455) |

The `pr-gates` workflow enforces this with a **main-source** check: a PR whose base is `main` fails unless its head branch is `release`, `release-patch`, `release-minor`, `release-major`, or matches `release-v*`. Approvers may apply the `main-source-override` label for a one-off exception (approver enforcement follows lifecycle config when present).

**Release window (merge freeze):** while the active standing Next Release issue (label `Release`, title contains `Next Release`) carries `release-window:open`, `pr-gates` fails any PR whose **base** is `release`, `release-patch`, `release-minor`, or `release-major`. There is no active Next Release → the window is treated as closed (no block). `gh plate release cut` applies `release-window:open` after a successful cut; `gh plate release finalize` closes the window on that issue first, then ensures a fresh standing Next Release (labels: `Release` only — the window stays closed until the next cut). Approvers may apply `release-window-override` on a PR for a one-off exception (#1439).

**Legacy single `release` branch** remains supported during transition for repos not yet adopting the multi-track model. See the design doc and migration guidance in the release-ceremony-refinement fragment for adoption steps. The persistent `release` (when present) continues to point at the tip that will become (or most recently became) a tag.

**For agents opening PRs:** MUST run `gh plate release status` (or inspect the issue's semver track label) *proactively as the very first step before any targeting, branch decision, or `gh pr create`*. Include `--base <base>` explicitly (where <base> is the value reported by `gh plate release status`, e.g. `release` for legacy or `release-minor` etc. for multi-track). Defaulting to `main` is incorrect for ongoing Feature/Bug work and will require manual retargeting. The "Open a PR" steps in the Feature and Bug work loops above take precedence for execution. (Addresses #513.)

### Epic-close ceremony

When all child issues for an Epic are resolved:
1. Confirm all Feature/Bug PRs for the Epic are merged into `epic/<name>`.
2. Post a summary comment on the Epic issue with outcomes and any migration notes.
3. Open a PR from `epic/<name>` → `release`. Label it `Feature` or `Documentation` as appropriate.
4. Human reviews and squash-merges into the release track. The Epic issue closes via `Closes #N` in the PR body.

### Release ceremony (refined multi-track model)

See the detailed steps in the **Release** work loop table above and the full model in `docs/design/release-ceremony-refinement.md`. High-level flow:

1. Standing "Next Release" issue exists and is the target for Epics (via sidebar links) and track-labeled work (Major/Minor/Patch labels drive landing on the matching `release-major` / `release-minor` / `release-patch` permissive next- branches).
2. Packaging (the decision + freeze + version lock point): determine semver, create versioned `release-vX.Y.Z` branch (combining tracks for minor/major as appropriate), rename the issue to the concrete version, immediately spawn a fresh "Next Release" issue.
3. Release PR from the versioned branch → `main` (this PR uses the `Documentation` PR type label **and** the `Release` label; the latter plus the `release-v*` / legacy `release` branch context triggers the differentiated heavy CI jobs and prevents the skip described in #532).
4. Human merge with **Create a merge commit** (`gh pr merge <N> --merge`) or fast-forward. Do not squash or rebase-merge Release PRs; squash breaks post-tag fast-forward of standing release-track branches (#1455).
5. GitHub Actions tags the merged Release PR commit (`vX.Y.Z`), then finalization handles configurable downstream triggers (`.plate/` + extensions), ensures next Next Release exists, and fast-forwards (or admin-resets) the relevant branches as needed.
6. GitHub Release created from the aggregated notes.

Legacy single-`release` + upfront versioned Release issue flow remains valid for transition (see migration guidance in the release-ceremony-refinement fragment).

### Standing release-track state

- `gh plate bootstrap --apply` is the canonical owner for initial standing release-track branches (`release-major`, `release-minor`, `release-patch`, and legacy `release`) and related bootstrap-time release metadata.
- PLATE should maintain exactly one open `Release` issue titled `Next Release` as the standing target for release negotiation. Do not create separate default Major/Minor/Patch release issues; track intent belongs on work items via labels and the matching branches.
- Treat a repository as never initialized only when release-track branches, Release issue history, and versioned release history are all absent. Partial standing state or missing artifacts after prior release activity is drift and should be repaired, not re-bootstrapped blindly.
- Until dedicated init/repair automation exists, repair missing standing state by running bootstrap for branches/labels, creating exactly one `Next Release` issue manually, and verifying the result with `gh plate release status`.

### Release branch protection guidance

The next-* (permissive integration) and versioned `release-vX.Y.Z` branches (and the legacy single `release` during transition) should be protected with:
- PRs required (no direct push).
- Appropriate source restrictions (e.g. epic/* or track-consistent branches for next-*; limited stabilization changes for versioned branches).
- Status checks: same as `main` (plus the differentiated heavy CI jobs for Release contexts).

See the design doc and bootstrap output for current recommended protection details. The "only epic-close" restriction is relaxed for the multi-track model in favor of track labels + the final Release PR gate.

### Automated post-tag fast-forward (`release.yml`) and credentials

After a Release PR merges to `main`, `.github/workflows/release.yml` fast-forwards standing release-track branches (`release-major`, `release-minor`, `release-patch`, legacy `release`) to the new tag using **non-destructive** `git push` ref updates only (never `--force`).

**GitHub App path (recommended on personal/user-owned repos):** Branch rulesets often block the default `GITHUB_TOKEN` from pushing directly to protected release branches. Configure a dedicated GitHub App (no webhook required):

1. Create the App with **Contents** (read/write), **Issues** and **Pull requests** (read/write), and **Actions** plus **Checks** (read).
2. Install the App on the repository that runs PLATE.
3. Add repository secrets **`PLATE_APP_ID`** (numeric App ID) and **`PLATE_APP_PRIVATE_KEY`** (PEM). Names are fixed in the shipped workflow; to use different names, fork or patch `.github/workflows/release.yml` and keep the values in repository secrets.
4. In repository **Settings → Rules → Rulesets**, edit the ruleset that covers your standing release branches: add the App as a **bypass actor** with **Always allow** so the post-merge job can update those refs without a pull request.

**Organization repositories:** You may alternatively add `github-actions` as a bypass actor on that ruleset if org policy allows, and rely on the default token—then the App secrets are optional and the workflow skips only the push (with an explicit warning) when secrets are absent.

**Free / unbranded path:** There is no requirement to use a public App name; you can use a fine-grained PAT stored in repository secrets and a small custom workflow, or have a maintainer run `gh plate release finalize <ver> --apply` (or an admin-level manual `git push` fast-forward) when automation cannot bypass protection.

If **`PLATE_APP_ID`** or **`PLATE_APP_PRIVATE_KEY`** is missing, the fast-forward job logs a workflow warning and does not attempt the push, so the workflow stays green while you add credentials or perform a manual fast-forward.

**Merge method on `main` (recommended, maintainer-only):** Optionally restrict allowed merge methods on `main` to merge commits only in repository Settings → Rules. PLATE documents this recommendation; it does not change branch protection or rulesets automatically.

### Fragment authoring

Every Feature (or process-changing) PR that changes PLATE process, templates, or agent surfaces must include a fragment under `.agentic/releases/unreleased/<slug>.json`. See `.agentic/releases/unreleased/README.md` for the schema and field guide. This includes all changes in a Release ceremony refinement Epic (new labels, branch model updates, CI conditions, tooling enhancements, milestone rules, .plate config, etc.). Fragments accumulate across the Epic's lifetime and are swept into the versioned directory at release-cut time.

The canonical design artifact for Release ceremony changes lives in `docs/design/release-ceremony-refinement.md`.

**Note from velocity polish (Q&A #580 / #569 / #556, fragments):** New support for PLATE Issue states (status:implemented auto-set on merge to release/next track; see children #582, workflow, labels). Ceremony foundation includes agent-only feedback gate, auto Closes block from fragments in cut (one merge to main closes addressed), enhanced finalize (#592 wires the gh release create + guarded reset + assets into finalize + core helpers). Guidance architecture enforced (thin persona; see #536 updates). See updated children #535/#583 etc and pending fragments for details. Update this section on future ceremony changes.
