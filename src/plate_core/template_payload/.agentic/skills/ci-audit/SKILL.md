---
name: CI audit
description: When and how to run gh plate ci audit and read waiting, setup, and running minutes.
---

# CI audit (`gh plate ci audit`)

> Skill id: `ci-audit`  
> **Lazy-load:** read this file only when baselining CI minutes, ranking expensive workflows, or working through [docs/migration/ci-speed-checklist.md](../../../docs/migration/ci-speed-checklist.md). Do not preload for ordinary feature or bug work.

## When to run

- Before and after CI speed or runner changes (checklist §8; Epic [#1268](https://github.com/akasper/plate/issues/1268)).
- When merge feedback is slow but tests themselves are fast (suspect queue or install time).
- When prioritizing which workflow jobs to optimize first.

This skill **measures** only. It does not edit workflows, weaken required checks, or change branch protection. Propose minimal workflow diffs separately; use `need:human-review` for runner labels on public repos, fork PRs, or secret access.

## Command

```bash
gh plate ci audit [--repo owner/name] [--limit N] [--json]
```

- **`--repo`**: defaults to `origin` from the current checkout (same as `gh plate health`).
- **`--limit`**: recent workflow runs to include (default `30`).
- **`--json`**: machine-readable report; otherwise a text summary with costliest jobs first.

Requires authenticated `gh` with Actions read access for the target repository.

## Reading waiting, setup, and running

| Bucket | What it is | What to try next |
| --- | --- | --- |
| **Waiting** | Queue time from job `created_at` until `started_at` | More runner capacity, larger hosted SKUs, self-hosted idle pool, fewer redundant concurrent jobs |
| **Setup** | Job steps **before** the first step whose name looks like a test (plus steps named checkout/setup/install/cache) | Seed caches from the default branch, slim installs, fix cache keys; verify hits in logs |
| **Running** | All remaining step time (tests and other work after setup phase ends) | Targeted test speedups, parallelism that matches CPU; avoid extra shards when startup dominates |

In text output, **costliest jobs** sort by the sum of waiting + setup + running over the fetched runs—start there.

**Cache hints** in output use the `hint_*` prefix (`hint_hit`, `hint_miss`, `hint_cache_step`). They are inferred from step **names** only, not log lines. Treat them as triage signals, not proof.

## Full reference

Heuristics (test-step detection, JSON fields, verification): [`docs/design/ci-audit-command.md`](https://github.com/akasper/plate/blob/main/docs/design/ci-audit-command.md) in **plate-core** (command ships with `gh plate`, not in the bootstrap doc tree).
