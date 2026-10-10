---
name: code-review
description: Review pull requests in PLATE repositories for process compliance, release evidence, and implementation hygiene.
---

# PLATE code review

Use this checklist when reviewing a pull request. Comment on anything that fails. Prefer one clear comment per theme.

## Issue link and PR type

- The PR body links its driving issue with `Closes #n`, `Fixes #n`, or `Resolves #n` (or the repo's documented equivalent).
- Feature, Bug, and Documentation PRs must link exactly one issue this way.
- The PR carries the correct type label (`Feature`, `Bug`, or `Documentation`) and it matches the linked issue type.

## Release fragment

- A release fragment exists for this change when the work is a Feature or changes PLATE process, templates, agent surfaces, or tooling.
- The fragment is valid JSON with required fields (`slug`, `change_type`, `surface`, `summary`, `migration_impact`, `agent_notes`).
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
