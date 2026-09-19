# Compound offline proof: adopter TTV stack (post-0.8.0)

- **Epic:** #1000 (under Next Release #983)
- **Stack PRs (merge order):** #995 → #997 → #999 → #1002 → #1004
- **Date:** 2026-07-28
- **Mode:** Offline library dry-run on a **simulated sequential merge** of the five open PRs onto `origin/release`
- **Status:** Routing + install-path evidence for under-30m polish — **not** LIVE third-party E2E

## Honest scope

| Claim | Status |
|---|---|
| `next_command` routing chain (import → bootstrap → first-qa → feed) | **Proven offline** on merged stack |
| pin==target self-migrate no false drift | **Proven offline** |
| Session timer records `within_30m` | **Proven offline** (12m synthetic wall clock) |
| Install pin docs (0.8.0 / gh-plate) | Landed in #999 docs |
| Goals hybrid SSOT | Landed in #995 docs |
| LIVE under-30m on third-party repo | **Not proven** — human-gated residual |
| #654 LIVE checklist boxes | **Do not check** from this note |

## Stack under test

| PR | Topic | Role in path |
|---|---|---|
| #995 | Goals.md hybrid SSOT | Mission text for adopters / audits |
| #997 | import-payload `next_command` | Dry-run → apply / escape-hatch / bootstrap |
| #999 | Install path 0.8.0 + pin notes | Prerequisites before the 30m clock |
| #1002 | first-qa dry-run → apply (no re-plan) | Seed routing after core_ready |
| #1004 | complete-session respects first_qa | Session end residual routing + guide |

## Measured path (library calls)

Wall-clock **compute** total ≈ **0.06s** (not operator wall time). Synthetic session duration **12.0m** → `within_30m=true`.

| Step | Result | `next_command` |
|---|---|---|
| Version (PYTHONPATH=src) | 0.8.0 | — |
| import-payload dry-run (empty target, conservative) | would_create=119, conflict=0 | `gh plate import-payload --apply --strategy conservative` |
| import-payload apply (safe) | created=119 | `gh plate bootstrap --repo OWNER/REPO --adopt --apply` |
| session start | ok | — |
| adopt status | core_ready=true, first_qa unseeded | `gh plate adopt --first-qa-plan --json` (entry) |
| first-qa plan (dry-run) | mode=dry_run | `gh plate adopt --first-qa-plan --apply-first-qa --json` |
| first-qa apply (injectable runner) | applied=true | `gh plate feed --json` |
| self-migrate plan (target 0.8.0) | drift=false | plan (review) |
| self-migrate verify | ready=false (`plate_config_invalid` on minimal fixture `.plate`) | re-verify residual |
| session complete (first_qa seeded) | within_30m=true, first_qa_seeded=true | `gh plate feed --json` |
| session complete residual (core_ready, unseeded) | must not re-plan forever | `gh plate adopt --first-qa-plan --apply-first-qa --json` |
| pin==target fixture (`VERSION=0.8.0`) | drift=false, pin_vs_target=equal | — |

### Assertions (routing)

- [x] Empty-target dry-run `next_command` is **apply** (same strategy), not a no-op re-plan
- [x] First-qa dry-run `next_command` includes **`--apply-first-qa`** (not circular `--first-qa-plan` alone)
- [x] First-qa apply success → **feed**
- [x] Session complete with first_qa seeded → **feed**
- [x] Session complete residual when unseeded + core_ready → **apply-first-qa** (aligned with #1002; not re-plan only)
- [x] pin==explicit target → **no drift**

### Known residual (fixture, not product regression)

Minimal seeded `.plate` (`version: 1` only) can fail self-migrate **verify** with `plate_config_invalid`. Full template/bootstrap payload or a valid `.plate` schema is required for `ready=true`. Do not treat that fixture failure as pin/payload drift.

## Operator install gate (from #999)

Before starting the wall-clock session on a real machine:

```bash
pip install -U 'plate-core==0.8.0'
python -c "import plate_core; print(plate_core.__version__)"  # 0.8.0
gh extension upgrade plate   # or reinstall akasper/gh-plate @ v0.8.0
```

## What remains for LIVE proof

1. ~~Human merge of the five PRs to `release` (risk-off).~~ **Done** 2026-07-29 (`release` @ `4f79237`).
2. ~~Post-merge offline re-verify (Phase A).~~ See `docs/research/adopter-ttv-phase-a-post-merge-2026-07-29.md` (#1005 Phase A).
3. Third-party repo adopt under 30m wall-clock with real GitHub bootstrap + Q&A issues (**#1005 Phase B**).
4. Only then consider #633 / #654 LIVE boxes with PR citations + session artifact.

## Closing

Artifact for Epic **#1000** / adopter path under **#983**. Complements `docs/research/adopter-install-path-0.8.0-parity.md` (#998/#999).
