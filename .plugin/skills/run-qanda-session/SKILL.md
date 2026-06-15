---
name: Run Q&A Session
description: Discover, prioritize, present (via native or fallback), and record answers to open Question issues, triggering contemplation against checklist-style answer signals with explicit citations before any Question is considered ready to close.
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Run Q&A Session

> Skill id: `run-qanda-session`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Discover, prioritize, present (via native or fallback), and record answers to open Question issues, triggering contemplation against checklist-style answer signals with explicit citations before any Question is considered ready to close.

**Owning agents:** research-agent, project-manager

## Inputs

- Repo / Epic context
- Open Questions (via MCP or gh plate qanda)

## Outputs

- Recorded answers + Contemplation logs
- New forward-progress issues/artifacts

## Examples

- Run Q&A on the top 3 open informational goals for the current Epic and summarize outcomes.

<!-- PLATE-GENERATED:END skills-surface -->
