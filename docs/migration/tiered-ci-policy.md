# Tiered CI policy and job selection

Parent design: [#1268](https://github.com/akasper/plate/issues/1268). Builds on
[path-based job selection](./ci-path-job-selection.md) (#1270), CI/CD split guidance
(#1269), and policy decisions on [#1332](https://github.com/akasper/plate/issues/1332).

This page documents **policy and helpers only**. It does not change `.github/workflows`
required checks (`labels`, `test`, `pr-gates`), branch protection, or what the plate
monorepo runs today. Wiring tiered selection into live workflows needs owner approval
(#1284 follow-up).

## Policy summary

1. **PLATE process checks** (`labels`, issue-link / closes-issue, feedback-resolution /
   `pr-gates`) run on **every** pull request. Tiered selection applies to **optional**
   product jobs only (same split as #1270).

2. **New tests and CI steps** introduced in a PR must pass in that PR. Changes under
   `.github/workflows/**`, the path-to-jobs map (`.agentic/ci-path-jobs.yml`), the tier
   policy file (`.agentic/ci-policy.yml`), or **newly added** test paths force the
   affected optional jobs to run even when tier caps would otherwise skip them.

3. **Job size** (estimated Actions cost per run, from `gh plate ci audit` — #1282):
   - **small**: about **≤ $0.10**
   - **medium**: about **$0.10–$2.00**
   - **large**: **> $2.00**

   Defaults live in config; adopters override `cost_tiers` and classify each optional
   job id in `job_sizes`.

4. **Ordinary PRs** run all **small** jobs plus path-selected jobs up to **medium**
   (large jobs skip unless forced).

5. **Release PRs** (level from the Release issue / release fragment):
   - **patch** — medium or less
   - **minor** — large or less
   - **major** — everything

6. **Nightly** (scheduled full suite on `main`) — everything.

7. **Skipped jobs** still report success via an aggregate required job (see
   [ci-path-job-selection.md](./ci-path-job-selection.md)); branch protection stays
   satisfied.

8. **Heavy jobs** may move post-merge or pre-release per
   [ci-cd-split-guidance.md](./ci-cd-split-guidance.md). A release still needs a green
   post-merge run on the tagged commit.

9. Report Actions minutes **before and after** CI changes (`gh plate ci audit`).

## Configuration

Author **one** policy file:

| Location | Format |
|---|---|
| `.agentic/ci-policy.yml` | YAML (recommended) |
| `.plate` → `ci.policy` | JSON object (same fields) |

Path-to-jobs config remains in `.agentic/ci-path-jobs.yml` (or `.plate` →
`ci.path_jobs`). When policy `enabled: false` or the file is missing, the tiered
helper behaves like plain path selection (#1270).

### Schema (version `1`)

```yaml
version: "1"
enabled: true
cost_tiers:
  small:
    max_usd: 0.10
  medium:
    min_usd: 0.10
    max_usd: 2.00
  large:
    min_usd: 2.00
job_sizes:
  lint-fast: small
  unit-backend: medium
  integration: large
  e2e: large
force_run:
  workflow_globs:
    - ".github/workflows/**"
  map_paths:
    - ".agentic/ci-path-jobs.yml"
    - ".agentic/ci-path-jobs.yaml"
    - ".agentic/ci-policy.yml"
    - ".agentic/ci-policy.yaml"
  test_path_globs:
    - "tests/**"
    - "**/test_*.py"
    - "**/*_test.py"
  on_workflow_change: all_jobs
  on_map_change: all_jobs
```

Every id in `all_jobs` (path map) must appear in `job_sizes` when policy is enabled.

## Helper

```bash
export PYTHONPATH=src   # plate-core monorepo; adopters pip install plate-core
python3 scripts/plate/select_tiered_ci_jobs.py \
  --paths src/foo.py \
  --pr-kind ordinary
python3 scripts/plate/select_tiered_ci_jobs.py \
  --base origin/main \
  --pr-kind release_minor
python3 scripts/plate/select_tiered_ci_jobs.py \
  --base origin/main \
  --pr-kind nightly
```

`--pr-kind` values: `ordinary`, `release_patch`, `release_minor`, `release_major`,
`nightly`. JSON output includes `selection` (same shape as #1270) and `tiered` metadata
(`forced_jobs`, `tier_filtered_out`, etc.). Exit codes match `select_ci_jobs.py`
(unsafe path selection → exit `1`).

Python API: `plate_core.ci_tiered_policy.select_tiered_ci_jobs` and
`tiered_selection_for_repo`.

## Related

- [ci-path-job-selection.md](./ci-path-job-selection.md) — modules, interfaces, aggregate `test` job
- [ci-cd-split-guidance.md](./ci-cd-split-guidance.md) — post-merge heavy jobs (#1269)
- [ci-speed-checklist.md](./ci-speed-checklist.md) — adoption checklist (#1283)
- Design [ci-audit-command.md](../design/ci-audit-command.md) — measuring job cost (#1282)
