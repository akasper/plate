# Path-based CI job selection

PLATE ships generic pieces so adopters can run only the CI jobs that match
touched modules, instead of paying for a full matrix on every pull request.
The idea follows path-to-job mapping described by
[Kun Chen on X](https://x.com/kunchenguid/status/2115565245293039814)
(module-scoped jobs and interface surfaces) and safety patterns from
[Owen Gretzinger on X](https://x.com/owengretzinger/status/2116292908303393032)
(test the skip logic and schedule a full suite on `main` so missed dependencies
surface quickly).

Parent design: Epic #1268. Implementation: #1270.

## Configuration

Author **one** of:

| Location | Format |
|---|---|
| `.agentic/ci-path-jobs.yml` | YAML (recommended) |
| `.plate` → `ci.path_jobs` | JSON object (same fields as YAML root) |

When the file is missing or `enabled: false`, the helper selects **all** jobs
(`run_all: true`) so existing workflows behave unchanged.

### Schema (version `1`)

```yaml
version: "1"
enabled: true
# When a changed file matches no module: run_all (safe default) or fail
unmatched_paths: run_all
# When modules match but no job ids would run: run_all or fail
empty_selection: run_all
# Optional job ids skipped by selection; required contexts stay separate
all_jobs:
  - unit-backend
  - unit-frontend
  - integration
modules:
  backend:
    paths:
      - "src/backend/**"
    jobs:
      - unit-backend
  api_surface:
    interface: true
    paths:
      - "src/backend/public_api.py"
    jobs:
      - unit-backend
  frontend:
    paths:
      - "src/frontend/**"
    depends_on:
      - api_surface
    jobs:
      - unit-frontend
```

**Cross-module interfaces:** set `interface: true` on a module whose paths are
shared contracts. When those paths change, jobs for every module listing that id
under `depends_on` are included (dependents run).

**Policies:**

- `unmatched_paths: fail` — exit non-zero when any changed path is outside every
  module (prevents “green skip” when the map is incomplete).
- `empty_selection: run_all` — if selection yields zero jobs but paths changed,
  fall back to the full `all_jobs` list.

## Helper

```bash
export PYTHONPATH=src   # plate-core monorepo only; adopters pip install plate-core
python3 scripts/plate/select_ci_jobs.py --paths src/backend/foo.py
python3 scripts/plate/select_ci_jobs.py --base origin/main
PLATE_CI_FULL_SUITE=1 python3 scripts/plate/select_ci_jobs.py --base origin/main
```

Composite action (after checkout):

```yaml
- uses: ./.github/actions/plate-select-ci-jobs
  id: ci_select
  with:
    base-ref: ${{ github.base_ref }}
```

Outputs: `run_all`, `jobs_json`, `jobs_csv`, `safety`. The script exits `1` when
`safety` is `fail` so the workflow cannot report success while every optional job
was skipped.

## Required checks (`labels`, `test`, `pr-gates`)

Path selection applies to **optional** product jobs only. Branch protection must
still see passing contexts named exactly `labels`, `test`, and `pr-gates`.

1. Keep PLATE process jobs (`labels`, imported `pr-gates`) always on.
2. Split product work into named jobs (`unit-backend`, `integration`, …).
3. Gate each optional job:

   ```yaml
   unit-backend:
     needs: [select]
     if: >-
       needs.select.outputs.run_all == 'true' ||
       contains(fromJSON(needs.select.outputs.jobs_json), 'unit-backend')
   ```

4. Add an aggregate job whose **job id** is `test` (not a display `name:`) so
   skipped optional jobs still satisfy the required `test` context:

   ```yaml
   test:
     needs: [select, unit-backend, unit-frontend, integration]
     if: always()
     runs-on: ubuntu-latest
     steps:
       - shell: bash
         run: |
           set -euo pipefail
           if [[ "${{ needs.select.outputs.safety }}" == "fail" ]]; then
             echo "CI job selection unsafe" >&2
             exit 1
           fi
           for job in unit-backend unit-frontend integration; do
             result="${{ needs[job].result }}"
             if [[ "$result" != "success" && "$result" != "skipped" ]]; then
               echo "$job finished with $result" >&2
               exit 1
             fi
           done
           echo "Aggregate test gate passed."
   ```

Never rename or remove the required check contexts `labels`, `test`, or
`pr-gates`. Skipped optional jobs must finish as `skipped`, not `failure`, so the
aggregate `test` job can pass.

## Scheduled full suite on `main`

When selection is enabled for pull requests, run the full job list on a schedule
against `main` so a bad map is caught within a day. Copy
`.github/workflows/plate-ci-scheduled-full-suite.example.yml` from the template
payload and set `full-suite: true` on the select step (or export
`PLATE_CI_FULL_SUITE=1`).

## Related

- [adoption-guide.md](./adoption-guide.md) — aggregate `test` job pattern
- [actions-cost-rollout.md](./actions-cost-rollout.md) — required check names
