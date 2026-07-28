# Licensing Epic (#390) — Next Release targeting hygiene (#453)

## Context
Documentation child #453 tracked planning paperwork for Epic #390 (Add Licensing). Core LICENSE / README / CONTRIBUTING artifacts shipped in PR #455. One remaining acceptance criterion required the Epic to appear correctly against the standing **Next Release** issue.

## Finding
- Epic #390 still pointed at **#449**, which is the closed **v0.6.0** release issue, not the live standing target.
- As of 2026-07-26, the open standing release issue is **#612** titled `Next Release` (`gh plate release status` / open `Release` issues). Far-future roadmap release remains #654 (v1.0.0) and is not the packaging target for licensing paperwork.

## Actions taken
1. Updated Epic #390 body **Target release** from #449 → **#612** (Next Release), with a short historical note.
2. Recorded this closeout so agents do not re-open #453 for the same stale pointer.

## Verification
- `gh issue view 390` shows Target release #612.
- `gh issue list --label Release --state open` includes #612 `Next Release` (and roadmap #654).
- Licensing artifacts remain present: root `LICENSE` (MIT + Commons Clause v1.0), README blurb, CONTRIBUTING licensing section.

## Out of scope
- Human sidebar link of Epic #390 onto a GitHub milestone/Project field for release negotiation (optional; track labels remain valid).
- Research #451 legal text finalization beyond the already-merged LICENSE.
