---
name: What Next? (PLATE Process Guidance)
description: Use plate_what_next (or equivalent) to get the next recommended PLATE step + prompt segment based on current repo state (health, open Epics, fragments, Goals page, etc.). Enables autonomous drive of the full process. In looped use, the caller must emit only terse bullet turn summaries and follow quiet comment discipline (see quiet_operations guidance and plate persona).
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# What Next? (PLATE Process Guidance)

> Skill id: `what-next-plate-process`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Use plate_what_next (or equivalent) to get the next recommended PLATE step + prompt segment based on current repo state (health, open Epics, fragments, Goals page, etc.). Enables autonomous drive of the full process. In looped use, the caller must emit only terse bullet turn summaries and follow quiet comment discipline (see quiet_operations guidance and plate persona).

**Owning agents:** research-agent

## Inputs

- Current repo state (via plate_health, plate_epic_status, release status, labels)

## Outputs

- next_action + prompt_segment + rationale

## Examples

- Call plate_what_next to decide whether to bootstrap, advance an Epic child, cut release, or babysit a PR.

<!-- PLATE-GENERATED:END skills-surface -->
