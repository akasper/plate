# Refinement drafts: Epic #1077 — cheap PR babysitting

**Parent:** [#1077](https://github.com/akasper/plate/issues/1077)  
**Children (stubs):** [#1078](https://github.com/akasper/plate/issues/1078), [#1079](https://github.com/akasper/plate/issues/1079), [#1080](https://github.com/akasper/plate/issues/1080), [#1081](https://github.com/akasper/plate/issues/1081)  
**Prepared:** 2026-11-28 (planning-only; no release fragment)  
**Audience:** Andrew — refine stubs without re-litigating shipped behavior on `release-minor`.

This file records **gaps-only** refinement: what is already merged is source of truth; new work must extend it, not propose alternate command shapes or paths.

---

## Discovery — in-flight and existing sources

| Key | Issue | GitHub state | Open PR (`in:body`) | Source of truth (repo) | Notes |
|-----|-------|--------------|---------------------|-------------------------|-------|
| Epic | #1077 | Open (`status:stub`, `need:refinement`) | *(none)* | `src/plate_core/cli.py` `cmd_pr_babysit` watch loop (~L1287–1516); fragment `.agentic/releases/v0.8.5/fragments/1077-babysit-watch-probe-wiring.json` | Owner comment (2026-10) says probe not wired; **code on `release-minor` wires probe + summary**. Epic still open for refinement / ceremony. |
| Child | #1078 | Closed (`status:stub`, `status:implemented`) | *(none)* | `src/plate_core/pr_watch_probe.py`; `tests/test_pr_watch_probe.py`; integration `tests/test_pr_babysit_watch_probe.py` | Merged #1082; wired in #1100. HTTP via `gh api -i` (`procutil.run_hidden`). State: `.agentic/babysit/<slug>-<pr>.probe.json`. |
| Child | #1079 | Closed (stub labels) | *(none)* | `src/plate_core/pr_watch_backoff.py`; `Backoff`, `should_stop`; `tests/test_pr_watch_backoff.py`, `tests/test_cli.py` (fake clock) | Merged #1084. CLI: `--min-interval` / deprecated `--interval`, `--max-interval`, `--max-hours` (wall clock stop). Legacy loop `_run_legacy_babysit_watch_loop` only when `GhClient` is a test double. |
| Child | #1080 | Closed (stub labels) | *(none)* | `src/plate_core/pr_watch_summary.py`; `docs/wiki/PR-Babysit-Wake-Summary.md`; `tests/test_pr_watch_summary.py`, `tests/test_pr_watch_summary_dedupe.py` (#1096) | Merged #1085. `RENDER_BYTE_BUDGET = 2048` enforced in tests. Watch prints `render_wake_summary`; `--json` adds `wake_summary` on actionable ticks. |
| Child | #1081 | Closed (stub labels) | *(none)* | `src/plate_core/pr_watch_caps.py`; `tests/test_pr_watch_caps.py`; CLI `--max-wakes`, `--cap-hours`, `--status`, `--reset-caps` | Merged #1083. Ledger: `.agentic/babysit/<slug>-<pr>.caps.json`. Pause marker `<!-- plate-babysit-cap -->`. |
| Wiring | — | — | — | Merged PR [#1100](https://github.com/akasper/plate/pull/1100) | Probe + summary path in production watch loop (not legacy). |
| Guards | #1233, #1246 | Closed | *(none)* | `src/plate_core/pr_watch_guards.py`; `tests/test_pr_watch_guards.py` | Required checks, CI settle, REST fallback, event memory, base overlap — extends #1077 cost model (no new CLI names). |
| Dedupe | #1096 | Closed | *(none)* | `pr_watch_summary` filters + `tests/test_pr_watch_summary_dedupe.py` | Skip repeated resolved Copilot comments in deltas. |
| MCP | — | — | Open [#1544](https://github.com/akasper/plate/pull/1544) (handler map; #1543) | `src/plate_core/mcp_server.py` `plate_pr_babysit` → one-shot `babysit_pr` only; `mcp/tool_profiles.py` lists tool | **No MCP `--watch` surface today.** Any new watch/MCP tool must follow #1544 registry + #1536 / #1538 / #1541 when those land. |
| Docs drift | — | — | — | `docs/wiki/Goals.md` L67 vs L74 | L67 still says watch loop does not call probe libraries; L74 and code contradict. Fix in a separate Documentation PR (out of scope here). |
| Related | — | — | — | `src/plate_core/pr_packet.py` + `tests/test_pr_packet.py` | Reuses `pr_watch_probe` with **separate** checkpoint from babysit watch — do not merge state files in #1077 refinement. |

**Child issue comments:** Only auto-close notices from merged integration PRs (#1082–#1085); no human refinement thread on the stubs.

---

## Recommended refinement order

1. **Confirm epic completion signal** (#1077) against shipped loop + tests (below).
2. **Per-child stub ceremony** — update issue bodies/AC in GitHub (human or follow-up PR), clear `need:refinement` / `status:stub` when Andrew accepts; do **not** clear labels in this planning PR.
3. **Documentation-only gaps** — Goals.md, optional skill cross-links (#1080), public-surface inventory when #1536/#1541 are ready.
4. **Optional product gaps** — `.plate` cap defaults (#1081), MCP watch/delta surface (only if Andrew wants it; separate Feature).

Dependencies: #1078 library → #1079 backoff in same loop → #1080 summary on `probe_result.changed` → #1081 caps around `record_wake`. Guards (#1233/#1246) assume all four; wiring (#1100) is already on `release-minor`.

---

## Epic #1077 — gaps only

**Already shipped (do not re-implement):** Quiet ticks call `probe_pr` (`GhApiHttp` / `gh api -i`); no `babysit_pr` unless first tick, `--full-every N`, or actionable `build_wake_summary`; `Backoff.next_interval(activity_tick)`; caps via `check_caps` / `record_wake`; stop via `should_stop`.

| Gap | Draft acceptance criteria | Paths |
|-----|-------------------------|-------|
| Epic closure criteria | Andrew agrees children are refinement-complete; #1077 closes with a Documentation or Epic-summary PR that points at this file + wiki wake doc, not new code. | Issues only (ceremony) |
| Stale epic comment | Epic body comment contradicts `release-minor`; refinement should note wiring landed in #1100 and guards in #1245. | GitHub #1077 comment (human) |
| Agent cost doctrine | `docs/wiki/PR-Babysit-Wake-Summary.md` is canonical for agents; link from `docs/agents/pr-feedback-and-babysit.md` if not already one hop away. | Wiki + agents doc |
| Out of scope reaffirm | Event-driven webhooks replacing poll loop stays out of epic (per epic body). | — |

---

## #1078 — cheap change detection

**Shipped:** Conditional GET, ETag persistence, `fetch_delta` with `since`, CI polling on every probe, delta ids in `ProbeState`.

| Gap | Draft acceptance criteria | Depends on |
|-----|-------------------------|------------|
| Stub sign-off | Refined issue states: unchanged tick = one probe path without GraphQL `babysit_pr`; changed tick = delta fetch only since `last_checked_at`. | Merged behavior + `tests/test_pr_watch_probe.py` |
| `gh api` vs raw HTTP | Document that production uses `gh api -i` (not generic `gh api` without headers) as the supported 304 path. | `pr_watch_probe` module docstring |
| `pr_packet` boundary | Refinement text says `pr_packet` checkpoint files are not shared with babysit `.probe.json` (separate paths). | `pr_packet.py` header comment |

**Open questions (Andrew)**

| # | Question | Recommended default |
|---|----------|---------------------|
| Q1 | Treat #1078 as refinement-complete and strip stub labels despite `CLOSED` + `status:implemented`? | **Yes** — code + tests satisfy original stub AC; use refinement edit to checklist only. |
| Q2 | Require live-network smoke for 304/ETag beyond unit tests? | **No** — keep injected `HttpClient` tests; optional manual note in wiki Troubleshooting only if flakes appear. |

---

## #1079 — backoff and stop conditions

**Shipped:** `Backoff` doubles quiet interval capped at `--max-interval` (default 1800s); reset on `activity_tick` (full babysit or actionable wake path). `should_stop` on merged/closed PR from probe body. `--max-hours` limits wall-clock watch duration (0 = off). Pidfile cleared in `finally`.

| Gap | Draft acceptance criteria | Depends on |
|-----|-------------------------|------------|
| Naming clarity | Refined stub distinguishes **`--max-hours`** (stop watch) vs **`--cap-hours`** (#1081 spend budget). | `cli.py` argparse help text (already separate; reflect in issue AC) |
| Quiet vs active backoff | Document that quiet ticks use `activity_tick=False` even when CI-only change was non-actionable (no `record_wake`). | `cli.py` watch loop L1430–1499 |
| Deprecated `--interval` | Stub AC lists `--min-interval` as canonical; `--interval` alias remains. | `cli.py` L5447–5452 |

**Open questions (Andrew)**

| # | Question | Recommended default |
|---|----------|---------------------|
| Q3 | Change default `--max-interval` from 30m if PRs are usually fast-moving? | **Keep 30m** — matches shipped default; tune via flags only until telemetry exists. |
| Q4 | Should `--max-hours` default to a non-zero stop (e.g. 24h) instead of 0 (unlimited)? | **Keep 0 disabled** — spend caps (#1081) already bound unattended cost; avoid double confusion with `--cap-hours`. |

---

## #1080 — change-summary wake

**Shipped:** `build_wake_summary`, `render_wake_summary`, `is_actionable`; bot/marker filtering; 2048-byte render budget; `--json` includes structured `wake_summary` on wake ticks.

| Gap | Draft acceptance criteria | Depends on |
|-----|-------------------------|------------|
| Skill / AGENTS pointer | `plugin/skills/address-pr-feedback/SKILL.md` (or pr-babysit skill if split) explicitly: on `--watch` wake, read CLI/MCP summary, do not re-run full GraphQL load unless summary says so. | Wiki wake doc §“Do not reload” |
| MCP scope | Document that **`plate_pr_babysit` is one-shot**; watch deltas are CLI-only unless a new MCP tool is approved. | `mcp_server.py` L745–759 |
| Size budget AC | Stub “~2 KB” maps to `RENDER_BYTE_BUDGET` and existing tests (`test_pr_watch_summary.py` assert ≤2048). | No new constant |

**Open questions (Andrew)**

| # | Question | Recommended default |
|---|----------|---------------------|
| Q5 | Add MCP tool (e.g. `plate_pr_babysit_watch_tick`) for hosted agents that cannot run long CLI watches? | **Defer** — CLI `--watch` + pidfile remains canonical; hosted agents use human-triggered `plate_pr_babysit` until a dedicated Feature is opened. |
| Q6 | Emit wake summary to a file under `.agentic/babysit/` for log scrapers? | **No** — stdout/`--json` already sufficient; avoid new persistence unless a consumer issue exists. |

---

## #1081 — spend caps

**Shipped:** Defaults `max_wakes=10`, `cap_hours=12` at ledger creation; `record_wake` only on full babysit path; single deduped pause comment; `--status` JSON/human via `_print_watch_cap_status`.

| Gap | Draft acceptance criteria | Depends on |
|-----|-------------------------|------------|
| `.plate` config | Original stub allowed `.plate` defaults — **not implemented**; refinement should either defer or open a child Feature with schema in `plate_config` / autonomy docs. | No `.plate` keys today |
| Public surface inventory | When #1536/#1541 land, stable CLI flags (`--max-wakes`, `--cap-hours`, `--reset-caps`, `--status`, `--full-every`) must appear in inventory + `public_surface_stable.json` per #1544 process. | Follow #1541 merge |
| Wake definition | Refinement defines “wake” = tick that called `record_wake` (actionable/full babysit), not quiet probes. | `cli.py` + `pr_watch_caps.record_wake` |

**Open questions (Andrew)**

| # | Question | Recommended default |
|---|----------|---------------------|
| Q7 | Add `.plate` `autonomy.babysit_watch_caps` defaults? | **Defer** — CLI flags + persisted ledger match shipped behavior; `.plate` only with explicit schema review (no silent edits in epic close). |
| Q8 | Lower default `max_wakes` (10) for cost-sensitive adopters? | **Keep 10** — document tuning via `--max-wakes` and `--reset-caps`; change default only with release fragment + migration note. |

---

## Cross-cutting open questions (Andrew)

| # | Question | Recommended default |
|---|----------|---------------------|
| Q9 | Close #1077 now that children are implemented on RC, leaving only stub-label cleanup? | **Yes, after** accepting this refinement draft and updating child issue checklists in a single human pass. |
| Q10 | One Documentation PR to fix `Goals.md` L67 and cross-link wake wiki from agents doc? | **Yes** — small docs PR, `Refs #1077`, no code. |
| Q11 | Register watch CLI flags in public-surface inventory in the same PR as #1541 or immediately after? | **After #1541** — use existing flag names from `cli.py`; no renames. |

---

## Verification anchors (for refinement sign-off, not this PR)

```text
python3 -m unittest tests.test_pr_watch_probe tests.test_pr_watch_backoff \
  tests.test_pr_watch_caps tests.test_pr_watch_summary \
  tests.test_pr_babysit_watch_probe tests.test_pr_watch_guards -v
```

These modules already encode the stub intents; refinement acceptance should cite them rather than expanding scope.