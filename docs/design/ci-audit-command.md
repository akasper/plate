# CI audit command (`gh plate ci audit`)

Parent design: [#1268](https://github.com/akasper/plate/issues/1268) (CI speed and cost at agent pace). Implementation: [#1282](https://github.com/akasper/plate/issues/1282).

The workflow idea—splitting each Actions job into queue time, dependency/setup work, and test execution so teams can spot missing caches and expensive jobs—comes from Owen Gretzinger’s public write-up on Boardy’s CI tuning ([post on X](https://x.com/owengretzinger/status/2116292908303393032), October 2026). The command and heuristics below are PLATE’s own design; they are not copied from that thread.

## Usage

```bash
gh plate ci audit [--repo owner/name] [--limit N] [--json]
```

- **`--repo`**: GitHub repository slug; defaults to `origin` from the current checkout (same as `gh plate health`).
- **`--limit`**: How many recent workflow runs to read from the Actions API (default `30`).
- **`--json`**: Machine-readable report; otherwise a human summary with the costliest jobs first.

The command uses the authenticated `gh` token via `plate_core.github_client.GhClient` (REST only; stdlib + existing dependencies).

## Time buckets

| Bucket | Source | Notes |
|--------|--------|--------|
| **Waiting** | Job `created_at` → `started_at` | Queue time before the job executes on a runner. |
| **Setup** | Selected job steps before the first “test” step | Step duration from `started_at` → `completed_at`. A step counts as setup when its name contains (case-insensitive) `checkout`, `setup`, `set up`, `install`, or `cache`. |
| **Running** | All other step time | Includes the first matching test step, later steps, and any pre-test steps that are not setup-named (for example “Select runs-on”). |

### Test-step heuristic

The first step whose name matches any of these patterns ends the setup phase:

- `\btests?\b`, `pytest`, `unittest`, `npm run test`, `cargo test`, `go test`, `vitest`, `jest` (case-insensitive regexes).

Document any false positives/negatives in your repo’s workflow step names when interpreting reports.

## Cache hit / miss

GitHub’s job API exposes step names and timestamps, not full logs. When a step name contains `cache` and also suggests an outcome (`cache hit`, `cache restored`, `cache miss`, `cache not found`, and similar substrings documented in `plate_core.ci_audit`), the report records a hint. Steps that mention cache without an outcome are counted as `cache_step`. Absence of hints does not prove caches were unused.

## Output

- **Text**: Repository summary, aggregated “costliest jobs” (sum of waiting + setup + running over the fetched runs), then up to 20 recent job instances.
- **JSON**: Full `job_instances` list, `costliest_jobs` aggregates, heuristic metadata, and minute/second fields per row.

Use this command before nightly or scheduled audits (#1271) to baseline where minutes go; it does not change workflows or branch protection.

## Verification

```bash
python -m unittest discover -s tests -p "test_ci_audit.py"
```
