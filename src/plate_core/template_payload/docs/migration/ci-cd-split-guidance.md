# CI/CD split guidance for heavy jobs

Parent design: [#1268](https://github.com/akasper/plate/issues/1268) (CI speed and cost at agent pace). This page explains how adopters move **heavy or redundant** work (extra OS matrices, installer builds, long integration suites) off the default pull-request path while keeping branch protection honest.

**Idea credit:** Kun Chen described splitting fast PR feedback from slower post-merge validation so teams stop paying full-matrix minutes on every agent-driven push ([summary on X](https://x.com/kunchenguid/status/2115565245293039814)). The patterns below apply that idea to PLATE repos that already require `labels`, `test`, and `pr-gates` on every PR.

Related operator docs:

- [Actions cost rollout](https://github.com/akasper/plate/blob/main/docs/migration/actions-cost-rollout.md) — guards, merged `pr-gates`, and rollout order before you reshape jobs (upstream in `akasper/plate`; not shipped in the default template payload).
- [Self-hosted runners](./self-hosted-runners.md) — optional local compute; splitting stages still applies on hosted runners.

## What belongs on the PR path

Keep PR CI **small and deterministic**. Required checks should answer: “Is this change safe to merge into the integration branch?”

| Keep on PR (typical required contexts) | Why |
|---|---|
| `labels`, `test`, `pr-gates` | PLATE enforcement and fast product/unit signal |
| One primary OS for compile/test | Catches most regressions agents introduce |
| Short smoke steps tied to touched areas | Bounded cost; re-run on every synchronize |

Do **not** remove or downgrade these to optional when splitting heavy work. Splitting means **moving extra jobs elsewhere**, not deleting gates.

## What to move post-merge or pre-release

| Candidate | Better stage | Trigger |
|---|---|---|
| Full OS / browser matrix | Post-merge to `main` or track branch | `push` to integration branches |
| Installer / packaging for every platform | Pre-release or Release PR | `release-v*`, `Release`-labeled PR, or tag workflow |
| Security scans with long cold start | Nightly or post-merge | `schedule` or `push` to `main` |
| Redundant duplicate of `test` | Delete or merge | N/A — avoid running the same suite twice on PR |

PLATE’s own `heavy-release` job in `.github/workflows/ci.yml` is **context-gated**, not limited to versioned release branches only. Its job-level `if:` runs when the PR head is `release` or any `release-*` head ref, **or** when the PR **base** starts with `release-` (including `release-major`, `release-minor`, and `release-patch`). Feature work targeting those permissive next branches can therefore see `heavy-release` on the PR path. Do not copy that condition expecting packaging-only execution on `release-v*` alone.

## Required checks: skipped jobs vs pending checks

Two different GitHub behaviors matter when splitting stages ([control jobs with conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)):

| Situation | Typical check status on a PR | Branch protection |
|---|---|---|
| Required job runs and succeeds | Success | Satisfied |
| Required job is **skipped** because a **job-level** `if:` is false | Skipped | Usually **satisfied** (skipped required jobs count as passing) |
| Required context comes from a workflow that **does not run at all** on this event (workflow `on:` branch/path filters, etc.) | Missing / **Pending** | **Blocks merge** until the check reports Success |

**Rules:**

1. **Only list contexts as required when the workflow that produces them runs on every PR** you intend to merge (for PLATE adopters: `labels`, `test`, `pr-gates` plus your fast `test` job).
2. **Do not** require check names from workflows triggered only on `push`, tags, or narrow branches—those workflows often never start on `pull_request`, leaving required checks **pending**.
3. **Do not** require heavy matrix or installer job names if those jobs use job-level `if:` to skip on most PRs; prefer a separate post-merge workflow instead of a required name that is usually skipped.
4. **Optional pattern:** When one workflow must run on both `pull_request` and `push` and a job name is required on PRs, you may add a lightweight PR-only step so expensive steps stay off the PR path while the job still runs—this is a **policy/clarity** choice, not something GitHub demands when the job is simply not required.

<!-- PLATES-CORE:BEGIN ci-cd-split-heavy-jobs -->
**Splitting heavy CI without weakening gates**

- Keep required PR contexts limited to fast jobs whose **workflows always run** on `pull_request` (for PLATE: `labels`, `test`, `pr-gates`).
- Move matrices, installers, and long scans to `push` (post-merge), `schedule`, or release-scoped workflows; do not add those check names to branch protection unless that workflow runs on every PR you merge.
- Distinguish **job skipped** (job-level `if:`; usually OK for a required job) from **workflow not run** (filters; leaves required checks **pending**—fix triggers or remove the name from required checks).
- Re-run post-merge/pre-release pipelines when integration branches move; treat failures there as release blockers even when PRs were green.
- Risk: deferring platform-specific builds can hide OS-only failures until merge or release — document that tradeoff for your team.
<!-- PLATES-CORE:END ci-cd-split-heavy-jobs -->

## Worked example: fast PR test + post-merge matrix

The following pattern uses **two jobs in one workflow**. `test-fast` is the required context on PRs. `test-matrix` runs only on **`push`** (post-merge) to the listed integration branches—not on `pull_request`.

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main, release, release-minor, release-major, release-patch]

concurrency:
  group: ci-${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  test-fast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Unit tests (PR gate)
        run: python -m unittest discover -s tests -p "test_*.py"

  test-matrix:
    needs: test-fast
    if: github.event_name == 'push'
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Unit tests (${{ matrix.os }})
        run: python -m unittest discover -s tests -p "test_*.py"
```

**Branch protection:** require `test-fast` (or your workflow’s job name mapped to the `test` context your repo uses). Do **not** require `test-matrix` (the workflow still runs on PRs, but that job is skipped on `pull_request`—do not list it as required unless you intend that skip semantics).

### Worked example: post-merge installer build (not on pull requests)

This job runs **only on `push`**. It does **not** run on Release PRs or any other `pull_request` event. Use a separate release workflow (or label/branch-aware `if:`) when installers must build during Release PR validation.

```yaml
  package-installers:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build installers (post-merge to integration branches)
        run: ./scripts/build-installers.sh
```

Do not mark `package-installers` as a required PR check—the workflow may run on PRs for other jobs, but this job does not execute on `pull_request`.

### Optional pattern: same job name required on PR and heavy work on push

If branch protection already requires `package-installers` and you cannot split workflows yet, run a cheap PR step and gate the build (policy choice for clarity, not a GitHub requirement for skipped jobs):

```yaml
  package-installers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: PR — defer installer build
        if: github.event_name == 'pull_request'
        run: echo "Installers build on push; see post-merge workflow."
      - name: Build installers
        if: github.event_name == 'push'
        run: ./scripts/build-installers.sh
```

## Risk note

Deferring heavy platform work improves PR latency and Actions spend, but **failures that only appear on one OS or in packaging** may not surface until post-merge CI or release packaging workflows run. Mitigations:

- Run post-merge matrix on every merge to your primary integration branch, not only on tags.
- Block release cuts when post-merge or `heavy-release` workflows fail.
- Keep a short, PR-local smoke test that exercises the most failure-prone platform if you drop it from the PR matrix.

## Adoption checklist

1. Inventory PR workflows and list current **required** status check names (`Settings → Branches` or `gh api` rulesets).
2. Classify each job as PR-gate vs post-merge vs pre-release; remove required names whose workflows do not run on every PR (avoid **pending** checks).
3. Prefer separate post-merge workflows over required jobs that are usually skipped on PRs.
4. Verify on a test PR: required contexts show **Success** (or acceptable **Skipped** only for optional/non-required jobs—not **Pending**).
5. Merge a canary change and confirm post-merge matrix/installer workflows fire and notify the right channel.

## Related PLATE artifacts

- Fragment: `.agentic/releases/unreleased/ci-cd-split-guidance-1269.json`
- Template copy: `src/plate_core/template_payload/docs/migration/ci-cd-split-guidance.md` (keep identical to this file)
