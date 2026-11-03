<!--
  ⚠️  AGENT REQUIRED ACTION — LABELS
  Checking boxes in GitHub's PR form does NOT apply labels.
  Apply exactly one type label when you create or edit the PR:

    gh pr create --label "Feature" ...
    gh pr edit NUMBER --add-label "Feature"

  Valid PR type labels: Bug | Feature | Documentation
  Missing or multiple type labels fail PLATE Label Check CI.

  Copilot and Grok Build: PR titles are for humans. Keep titles clean and descriptive.
  Do not use bracketed prefixes ([Feature], [WIP], [DRAFT], …) or colon-style status prefixes.
  Do not put (Closes #N) or similar metadata in the title. Use labels, draft status,
  milestones, and body closing keywords instead (see AGENTS.md).
-->

# PLATE Pull Request

## Summary

<!-- One or two sentences: user or process outcome, and whether behavior, tests, docs, or release posture changes. -->

## What changed

<!-- Bullet list of the main edits. Name files or subsystems only when it helps reviewers find the diff. -->

## How verified

<!-- Commands run, tests added, or manual checks — one line per check; no pasted log dumps. -->

## Links

- `Closes #N` (or `Fixes #N` / `Resolves #N`) when merge should close an issue — required for Feature, Bug, and issue-driven Documentation PRs unless `no-issue` applies
- Apply exactly one PR type label: `Bug`, `Feature`, or `Documentation` (see comment at top of this file)
- Feature PRs: add or update a per-feature change file under `.agentic/releases/` (unreleased fragment or version directory)

## Visual evidence

For UI or user-visible changes, embed **desktop** and **320px-wide mobile** screenshots inline (before/after when possible). **Do not commit images** to the repository.

1. Reference the image in the PR body markdown:

   `![short alt text](./screenshot.png)`

2. Attach the file when creating or editing the PR (GitHub stores the image; the body uses the reference above):

   ```bash
   gh pr create --title "…" --body-file body.md --attach ./screenshot.png
   gh pr edit NUMBER --body-file body.md --attach ./screenshot.png
   ```

Do not use repo-relative paths or raw blob URLs for screenshots in the description.

If no UI files changed, use this line instead of images:

`Visual evidence: not applicable — <reason>`
