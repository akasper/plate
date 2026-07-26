# Closeout: `.plate` config lifecycle (#331) and extension precedence/upgrade (#333)

- **Issues:** #331, #333
- **Epic:** #259 (closed)
- **Date:** 2026-07-26
- **Status:** Delivered in v0.2.x; issues left open without closing keyword — this doc is the formal closeout artifact

## Context

Epic #259 (`.plate` Root Config Lifecycle) closed after shipping baseline surfaces and extension/upgrade helpers. Child Features **#331** and **#333** remained `OPEN` even though fragments and release notes already record the work:

| Fragment / release | Links |
|---|---|
| `.agentic/releases/v0.2.1/fragments/259-plate-config-lifecycle.json` | #259, #332, #333 |
| `.agentic/releases/v0.2.1/fragments/333-plate-config-extension-upgrade.json` | #333, #259 |
| Aggregated in `v0.2.0` / `v0.2.1` `release.json` | same |

Design baseline: `docs/design/plate-root-config-schema-lifecycle.md`.

## #331 — Baseline lifecycle surfaces

| Acceptance criterion | Evidence on `release` (2026-07-26) |
|---|---|
| CLI `config show` / `validate` / `init` with `--json` | `src/plate_core/cli.py` `cmd_config_show|validate|init`; parsers under `gh plate config` |
| MCP get / validate / init | `plate_config_get`, `plate_config_validate`, `plate_config_init` in `mcp_server.py` |
| Shared report type | `PlateConfigReport` via `get_plate_config_report()` |
| Bootstrap seeds missing `.plate` | `bootstrap.py` + design/checklist docs from #259 fragments |
| Tests | `tests/test_epic89_plate_config.py` (31 passed locally this closeout) |

**Live probe (this repo):** `get_plate_config_report` → `present=True`, `valid=True`, `file_version=1.2`, `resolved_version=1.2`.

## #333 — Extension precedence and upgrade helpers

| Acceptance criterion | Evidence |
|---|---|
| Extension precedence (defaults < extension layer < local) | `plate_config._resolve_extension_layer`, `_resolve_plate_config`, builtin manifests `plate_extensions.yml` (`release-track-management`, `specialist-agents`) |
| `provided_by` / manifest-driven scenario | Builtin extension manifests + normalize/merge paths covered in tests |
| Schema migration / upgrade helpers | `upgrade_plate_config_dict` (1.0→1.1→1.2), `apply_plate_config_upgrade`, CLI `gh plate config upgrade`, MCP `plate_config_upgrade` |
| Migration guidance | Upgrade returns guidance steps; CURRENT_CONFIG_VERSION = `1.2` |
| Docs / fragments aligned | Design doc + v0.2.1 fragments cited above |

**Live probe:** `upgrade_plate_config_dict({"version":"1.0"})` → `1.2` with 4 guidance steps.

## Non-goals of this closeout

- Changing runtime config behavior
- Re-opening Epic #259
- Multi-track release branch repair (#320) — separate issue

## Closeout actions

1. Land this document via Documentation PR with `Closes #331` and `Closes #333`.
2. No further implementation required for these two issues unless a new regression is found (open a Bug then).
