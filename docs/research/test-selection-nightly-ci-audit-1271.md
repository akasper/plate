# Research: test selection and a nightly CI-audit routine

- **Issue:** [#1271](https://github.com/akasper/plate/issues/1271)
- **Parent design:** [#1268](https://github.com/akasper/plate/issues/1268) (CI speed and cost at agent pace)
- **Researched by:** Cursor cloud agent (PLATE)
- **Date:** 2026-10-31
- **Status:** Completed

## Research question

How can a nightly routine read past CI runs and suggest test-selection changes, and report the costliest jobs by minutes? Compare simple approaches (coverage maps, path heuristics, flaky-test history), describe adopter opt-in, and estimate the cost of running the audit itself.

**Idea credit (summarized in our own words):** Kun Chen [described on X](https://x.com/kunchenguid/status/2115565245293039814) a loop where CI cost and latency are managed at agent pace: narrow what runs on each change, measure where minutes go, and feed that back into selection rules. PLATE already ships pieces for job-level path selection ([#1270](https://github.com/akasper/plate/issues/1270)) and job timing splits ([#1282](https://github.com/akasper/plate/issues/1282) / `gh plate ci audit`). This note closes the gap for **test-level** selection and a **repeatable audit routine** without repeating the checklist or command reference docs.

## Sources

- [Kun Chen on X (Oct 2026)](https://x.com/kunchenguid/status/2115565245293039814) — module-scoped CI and feedback loops (summarized above).
- Design [#1268](https://github.com/akasper/plate/issues/1268) — constraints (required checks stay green; generic infrastructure only; stdlib unittest in PLATE core).
- [Path-based CI job selection](../migration/ci-path-job-selection.md) — `.agentic/ci-path-jobs.yml`, `select_ci_jobs.py`, composite action ([#1270](https://github.com/akasper/plate/issues/1270)).
- [CI speed checklist](../migration/ci-speed-checklist.md) — adopter playbook; points to audit and minutes reporting ([#1283](https://github.com/akasper/plate/issues/1283)).
- [CI audit command](../design/ci-audit-command.md) — `gh plate ci audit` behavior, buckets, JSON shape ([#1282](https://github.com/akasper/plate/issues/1282)).
- Implementation: `src/plate_core/ci_audit.py`, `tests/test_ci_audit.py`.
- Task [#1272](https://github.com/akasper/plate/issues/1272) — cross-repo minutes ranking (owner Task; out of scope for automation here).

## Findings

### 1. Three ways to shrink test work on a PR

These are complementary; adopters usually start with heuristics and add maps or history when pain justifies complexity.

| Approach | What it uses | Strengths | Weaknesses | Fit with PLATE today |
|----------|--------------|-----------|------------|----------------------|
| **Path heuristics** | Changed file paths → test modules or markers | Cheap, no extra CI artifacts; aligns with [#1270](https://github.com/akasper/plate/issues/1270) job maps | Coarse: one shared file may pull many tests; easy to under-select without `fail` policies | **Job** maps exist; **test** maps are adopter YAML + a small helper (same pattern as `ci-path-jobs.yml`) |
| **Coverage maps** | Prior full-suite run: line/file coverage → tests that executed those lines | Tighter than directory guesses when coverage is good | Needs stored coverage JSON per branch/tool; stale maps miss new tests; setup cost on first run | Not shipped; adopter stores artifacts (e.g. `coverage.xml` + index) and a script selects `pytest`/`go test` packages |
| **Flaky-test history** | Past workflow conclusions, re-runs, `conclusion: failure` then success on same commit | Surfaces tests that waste minutes without catching regressions | Does not reduce scope by itself; informs quarantine, order, or `pytest --lf` style policies | Derivable from the same Actions API `gh plate ci audit` already calls (job `conclusion`, run list); no PLATE aggregator yet |

**Path heuristics (test level):** Mirror the job map schema: modules with `paths` globs and a `tests` list (files, directories, or pytest `-k` expressions). Run the full suite on `main` on a schedule (already recommended in the job-selection doc) so under-selection is caught quickly.

**Coverage maps:** After a nightly or post-merge full run, upload a tool-native coverage report and build a sidecar index (`path prefix → [test ids]`). On PRs, union tests for all touched paths plus tests for any `interface: true` modules (same dependent-run idea as job maps). Regenerate the index when coverage format or layout changes.

**Flaky history:** Over the last *N* runs, score tests (or jobs) with high `(failures + reruns) / attempts`. The nightly routine should **flag** candidates for human quarantine or stricter isolation—not auto-skip required checks. Pair with checklist item 6 (shared worker reset) before blaming “flaky infrastructure.”

### 2. Nightly routine: reuse `gh plate ci audit`, then suggest selection changes

Do **not** reimplement timing math; consume existing output documented in [ci-audit-command.md](../design/ci-audit-command.md).

**Suggested flow (adopter-owned schedule or local cron):**

1. **Baseline minutes by job** — `gh plate ci audit --repo owner/repo --limit 100 --json` (raise `--limit` for quiet repos; default `30` is fine for active agent repos). Read `costliest_jobs[]`: each row aggregates `waiting_minutes`, `setup_minutes`, `running_minutes`, and `total_minutes` for `(workflow_name, job_name)`.
2. **Interpret buckets** — High **waiting** → runner pool or concurrency; high **setup** → cache seeding (checklist §2) or cache hints in the JSON; high **running** → candidate for test/job selection or sharding (checklist §4–§5).
3. **Correlate with changes** — For the top *K* jobs, pull recent runs where those jobs ran and list changed paths (merge commit or PR files). Compare against the adopter’s job map and any test map: paths with no module match are map gaps; modules that never appear in expensive runs might be over-selected.
4. **Emit a human-readable report** — Rank jobs by `total_minutes`, list 3–5 suggested map edits (add path, add `depends_on`, or “run full suite on main only”), and flaky candidates if step 3 includes conclusion stats. Store reports in a private repo path or issue; [#1272](https://github.com/akasper/plate/issues/1272) covers cross-adopter aggregation for PLATE maintainers.
5. **Optional test-selection pass** — If a coverage index exists, diff touched paths against the index and propose narrowing or widening test lists; if only heuristics exist, propose new globs when expensive runs always touch the same directory prefix.

PLATE core could later wrap steps 1–4 in a procedure or CLI subcommand; this research intentionally stops at documented composition of existing tools plus adopter config.

### 3. Adopter opt-in

Nothing runs automatically in a bootstrapped repo until the owner wires it.

| Layer | Opt-in mechanism |
|-------|------------------|
| **Measure** | Install `plate-core` / `gh plate`; run `gh plate ci audit` locally or in CI with `actions: read` on the token. |
| **Job selection** | Add `.agentic/ci-path-jobs.yml` and wire [plate-select-ci-jobs](../migration/ci-path-job-selection.md) into optional jobs; required gates unchanged. |
| **Test selection** | Adopter adds `.agentic/ci-test-selection.yml` (or extends path-jobs with test lists), a small script in `scripts/plate/`, and conditional steps in **non-required** or **scheduled** jobs first. |
| **Nightly** | `workflow_dispatch` + `schedule` cron in the adopter repo, or `.agentic/procedures/` + autonomy when enabled; procedure runs audit JSON and opens a draft issue or commits a report branch. |
| **Safety** | Keep `labels`, `test`, and `pr-gates` required paths running full checks until a human approves narrowed PR jobs; use `PLATE_CI_FULL_SUITE=1` (job helper) or a `main` schedule for full regression ([#1270](https://github.com/akasper/plate/issues/1270)). |

Skipped optional jobs must still satisfy branch protection (passing skip/neutral checks)—same constraint as [#1268](https://github.com/akasper/plate/issues/1268).

### 4. Cost of running the audit itself

| Cost type | Typical magnitude | Notes |
|-----------|-------------------|--------|
| **GitHub REST API** | ~`1 + limit` list calls per run (one `actions/runs` paginated fetch plus one `.../runs/{id}/jobs` per workflow run in the sample) | Default `limit=30` → on the order of tens of requests, well under normal rate limits for a once-per-night cron. |
| **Local / agent time** | Sub-minute for 30 runs on medium repos | Dominated by network latency, not CPU; `--json` output is small. |
| **Actions minutes (if audit runs in CI)** | ~0.5–2 billed minutes on a small Linux runner | One job, no matrix; far cheaper than re-running a full test suite. |
| **Human review** | Main ongoing cost | Audit only **suggests** map changes; misapplied selection saves minutes but risks missed regressions. |

Running the audit nightly on `limit=100` for a busy repo is still inexpensive compared to one redundant full-matrix PR run.

### 5. Comparison summary

- **Fastest to adopt:** path heuristics at job level (already in PLATE) plus manual weekly `gh plate ci audit` review.
- **Best precision per minute saved:** coverage maps, after investing in artifact storage and a full run on `main`.
- **Best for agent stability:** flaky history + worker reset discipline before shrinking scope.
- **Nightly value:** turns [#1282](https://github.com/akasper/plate/issues/1282) output into prioritized edits to maps and schedules, aligned with checklist measurement items ([#1283](https://github.com/akasper/plate/issues/1283), [#1272](https://github.com/akasper/plate/issues/1272)).

## Recommendation

### Smallest first slice

1. **Manual cadence (no new PLATE code):** Weekly `gh plate ci audit --limit 50 --json`, save `costliest_jobs`, and adjust `.agentic/ci-path-jobs.yml` using [ci-path-job-selection.md](../migration/ci-path-job-selection.md).
2. **Keep full regression on `main`:** Scheduled workflow with `PLATE_CI_FULL_SUITE=1` or equivalent so narrowed PR jobs cannot drift unnoticed.
3. **Document test-level globs in repo** (single YAML file, no new dependency): one module → one test directory; run via existing test runner flags in an **optional** CI job only after one green week of audit reports.

Defer coverage-index generation and flaky scoring to follow-up Features once the job map and audit habit exist.

### Suggested follow-up issues (titles only — not filed)

1. **Feature: `gh plate ci suggest-maps` — rank costliest jobs and diff against ci-path-jobs.yml**
2. **Feature: template `.agentic/ci-test-selection.example.yml` and select_tests.py helper**
3. **Feature: scheduled procedure template for nightly ci audit JSON + issue comment**
4. **Research: coverage artifact index format for Python and Node adopters**

## Verification

This artifact is documentation only. Related implementation tests:

```bash
PYTHONPATH=src python3 -m unittest tests.test_ci_audit tests.test_ci_path_jobs
```
