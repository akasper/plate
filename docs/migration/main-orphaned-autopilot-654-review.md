# Review note: orphaned `main` autopilot tip (2026-06)

## Context

Between **v0.7.2** (merge PR #611, tag `v0.7.2` = `bd50211`) and the **v0.8.0** packaging cut, the default branch `main` no longer shared history with the product line on `release`.

- **Product line:** `release` / `release-v0.8.0` (descends from real Initial commit + all shipped work).
- **Orphan tip (this branch):** 29 commits rooted at `76f03de`, labeled autopilot `#654`, with messages like "Advance research/design surface still [ ]" and "MCP direct to main. No PR."

## What these commits contain

| Layer | Content |
|-------|---------|
| Root commit `76f03de` | Unrelated-history snapshot of an older monorepo tree (~671 paths), **not** an ancestor of `release`. |
| Commits after root (28 files) | Only additional JSON sketch fragments under `.agentic/releases/unreleased/*-654*.json`. |

Sample fragment shape: `"still [ ]; active sketch"`, claims of tests-first updates, but **no subsequent commits touch `src/`** after the root. These are **planning/sketch noise**, not landable Features.

## Cherry-pick decision (2026-07-28)

**Not ported into `release`.** Reasons:

1. No shared merge-base with `release` → cannot cherry-pick as a normal series.
2. Post-root deltas are sketch fragments only; they would re-pollute unreleased after the 0.8.0 cut.
3. Real #654 autonomy/adoption work already shipped on `release` via reviewed PRs (#691–#982) and is packaged as **v0.8.0**.

## Restoration of `main`

`main` was force-with-lease reset to **`v0.7.2`** (`bd50211`), then advanced via Release PR **#984** (`release-v0.8.0` → `main`) for the 0.8.0 cut.

## How to inspect this archive

```bash
git fetch origin archive/main-autopilot-654-sketches-2026-06
git log --oneline origin/archive/main-autopilot-654-sketches-2026-06
git diff --stat 76f03de origin/archive/main-autopilot-654-sketches-2026-06
```
