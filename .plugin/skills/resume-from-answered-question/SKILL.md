---
name: Resume from Answered (Blocking) Question
description: After a blocking Question is answered, retrieve the full answer + provenance, merge into the original Issue via unblock report + context updates, and resume the paused work.
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Resume from Answered (Blocking) Question

> Skill id: `resume-from-answered-question`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

After a blocking Question is answered, retrieve the full answer + provenance, merge into the original Issue via unblock report + context updates, and resume the paused work.

**Owning agents:** research-agent, project-manager

## Inputs

- Answered blocking Question (with dump marker)

## Outputs

- Unblock report on original Issue
- Merged context + resumed work items

## Examples

- The blocking Question on user personas was answered. Merge the findings and resume the onboarding Feature.

<!-- PLATE-GENERATED:END skills-surface -->
