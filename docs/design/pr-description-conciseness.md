# PR description conciseness — Design Spec

- **Issue:** #1053
- **Epic:** #1048 (Pretty PRs)
- **Date:** 2026-11-03
- **Status:** Draft

## Problem

PR descriptions are often too long for reviewers to scan. The current template uses many tables and invites empty "TBD" cells instead of short, plain answers.

## Design decision

Use a fixed four-section body for narrative text. UI PRs also use a **Visual evidence** section per #1049; that section and its images do not count toward the word target below.

### Section guide

| Section | Purpose | What to write |
|---|---|---|
| **Summary** | Why the PR exists | One or two sentences: user or process outcome, and whether behavior, tests, docs, or release posture changes. |
| **What changed** | Scope of the diff | Bullet list of the main edits. Name files or subsystems only when it helps a reviewer find the diff. Skip boilerplate and file trees. |
| **How verified** | Proof the change works | Commands run, tests added, or manual checks. One line per check; no pasted log dumps. |
| **Links** | Traceability | Closing keyword (`Closes #N`), related issues or ADRs, and links to longer write-ups moved out of the body (see below). Markdown link text counts toward the word target; URL strings do not. |

### Length target

Aim for **about 150 words** of prose across Summary, What changed, and How verified. **Do not count** image alt text, embedded screenshots, URL strings, or the Links section toward that target. Prefer shorter when the change is small.

### Wording (STE-lite)

Write PR descriptions in **STE-lite** plain language, aligned with the style under evaluation in #1086:

- Short sentences, common words, consistent terms.
- One action or fact per sentence.
- Active voice; keep a natural tone.
- Keep technical precision and uncertainty; do not oversimplify safety or behavior claims.

The candidate style prompt and adoption criteria live on #1086 and its child issues. Until STE adoption is decided, treat STE-lite as the default tone for PR bodies in PLATE and downstream templates.

### Where long detail goes

Keep the PR body scannable. Move depth to linked artifacts and point to them from **Links** (or a single line in **What changed**):

| Detail type | Put it here |
|---|---|
| Design rationale, API contracts, research | `docs/design/`, `docs/research/`, or wiki paths — link the file or PR that added it |
| Scope debate, alternatives, checklist replies | GitHub issue comments or the PR conversation |
| Step-by-step test logs, large diffs, screenshots | PR comments, `--attach` on the PR (#1049), or CI artifacts — not the opening description |

Do not duplicate AGENTS.md, SPEC.md, or fragment JSON in the body; link or cite the path.

### Downstream use

The slim PR template (#1049) and agent guidance (#1050) should mirror this structure and length target. They may add required lines (type label note, release fragment note, visual evidence) without expanding narrative sections.

## Optional later enforcement

A **length lint** in CI or `gh plate` is out of scope for #1053 but may follow once templates land.

**Open questions**

- Count words in code fences and command lines, or exclude them like URLs?
- Warn-only vs fail the check; exclude Documentation-only PRs?
- Apply to human-authored bodies, agent-authored only, or both?
- Single global cap (~150) or slightly higher for Release PRs?

## Acceptance evidence

- This file satisfies the #1053 design acceptance criteria.
- #1049 template work implements the four sections and visual evidence add-on.
- Docs CI link and label checks pass on the Documentation PR that adds this file.
