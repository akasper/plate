# CI speed checklist for adopters

Use this page when CI is the bottleneck at agent pace: slow feedback burns Actions minutes and blocks merge loops. The checklist is generic infrastructure guidance (Epic [#1268](https://github.com/akasper/plate/issues/1268), Documentation [#1283](https://github.com/akasper/plate/issues/1283)). Each adopter applies items in its own workflows and config; PLATE does not prescribe a single vendor stack.

**Idea credit (summarized in our own words):** Owen Gretzinger [described on X](https://x.com/owengretzinger/status/2116292908303393032) how tightening runner choice, caching, checkout, job layout, and lint strictness cut wall-clock CI without hiding failures—similar themes appear in the checklist below.

Related PLATE docs:

- [Self-hosted runners](./self-hosted-runners.md) — optional faster compute on private repos ([#1210](https://github.com/akasper/plate/issues/1210), workflow probe [#1214](https://github.com/akasper/plate/issues/1214)).
- [Actions cost rollout](https://github.com/akasper/plate/blob/main/docs/migration/actions-cost-rollout.md) — guards and merged `pr-gates` before you spend on speed (PLATE core repo; not copied in the bootstrap payload).
- Epic [#1269](https://github.com/akasper/plate/issues/1269) — CI/CD split guidance for heavy jobs (separate page).
- [#1282](https://github.com/akasper/plate/issues/1282) — `gh plate ci audit` (waiting vs setup vs run; cache visibility).
- [#1272](https://github.com/akasper/plate/issues/1272) — periodic minutes report to rank expensive workflows.

<!-- PLATES-CORE:BEGIN ci-speed-checklist-1283 -->
## Checklist

Work top to bottom; skip items that do not apply to your host or trust model. Required merge gates (`labels`, `test`, `pr-gates` when configured) must stay green—speed work must not weaken them without owner approval.

### 1. Run jobs on faster machines, including tiny ones

A five-second script that waits ten minutes for a hosted runner is still a ten-minute job. Move **every** workflow job—not only test matrices—off the slowest default pool when you control faster hardware or larger hosted sizes.

- Private repos may use [self-hosted runners](./self-hosted-runners.md) with idle-only policy and hosted fallback ([#1210](https://github.com/akasper/plate/issues/1210), [#1214](https://github.com/akasper/plate/issues/1214)).
- Keep fork and untrusted PR paths on hosted runners only (see the security table in the runner guide).
- Example host knobs (not requirements): larger hosted runner SKUs, your own Linux/Windows/macOS agents, or cloud VMs you already operate.

### 2. Seed dependency caches from the default branch

Pull-request cache scopes are usually **branch-scoped**. Most PRs then start cold unless something populates a cache from the integration branch (for example `main` or your release track).

- Run a scheduled or post-merge workflow on the default branch that installs dependencies and writes the cache keys your PR jobs read.
- Cache **installed** trees (for example language package directories), not only lockfiles, when restore is cheaper than reinstall.
- Verify hit rate in logs; a cache nobody hits is wasted storage and complexity.

### 3. Prefer blobless checkout over shallow clone

Use a **blobless** partial clone (for example Git `filter: blob:none` or the equivalent in your CI checkout action) when jobs need history or tags but not every blob upfront.

- **Shallow** clones (`fetch-depth: 1`) break steps that read full history, merge bases, or release tags.
- Blobless keeps clone time down while remaining compatible with common versioning and diff tools.

### 4. Parallelize independent gates; trim the slowest job

Run lint, typecheck, build, and test in **parallel jobs** when they do not depend on each other's artifacts.

- Move unrelated extras (packaging smoke, doc builds, cross-platform matrices) out of the job that every PR waits on.
- Keep one fast “required” path that matches branch protection; park optional work behind labels, schedules, or post-merge workflows ([#1269](https://github.com/akasper/plate/issues/1269)).

### 5. Add CPU before adding shards

When wall time is dominated by **process or module startup** (interpreter boot, JVM warm-up, loading a large test harness), adding more shards or workers often multiplies that cost.

- Prefer fewer, **wider** machines (more cores per job) before splitting the same suite across many tiny runners.
- Match parallelism to physical cores; oversubscribing CPU can slow everyone down.

### 6. Shared test workers need explicit reset

If the test runner reuses workers across files (for example parallel pytest workers or a pooled browser), require a **reset hook** between files or classes so order-dependent pollution does not flake.

- Document in `AGENTS.md` or test README what each test must clean up (temp dirs, env vars, global singletons).
- Agents should not “fix” flakes by disabling tests without an owner-approved follow-up issue.

### 7. Strict lint and fast static tools

Turn on stricter lint and type rules in CI; automated contributors tolerate noise humans avoid, and catching issues early avoids slow test reruns.

- Prefer **fast** linters and formatters for the default gate; keep heavier analysis on a schedule or optional job.
- Name tools only as examples (for example Ruff, ESLint, `mypy`, `tsc`); choose what fits your stack.

### 8. Measure cost; faster CI can cost more per month

Larger runners, always-on agents, and extra parallel jobs reduce **latency** but often raise **spend**. Track both.

- Use [#1272](https://github.com/akasper/plate/issues/1272) style minutes reporting and [#1282](https://github.com/akasper/plate/issues/1282) job timing splits before and after changes.
- Revisit monthly: if minutes drop but invoice rises, adjust runner size or parallelism.
<!-- PLATES-CORE:END ci-speed-checklist-1283 -->

## Agents

When asked to “speed up CI,” walk this checklist against the adopter’s workflows. Propose minimal diffs; do not remove required checks or bypass branch protection. Escalate with `need:human-review` when speed changes affect security boundaries (runner labels on public repos, fork PRs, or secret access).
