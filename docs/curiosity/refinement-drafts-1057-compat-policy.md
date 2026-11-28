# Refinement draft: deprecation and compatibility policy (#1057)

**Parent Epic:** [#1055](https://github.com/akasper/plate/issues/1055) — 1.0 compatibility: public-surface promise  
**Issue:** [#1057](https://github.com/akasper/plate/issues/1057) — Design: deprecation and compatibility policy with versioning rules  
**Milestone:** 1.0  
**Prepared for:** Andrew (stub refinement; does not clear `status:stub` / `need:refinement`)  
**Status:** Draft refinement only

---

## Source of truth (already in flight)

This draft refines **#1057 only**. Inventory, contract tests, generated reference, and loaders are implemented elsewhere—policy must cite them, not reinvent paths.

| Child | Implementation PR | Canonical artifacts |
|---|---|---|
| **#1056** Research inventory | [#1536](https://github.com/akasper/plate/pull/1536) | `docs/plate/research/public-surface-inventory.md` — six surface classes; each row **stable** / **experimental** / **internal** (§Classification criteria). |
| **#1058** Contract tests | [#1541](https://github.com/akasper/plate/pull/1541) (stacked on #1536); loaders in [#1547](https://github.com/akasper/plate/pull/1547) | Snapshot `tests/fixtures/public_surface_stable.json`; deprecation registry `tests/fixtures/public_surface_deprecations.json`; `tests/test_public_surface_contract.py`, `tests/public_surface_contract_lib.py`; `scripts/regenerate_public_surface_stable.py`. Live CLI/MCP via `src/plate_core/public_surface_loader.py` (`load_cli_tree()`, `load_mcp_tool_definitions()`). |
| Stable CLI/MCP reference + drift | [#1538](https://github.com/akasper/plate/pull/1538) | `docs/cli-mcp-reference.md`; `scripts/generate-cli-mcp-reference.py` (`--check` in CI). Stable rows sourced from the inventory markdown. |

- **#1056:** refinement is owned by [#1536](https://github.com/akasper/plate/pull/1536); this file does not duplicate it.
- **#1058:** behavior and maintainer workflow are defined in [#1541](https://github.com/akasper/plate/pull/1541) / [#1547](https://github.com/akasper/plate/pull/1547); policy below explains *when* to use the deprecation registry vs a release fragment.

---

## Overview

[#1057](https://github.com/akasper/plate/issues/1057) publishes how PLATE **1.0+** maps inventory **stability classes** to **semver** and **adopter action**, aligned with release ceremony (`Major` / `Minor` / `Patch`, fragments, `gh plate release cut|finalize`) in `AGENTS.md` and `docs/design/release-ceremony-refinement.md`. The policy document is the human-facing rules layer on top of the machine checks in [#1541](https://github.com/akasper/plate/pull/1541).

**Epic #1055 non-goals (unchanged):** no `.plate` schema edits in the Epic itself; no LTS unless this design explicitly adds it.

**Related:** [#654](https://github.com/akasper/plate/issues/654) roadmap, [#649](https://github.com/akasper/plate/issues/649) self-migrate, [#1065](https://github.com/akasper/plate/issues/1065) upgrade guide (must cite final policy path).

---

## Stub #1057 — Design: deprecation and compatibility policy

### Proposed scope

Ship **`docs/plate/design/deprecation-and-compat-policy-1057.md`** that defines:

1. **Stability semantics** — same three classes as `docs/plate/research/public-surface-inventory.md` (§Classification criteria):
   - **stable:** semver-covered adopter contract; listed in snapshot + (for CLI/MCP) reference doc.
   - **experimental:** shipped but may change across minors; excluded from `public_surface_stable.json` unless promoted via inventory + regenerate.
   - **internal:** not in adopter migration guides; contract tests do not treat removals as breaking.

2. **Semver impact rules** — per surface class, with examples tied to repo enforcement:

| Surface class | Source in inventory | Major (breaking) examples | Minor examples | Patch examples |
|---|---|---|---|---|
| CLI stable invocations/flags | §1.2 rows class **stable**; snapshot `cli` map | Remove invocation or flag in snapshot without deprecation entry ([#1541](https://github.com/akasper/plate/pull/1541) `kind`: `cli_invocation`, `cli_flag`) | New optional flag on stable invocation (snapshot regen only) | Doc-only fix in inventory/reference |
| MCP stable tools/schemas | §2.2 **stable** tools; snapshot `mcp_tools` | Remove tool, drop property, or new **required** input field without `mcp_required_field` deprecation | New optional property on stable tool | Profile/docs clarification |
| Labels | §6 **stable**; snapshot `labels` | Rename/remove stable label without `label` deprecation | Add new `area:*` / `need:*` (inventory row + snapshot) | Description-only in `.github/labels.yml` |
| `.plate` keys | Inventory §3 + `gh plate config validate` / `plate_config.py` | Remove required top-level key or reject previously valid file | New optional nested key with default in `DEFAULT_CONFIG` | Validation message only |
| Release fragments | `.agentic/releases/unreleased/README.md`, `validate_fragment()` | New required fragment field for adopters | New optional field | Typo in README |
| `.agentic/` layouts | `.agentic/process.yml` `artifacts:` | Rename/remove path import-payload writes | Add optional file under template payload | Comments |

3. **Deprecation workflow (machine + human)** — align policy text with [#1541](https://github.com/akasper/plate/pull/1541):

   - **Shrink or break stable surface:** add an object to `tests/fixtures/public_surface_deprecations.json` (`kind`, `name`, `since`, optional `replacement`), update inventory in #1536, regenerate snapshot (`PYTHONPATH=src python3 scripts/regenerate_public_surface_stable.py`), refresh `docs/cli-mcp-reference.md` (`python3 scripts/generate-cli-mcp-reference.py`).
   - **Release narrative:** Feature/Breaking PR includes fragment with `"breaking": true` when downstream repos must act; pair with `Major` issue label and `release-major` track per branch model.
   - **Additions** to live CLI/MCP/labels do not fail contract tests; policy still requires inventory update before calling something **stable**.

4. **Self-migration (#649)** — policy section: how `gh plate self-migrate` / `plate_self_migrate_*` consume release notes and inventory `migration_impact` when stable surface shrinks (reference #649 offline verify; no new commands in this Design issue).

5. **Freeze / 1.0 moment** — when `stable` classifications in the inventory markdown are treated as frozen for semver promises (see open questions).

### Non-goals

- Editing the inventory ([#1536](https://github.com/akasper/plate/pull/1536)) or contract code ([#1541](https://github.com/akasper/plate/pull/1541), [#1547](https://github.com/akasper/plate/pull/1547)) in the #1057 Design PR.
- New CI workflows beyond what those PRs already wire into the existing `test` job.
- Implementing runtime deprecation warnings in CLI/MCP (optional follow-up Features).

### Draft acceptance criteria

- [ ] Design doc at **`docs/plate/design/deprecation-and-compat-policy-1057.md`** with: stability semantics, semver table (above expanded with real command examples from inventory), deprecation registry + fragment rules, self-migrate pointer, link to [#1065](https://github.com/akasper/plate/issues/1065) upgrade section placeholder.
- [ ] Every rule cites [#1536](https://github.com/akasper/plate/pull/1536) inventory sections, [#1541](https://github.com/akasper/plate/pull/1541) deprecation `kind` values, or release ceremony docs—no alternate snapshot paths.
- [ ] Contributor checklist: intentional stable shrink → deprecations JSON + inventory + regenerate script + reference generator `--check` green.
- [ ] Documentation PR labeled `Documentation`, body `Closes #1057` when implemented (not this curiosity draft PR).

### Dependencies

- **Blocked by:** merged or agreed inventory from [#1536](https://github.com/akasper/plate/pull/1536) (classification columns are normative).
- **Informed by:** contract behavior in [#1541](https://github.com/akasper/plate/pull/1541), loaders in [#1547](https://github.com/akasper/plate/pull/1547), reference drift in [#1538](https://github.com/akasper/plate/pull/1538).
- **Blocks:** [#1065](https://github.com/akasper/plate/issues/1065) upgrade guide policy section; Epic #1055 “policy cited from upgrade guide” criterion.

---

## Open questions for Andrew (#1057)

1. **Deprecation duration before stable removal:** how many minor releases (or minimum calendar time) between deprecation registry entry and deleting from live code/snapshot?  
   **Recommended default:** two PLATE minors or 90 days, whichever is longer; `since` field in `public_surface_deprecations.json` records the announcing version.

2. **Experimental → stable promotion:** minor release with inventory reclassification + snapshot regen + reference regen only (no deprecation entry)?  
   **Recommended default:** yes—promotion is minor-level product news, not breaking.

3. **Breaking change without deprecation file entry:** ever allow emergency major with only `breaking: true` fragment and no JSON registry row?  
   **Recommended default:** no for CLI/MCP/label removals; registry entry required so [#1541](https://github.com/akasper/plate/pull/1541) stays green.

4. **Pre-1.0 enforcement:** contract tests fail on stable shrink today (per [#1541](https://github.com/akasper/plate/pull/1541)); should policy text still describe a softer “inventory-only” phase until `v1.0.0` tag?  
   **Recommended default:** policy prose says “1.0 promise starts at tag”; engineering keeps fail-fast contract tests on `release-minor` once [#1541](https://github.com/akasper/plate/pull/1541) lands.

5. **`.plate` `version` field vs GitHub Release semver:** when inventory marks a config key stable, is file `version` bump always major for adopters?  
   **Recommended default:** yes for top-level key add/remove; optional nested keys minor when `gh plate config upgrade` can migrate automatically.

6. **LTS / long-term support branches**  
   **Recommended default:** out of scope for #1057; defer to #654 negotiation.

---

## Recording status

- This curiosity draft does **not** clear stub labels on [#1057](https://github.com/akasper/plate/issues/1057).
- Implementation PRs above are authoritative for inventory, snapshot, reference, and loaders; #1057 Design PR should not contradict them.

**References**

- Epic [#1055](https://github.com/akasper/plate/issues/1055) · Issues [#1056](https://github.com/akasper/plate/issues/1056), [#1058](https://github.com/akasper/plate/issues/1058)  
- PRs [#1536](https://github.com/akasper/plate/pull/1536), [#1538](https://github.com/akasper/plate/pull/1538), [#1541](https://github.com/akasper/plate/pull/1541), [#1547](https://github.com/akasper/plate/pull/1547)  
- Release ceremony: `docs/design/release-ceremony-refinement.md`, `docs/agents/branch-model-and-ceremonies.md`  
- Self-migrate: #649 · User docs: #1065