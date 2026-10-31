# CI/CD split guidance for heavy jobs

Parent design: [#1268](https://github.com/akasper/plate/issues/1268) (CI speed and cost at agent pace). This page explains how adopters move **heavy or redundant** work (extra OS matrices, installer builds, long integration suites) off the default pull-request path while keeping branch protection honest.

**Idea credit:** Kun Chen described splitting fast PR feedback from slower post-merge validation so teams stop paying full-matrix minutes on every agent-driven push ([summary on X](https://x.com/kunchenguid/status/2115565245293039814)). The patterns below apply that idea to PLATE repos that already require `labels`, `test`, and `pr-gates` on every PR.

Related operator docs:

- [Actions cost rollout](./actions-cost-rollout.md) — guards, merged `pr-gates`, and rollout order before you reshape jobs.
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

PLATE’s own `heavy-release` job in `.github/workflows/ci.yml` is an example of **context-gated** work: it runs only when head/base refs look like release packaging, not on ordinary feature PRs to permissive next branches.

## Required checks and skipped jobs

Branch protection treats **Skipped** contexts differently from **Success**. If a job listed as required never starts because `if:` is false, merges can block or behave inconsistently across repositories.

**Rules:**

1. **Only list contexts as required when that job runs on every PR** you intend to merge (for PLATE adopters: `labels`, `test`, `pr-gates` plus your own fast `test` implementation).
2. **Do not** add heavy matrix or installer jobs to required checks if they run only on `push` or release branches.
3. When a single workflow file must serve both PR and post-merge events, make the **required job succeed on PR** even when heavy steps are deferred — run an explicit no-op step on `pull_request` before skipping expensive work.

<!-- PLATES-CORE:BEGIN ci-cd-split-heavy-jobs -->
**Splitting heavy CI without weakening gates**

- Keep required PR contexts limited to fast jobs that always execute on `pull_request` (for PLATE: `labels`, `test`, `pr-gates`).
- Move matrices, installers, and long scans to `push` (post-merge), `schedule`, or release-scoped workflows; do not add those job names to branch protection unless they run on every PR.
- If one workflow serves both PR and post-merge, add a PR-only step that exits successfully and documents the deferral, then guard expensive steps with `if:` so the **job** still completes with success on PRs — never leave a required context in `Skipped` state.
- Re-run post-merge/pre-release pipelines when integration branches move; treat failures there as release blockers even when PRs were green.
- Risk: deferring platform-specific builds can hide OS-only failures until merge or release — document that tradeoff for your team.
<!-- PLATES-CORE:END ci-cd-split-heavy-jobs -->

## Worked example: fast PR test + post-merge matrix

The following pattern uses **two jobs in one workflow**. `test-fast` is the required context on PRs. `test-matrix` runs only after merge to `main` (adjust branches to match your model).

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

**Branch protection:** require `test-fast` (or your workflow’s job name mapped to the `test` context your repo uses). Do **not** require `test-matrix`.

### Worked example: installer build deferred but job stays green on PR

When you must keep one job name for historical reasons, use an explicit PR deferral step:

```yaml
  package-installers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: PR path — record deferral (required job must succeed)
        if: github.event_name == 'pull_request'
        run: |
          echo "Installer builds run on push to main and on Release PRs only."
      - name: Build installers (post-merge / release)
        if: github.event_name != 'pull_request'
        run: ./scripts/build-installers.sh
```

On pull requests the first step runs and the job completes **Success**. On push, the build runs. Do not mark this job required unless every PR needs it — prefer a separate release workflow for packaging.

## Risk note

Deferring heavy platform work improves PR latency and Actions spend, but **failures that only appear on one OS or in packaging** may not surface until post-merge CI or a Release PR. Mitigations:

- Run post-merge matrix on every merge to your primary integration branch, not only on tags.
- Block release cuts when post-merge or `heavy-release` workflows fail.
- Keep a short, PR-local smoke test that exercises the most failure-prone platform if you drop it from the PR matrix.

## Adoption checklist

1. Inventory PR workflows and list current **required** status check names (`Settings → Branches` or `gh api` rulesets).
2. Classify each job as PR-gate vs post-merge vs pre-release; remove heavy names from required checks if they are not PR-always.
3. Implement deferral with successful PR completion (see PLATES-CORE block above).
4. Verify on a test PR: required contexts show **Success**, not **Skipped** or missing.
5. Merge a canary change and confirm post-merge matrix/installer workflows fire and notify the right channel.

## Related PLATE artifacts

- Fragment: `.agentic/releases/unreleased/ci-cd-split-guidance-1269.json`
- Template copy: `src/plate_core/template_payload/docs/migration/ci-cd-split-guidance.md` (keep identical to this file)
