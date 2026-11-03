<!--
  ⚠️  AGENT REQUIRED ACTION — LABELS
  The checkboxes under "PR type label" are documentation only. They do NOT apply GitHub labels.
  Apply exactly one type label at creation or edit time:

    gh pr create --label "Feature" ...
    gh pr edit NUMBER --add-label "Feature"

  Valid PR type labels: Bug | Feature | Documentation
  Missing or multiple labels fail CI (label-check).
-->

# PLATE Pull Request

## PR type label

Select exactly one and apply it on GitHub (not by checking a box here).

- [ ] `Bug`
- [ ] `Feature`
- [ ] `Documentation`

## Summary

One or two sentences on the user or process outcome. Say whether behavior, tests, docs, or release posture changes.

## What changed

-

## How verified

-

## Links

- Closing keyword: `Closes #N` (or `Fixes` / `Resolves`) when merge should close an issue
- Feature PRs: add or update a release fragment under `.agentic/releases/` (see `AGENTS.md`)

## Visual evidence

For UI or other visible changes, attach **desktop** and **320px-wide mobile** screenshots (before and after when possible). Do **not** commit images to git.

1. In this section, write `![alt text](./shot.png)` (the path is for GitHub attachment mapping only — not a repo file).
2. Create or edit the PR with attachments:

   `gh pr create --body-file body.md --attach ./shot.png`

   `gh pr edit NUMBER --body-file body.md --attach ./shot.png`

If no UI files changed, use one line:

`Visual evidence: not applicable — <reason>`

## Agent review models

Warn-only in this release; human merge approval is unchanged. Use `copilot` when GitHub Copilot reviewed the PR.

- Author model:
- Reviewer model:
