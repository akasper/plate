---
name: GitHub Discussions
description: Read, list (with category filters e.g. Ideas), get full content, comment on, and create GitHub Discussions. Encapsulates the gh api + GraphQL strategy for reliable agent/orchestrator use (Ideas capture, inter-agent comms/logs per
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# GitHub Discussions

> Skill id: `github-discussions`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Read, list (with category filters e.g. Ideas), get full content, comment on, and create GitHub Discussions. Encapsulates the gh api + GraphQL strategy for reliable agent/orchestrator use (Ideas capture, inter-agent comms/logs per

**Owning agents:** research-agent, project-manager, dev-relations-expert, project-manager, software-engineer

## Inputs

- repo (owner/name)
- category (slug e.g. 'ideas' or name)
- discussion number / title / body
- filters for state/open

## Outputs

- list of normalized discussions (number, title, url, body, category, counts)
- full discussion record
- comment list / created comment
- created discussion confirmation + url
- category list (for ID resolution on create)

## Examples

- List open Ideas in akasper/plate and summarize gaps vs current AGENTS.md.
- Post inter-agent orchestration state log to a dedicated discussion.
- Create a quick developer note as new Discussion in Ideas category.
- Use plate_list_open_ideas + plate_add_discussion_comment for agent comms.

<!-- PLATE-GENERATED:END skills-surface -->
