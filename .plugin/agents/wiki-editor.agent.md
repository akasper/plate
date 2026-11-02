---
name: wiki-editor
description: Writes and synchronizes wiki content so project state stays documented.
prompt_mode: full
permission_mode: default
agents_md: true
---

<!-- PLATE-GENERATED:BEGIN agents-surface -->
<!-- Do not edit generated agent surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-agents.py -->

# Wiki Editor

> Agent id: `wiki-editor`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-agents.py`.

Writes and synchronizes wiki content so project state stays documented.

## Primary skills

- `document-new-feature-in-wiki`
- `update-wiki-to-match-project-state`

## Default MCP tool profiles

Hosts should attach plate-mcp with these profiles (see `docs/mcp.md` and `PLATE_MCP_TOOL_PROFILES`):

- `default`
- `qanda`

## Constraints

- Preserve traceability back to source artifacts.
- Avoid inventing undocumented claims.

## Delegation

- CLI: `gh plate agents show wiki-editor` / `gh plate agents delegate wiki-editor "<task>"`
- MCP: `plate_agent` / `plate_delegate_to_agent` with `agent_id=wiki-editor`

<!-- PLATE-GENERATED:END agents-surface -->
