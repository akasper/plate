---
name: code-review
description: Review pull requests in PLATE repositories for process compliance, release evidence, and implementation hygiene.
---

# PLATE code review

Use this checklist when reviewing a pull request. Comment on anything that fails. Prefer one clear comment per theme.

## Issue link and PR type

- When the PR should close a driving issue on merge, the body includes `Closes #n`, `Fixes #n`, or `Resolves #n` (or the repo's documented equivalent). `Feedback Response` PRs are exempt from the issue-link gate where AGENTS.md says so.
- The PR carries exactly one required type label: `Bug`, `Feature`, `Documentation`, or `Feedback Response`.
- When a closing keyword links an issue, the PR type label must follow AGENTS.md issue-to-PR mapping:
  - `Feature` issue → `Feature`
  - `Bug` issue → `Bug`
  - `Research`, `Design`, `Question`, `Audit`, `Migration`, `Epic`, and `Release` issues → `Documentation`
  - `Task` issues normally close via the Task completion comment; use `Documentation` when a PR artifact is required for follow-up docs.

## Release fragment

- A release fragment exists for this change when the work is a Feature or changes PLATE process, templates, agent surfaces, or tooling.
- The fragment is valid JSON with required fields (`slug`, `change_type`, `surface`, `summary`, `migration_impact`, `agent_notes`).
- `change_type` is one of `feature`, `fix`, `docs`, `process`, or `breaking` (per `.agentic/releases/unreleased/README.md`) and matches the actual change (for example `feature` for Feature work, `fix` for bug fixes—a `fix` fragment for feature work fails review).
- Epic-scoped work lives under `.agentic/releases/epic-<NNN>-<slug>/`; other unreleased work lives under `.agentic/releases/unreleased/`, per the releases README.

## Labels and scope

- Labels match the issue: type, `area:*`, and `risk:*` where the repo expects them.
- The change does not edit `.plate` unless the linked issue explicitly requires `.plate` changes.

## Documentation layout

- Imported or vendored PLATE documentation lives under `docs/plate/`, not scattered at repo root.

## Tests

- Tests use the repository's real test runner. In plate-core that is stdlib `unittest` via `python -m unittest discover`.
- New or changed tests must not `import pytest` unless the project explicitly adopted pytest.

## Subprocess and scripts

- Subprocess calls go through the project helper (`plate_core.procutil`) so Windows does not flash console windows.
- Scripts are POSIX shell (`.sh`) by default. PowerShell (`.ps1`) appears only when the project declares Windows support in `.plate` or documented platform policy.

## Claims

- Release fragments, release notes, and user-facing docs do not overstate behavior. Wording matches what the code and tests actually do.
