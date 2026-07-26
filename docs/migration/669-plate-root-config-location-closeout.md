# Closeout: Follow-up from Question #327 (Feature #669)

- **Issue:** #669
- **Question:** #327 — Should `.plate` remain a repository-root config surface?
- **Date:** 2026-07-26
- **Status:** Decision already implemented; no further code change required

## Answer (authoritative)

**Keep `.plate` at the repository root** as the durable, repo-owned config surface.

## Evidence already on `release`

| Surface | Evidence |
|---|---|
| Design | `docs/design/plate-root-config-schema-lifecycle.md` — root `.plate` file contract |
| Runtime | `plate_core.plate_config` loads/saves `repo_root / ".plate"` |
| CLI/MCP | `gh plate config show|validate|init|upgrade`, `plate_config_*` |
| Health | `plate_config_present` / validity on `gh plate health` |
| SPEC/AGENTS | Autonomy + authority text treat `.plate` as single source for autonomy config |
| Closeout of lifecycle | `docs/migration/331-333-plate-config-lifecycle-closeout.md` (Epic #259 children) |

Contemplation ref on #669: `plate-contemplation-ref: q327 @2026-06-18…` — same decision.

## Non-goals

- Moving config under `.github/` (explicitly rejected; would break conventions and tooling)
- Re-opening Epic #259

## Closeout

Land this document with `Closes #669`. No runtime PR required beyond this Documentation artifact.
