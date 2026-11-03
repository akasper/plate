# PR description conciseness — Design Spec

- **Issue:** #1053
- **Epic:** #1048 (Pretty PRs)
- **Date:** 2026-11-03
- **Status:** Draft

## Problem

PR descriptions are often too long to scan. The current template uses many tables and empty “TBD” cells. Humans and reviewers need a fixed, short structure with plain wording.

## Target length

Aim for about **150 words** in the filled-in body text. Do not count image alt text, embedded screenshots, or URLs toward that limit.

## Required sections

Use these four headings in order. The slim PR template in [#1049](https://github.com/akasper/plate/issues/1049) mirrors this list. UI changes also use **Visual evidence** from #1049; that section is outside the word target.

| Section | Purpose |
|---|---|
| **Summary** | One or two sentences: what changed and why it matters (product or process). |
| **What changed** | Bullet list of concrete edits (files, behavior, config). No essay. |
| **How verified** | Commands run, tests added, or manual checks. Name the outcome (pass/fail), not a long log. |
| **Links** | Closing keyword (`Closes #N`), related issues, ADRs, wiki pages, or follow-ups. |

Keep required process notes from the template (exactly one PR type label, release fragment note for Features) as short lines under **Links** or **How verified**, not as extra tables.

## Wording (STE-lite)

Follow **STE-lite** as defined in Epic [#1086](https://github.com/akasper/plate/issues/1086): short sentences, common words, one action per sentence, consistent terms, active voice. Keep tone natural; do not sacrifice technical precision.

Avoid filler (“This PR implements…”, “As per the issue…”). Prefer verbs: “Add”, “Fix”, “Remove”, “Update”.

## Where long detail goes

Do not paste specs, stack traces, or meeting notes into the PR body. Put them in linked artifacts and point from **Links**:

- Design or research docs under `docs/`
- The issue thread or a PR comment for step-by-step notes
- `.agentic/releases/` fragments for Feature traceability
- Wiki pages for user-facing behavior

The PR body should let a reviewer decide whether to open those links.

## Optional length lint (out of scope here)

A future check could warn when prose (excluding images and links) exceeds ~150 words or when required headings are missing. Open questions:

- Count words in comments/HTML only, or also in checklist lines?
- Warn only, or block merge?
- Apply to agent-opened PRs first, or all PRs?

Implementation is a separate issue; this doc is the source of guidance.

## Acceptance mapping

| Criterion | Where |
|---|---|
| Four sections defined | **Required sections** |
| ~150 words; images/links excluded | **Target length** |
| STE-lite | **Wording (STE-lite)** → #1086 |
| Detail in linked artifacts | **Where long detail goes** |
| Template alignment | **Required sections** → #1049 |
| Lint as future option | **Optional length lint** |
