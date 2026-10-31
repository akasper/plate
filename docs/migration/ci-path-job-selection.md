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
# Every optional job id (must include every module job when set)
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
      - "src/**/api.py"
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
under `depends_on` are included (dependents run). Patterns such as
`src/**/api.py` match zero or more directories (including `src/api.py`).

**Policies:**

- `unmatched_paths: fail` — exit non-zero when any changed path is outside every
  module (prevents “green skip” when the map is incomplete).
- `empty_selection: run_all` — if selection yields zero jobs but paths changed,
  fall back to the full `all_jobs` list.
- When `all_jobs` is set, it must list every job id referenced by modules.

## Helper

```bash
export PYTHONPATH=src   # plate-core monorepo only; adopters pip install plate-core
python3 scripts/plate/select_ci_jobs.py --paths src/backend/foo.py
python3 scripts/plate/select_ci_jobs.py --base origin/main
PLATE_CI_FULL_SUITE=1 python3 scripts/plate/select_ci_jobs.py --base origin/main
```

Without `--paths` or `--base`, the helper fails closed when selection is enabled
(so a missing action input cannot yield an empty diff and skip every optional job).

Composite action (after a full-history checkout):

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: ./.github/actions/plate-select-ci-jobs
  id: ci_select
  with:
    base-ref: origin/${{ github.base_ref }}
```

On pull requests, `github.base_ref` is a branch name only; the checkout step
must fetch enough history that `origin/<base>` resolves (for example
`fetch-depth: 0` as above). Alternatively pass
`github.event.pull_request.base.sha` as `base-ref` with `head-ref: HEAD`.

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
         env:
           SELECT_RESULT: ${{ needs.select.result }}
           SELECT_SAFETY: ${{ needs.select.outputs.safety }}
           RUN_ALL: ${{ needs.select.outputs.run_all }}
           JOBS_JSON: ${{ needs.select.outputs.jobs_json }}
           UNIT_BACKEND: ${{ needs.unit-backend.result }}
           UNIT_FRONTEND: ${{ needs.unit-frontend.result }}
           INTEGRATION: ${{ needs.integration.result }}
         run: |
           set -euo pipefail
           if [[ "$SELECT_RESULT" != "success" ]]; then
             echo "select job failed" >&2
             exit 1
           fi
           if [[ "$SELECT_SAFETY" != "ok" ]]; then
             echo "CI job selection unsafe" >&2
             exit 1
           fi
           selected=()
           if [[ "$RUN_ALL" == "true" ]]; then
             selected=(unit-backend unit-frontend integration)
           else
             mapfile -t selected < <(python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin)))' <<<"$JOBS_JSON")
           fi
           declare -A results=(
             [unit-backend]="$UNIT_BACKEND"
             [unit-frontend]="$UNIT_FRONTEND"
             [integration]="$INTEGRATION"
           )
           for job in unit-backend unit-frontend integration; do
             result="${results[$job]}"
             if printf '%s\n' "${selected[@]}" | grep -qx "$job"; then
               if [[ "$result" != "success" ]]; then
                 echo "$job finished with $result (selected)" >&2
                 exit 1
               fi
             elif [[ "$result" != "skipped" ]]; then
               echo "$job finished with $result (not selected)" >&2
               exit 1
             fi
           done
           echo "Aggregate test gate passed."
   ```

Never rename or remove the required check contexts `labels`, `test`, or
`pr-gates`. Unselected optional jobs must finish as `skipped`; selected jobs must
be `success`.

## Scheduled full suite on `main`

When selection is enabled for pull requests, run the full job list on a schedule
against `main` so a bad map is caught within a day. Copy
`docs/examples/plate-ci-scheduled-full-suite.workflow.yml.example` from the template
payload into `.github/workflows/` (only after you wire optional jobs) and set
`full-suite: true` on the select step (or export `PLATE_CI_FULL_SUITE=1`).

Example files under `docs/examples/` are **not** registered as workflows until you
copy them into `.github/workflows/`.

## Related

- [adoption-guide.md](./adoption-guide.md) — aggregate `test` job pattern
- [actions-cost-rollout.md](./actions-cost-rollout.md) — required check names
