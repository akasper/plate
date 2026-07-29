# Phase A: post-merge offline re-verify (adopter TTV stack)

- **Feature:** #1005 (Phase A only)
- **Epic:** #1000 · Next Release #983
- **Date:** 2026-07-29
- **release tip:** `4f79237` (squash-merged stack #995 → #997 → #999 → #1002 → #1004)
- **Mode:** Offline library dry-run on **merged** `origin/release` (not a simulated stack)
- **Status:** Phase A **complete** — routing re-verified on real tip · **not** LIVE third-party E2E

## Gate clearance

| Gate | State |
|---|---|
| Human squash-merge stack to `release` | **Done** (PRs #995/#997/#999/#1002/#1004 MERGED 2026-07-29) |
| Task #1006 completion comment | Human residual (`<!-- PLATE-TASK-CLOSED -->`) |
| Offline re-verify on post-merge tip | **This document** |
| LIVE under-30m third-party | **Phase B** — still open on #1005 |

## Measured path (library, PYTHONPATH=src @ 4f79237)

Wall-clock **compute** ≈ **0.12s** (not operator wall time). Session complete records `within_30m=true` for near-instant synthetic sessions.

| Step | Result | `next_command` |
|---|---|---|
| Version | 0.8.0 | — |
| import-payload dry-run (empty, conservative) | would_create=121, conflict=0 | `gh plate import-payload --apply --strategy conservative` |
| import-payload apply (safe) | created=121 | `gh plate bootstrap --repo OWNER/REPO --adopt --apply` |
| session start | ok | — |
| assess (post-import) | core_ready=true, first_qa unseeded | `gh plate adopt --first-qa-plan --apply-first-qa --json` |
| first-qa plan (dry-run) | mode=dry_run | `gh plate adopt --first-qa-plan --apply-first-qa --json` |
| first-qa apply (injectable runner) | applied=true | `gh plate feed --json` |
| self-migrate plan (target_version=0.8.0, VERSION pin) | drift=false, pin_vs_target=equal | plan (review) |
| self-migrate verify (pin-only fixture) | ready=false (`adoption_not_core_ready` only; `no_drift` ok; `.plate` valid) | bootstrap residual on bare fixture |
| session complete (first_qa seeded) | within_30m=true, first_qa_seeded=true | `gh plate feed --json` |
| session complete residual (core_ready, unseeded) | must not re-plan forever | `gh plate adopt --first-qa-plan --apply-first-qa --json` |

### Unit tests on tip

```text
tests/test_adoption.py + test_import_payload.py + test_what_next.py
  + test_copilot_cli_marketplace_packaging.py  → 87 passed
tests/ -k self_migrate  → 34 passed
```

### Assertions (routing)

- [x] Empty-target dry-run `next_command` is **apply** (same strategy)
- [x] Assess / first-qa dry-run `next_command` includes **`--apply-first-qa`**
- [x] First-qa apply success → **feed**
- [x] Session complete with first_qa seeded → **feed**
- [x] Session complete residual when unseeded + core_ready → **apply-first-qa**
- [x] pin==explicit target → **no drift** (`pin_vs_target=equal`)

### Honest non-claims

- LIVE under-30m on a third-party GitHub repo: **not proven**
- Operator wall-clock install + bootstrap + Q&A issues: **not proven**
- #654 LIVE checklist boxes: **do not check** from Phase A alone

## Delta vs pre-merge offline note

Pre-merge compound note: `docs/research/adopter-ttv-stack-offline-proof.md` (simulated merge).  
This Phase A note re-runs the same routing spine on the **actual** post-merge `release` tip after human merge.

Minor count drift: would_create/created **121** on tip (was 119 in pre-merge note) — payload growth since the simulated stack, not a routing regression.

## Phase B spine (unchanged)

```bash
pip install -U 'plate-core==0.8.0'
python -c "import plate_core; print(plate_core.__version__)"  # 0.8.0
gh extension upgrade plate   # or reinstall akasper/gh-plate @ v0.8.0

# in throwaway/target repo:
gh plate adopt --start-session --json
# follow next_command: import-payload → bootstrap --adopt → first-qa apply → feed
gh plate adopt --complete-session --json
```

Evidence target: `docs/research/adopter-live-under-30m-<date>.md` with wall-clock table, session `within_30m`, and issue links.

## Related

#1005 · #1000 · #1006 · #983 · #633 · #989 · #992 · offline stack proof · install path #999
