# Research / timed note: adopter install path parity (v0.8.0)

- **Issues:** #998 (this Documentation); related #983 Next Release, #989 / #992 adopter TTV, #633, #649
- **Date:** 2026-07-28
- **Mode:** **Local offline library dry-run** — not LIVE third-party repo E2E
- **Status:** Evidence for install-path docs polish; **do not** check #654 LIVE under-30m boxes from this note alone

## Problem

After shipping **v0.8.0** (PyPI `plate-core==0.8.0`, `akasper/gh-plate` **v0.8.0** with `PLATE_CORE_VERSION=0.8.0`), developer machines and docs often still:

- Install unpinned `pip install plate-core` without verifying version
- Run an older **gh-plate** extension that **re-locks** pip to `plate-core==0.7.2` on every `gh plate` invocation
- Mix monorepo `PYTHONPATH=src` (0.8.0) with site-packages (0.7.2)

That pin skew is pure friction on the under-30m adopt clock and confuses self-migrate “drift” reading if operators compare the wrong runtime.

## Published truth (checked 2026-07-28)

| Surface | Version observed |
|---|---|
| PyPI `plate-core` latest | **0.8.0** (also published: 0.7.2) |
| GitHub Release `akasper/plate` | **v0.8.0** |
| GitHub Release `akasper/gh-plate` | **v0.8.0** |
| `akasper/gh-plate` `PLATE_CORE_VERSION` | **0.8.0** |
| Monorepo `plate_core.__version__` (via `PYTHONPATH=src`) | **0.8.0** |
| Sample local site-packages (this agent host) | **0.7.2** (stale — needs upgrade) |

## Recommended install / upgrade (docs SSOT in README)

```bash
pip install -U 'plate-core==0.8.0'
python -c "import plate_core; print(plate_core.__version__)"  # 0.8.0

gh extension install akasper/gh-plate
# or: gh extension upgrade plate
# reinstall if pin file still says 0.7.x:
#   gh extension remove plate && gh extension install akasper/gh-plate
```

Symptom of stale extension: stderr line like `plate-core version lock active ... ensuring plate-core==0.7.2`.

## Offline timed dry-run (this host)

Library-level calls only (no GitHub network apply, no third-party target repo).

| Step | Result | Elapsed (s, cumulative ≈) |
|---|---|---|
| Version probe | src **0.8.0** · site-packages **0.7.2** | 0.01 |
| `import_payload` empty temp, conservative dry-run | ok; would_create=119; would_conflict=0 | 0.04 |
| `assess_adoption_readiness` on monorepo | `core_ready=true`; next → health/feed | 0.04 |
| `plan_self_migrate` monorepo | drift=false; target=installed=0.8.0; no pin files | 0.04 |
| `verify_self_migrate` monorepo | ready=true; failures=[] | 0.04 |
| Explicit pin==target fixture (`VERSION=0.8.0`, target 0.8.0) | **drift=false**; pin_vs_target=equal | 0.04 |

- **Wall-clock total (library path):** ~0.04s (machine-local; not operator wall time)
- **within_30m budget (compute only):** yes
- **LIVE under-30m claim:** **no** — still requires human-gated third-party repo E2E (payload apply, bootstrap remote, first Q&A, session timer)

### Self-migrate pin UX

Fixture with `VERSION` pin **equal** to explicit `target_version=0.8.0` did **not** mark drift even when comparing against installed 0.8.0. This matches the post-#984 rule: pin==target is not false-drift when installed is equal/ahead of pin without pin/target mismatch.

### import-payload `next_command`

On **origin/release** at measurement time, empty-target dry-run did not yet surface `next_command` in the library build under test (Feature **#996** / PR **#997** lands that field). After merge, expect:

`gh plate import-payload --apply --strategy conservative` for empty-target dry-run with pending creates.

## Gaps remaining (honest)

1. **Human:** upgrade local/dev gh-plate + pip to 0.8.0 on operator machines (not a repo Task unless CI pins lag).
2. **LIVE E2E:** third-party adopt under 30m with session timer evidence (#633 residual).
3. **Docs drift:** keep pin examples current at next cut (0.9.x) — do not leave 0.8.0 forever without a follow-up bump.

## Closing

This file is the research/timed artifact for **#998**. Install command parity is also applied in:

- `README.md` (Install versions + Quick Start)
- `docs/migration/adoption-guide.md` (Prerequisites)
- `docs/bootstrap/marketplace-install-checklist.md`

```
Closes #998
```
