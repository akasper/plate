# Bootstrap Scaffolding Contract — Design Spec

- **Issue:** #415
- **Designed by:** Copilot session 23eb9967-e96f-472f-af48-937d241267de
- **Date:** 2026-06-09
- **Status:** Draft

## Problem

New PLATE repositories need to start with the repository-level artifacts that teach the process to humans and agents without forcing them to leave the repo.

## Constraints

- Must preserve the existing GitHub bootstrap behavior for labels, wiki, questions, and branch setup.
- Must use the checked-in template payload as the source of truth.
- Must avoid overwriting files that already exist in the target repository.
- Must continue creating `.plate` separately, since it is runtime config rather than template payload content.

## Design Decision

Add a bootstrap phase that walks the selected template payload files, checks each target path in the repository, and uploads only missing files through the GitHub contents API.

The copy phase should:

1. Use the manifest to select payload files.
2. Skip files that already exist in the target repo.
3. Upload file bytes through `gh api` so text and binary scaffold assets both work.
4. Report the result as a summary bootstrap action.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Keep bootstrap GitHub-only | Leaves new repos without the in-repository PLATE scaffold. |
| Overwrite files unconditionally | Risks clobbering local customization in an already-initialized repo. |
| Move payload copying into local scripts only | Would not help `gh plate bootstrap --apply`, which is the authoritative bootstrap entrypoint. |

## Artifact

Bootstrap should create the payload set selected by `template_payload_manifest.yml`, including `AGENTS.md`, `SPEC.md`, `README.md`, docs, workflows, scripts, tests, and starter assets.

## Open Questions

None.

## Acceptance Evidence

The bootstrap command copies the payload into a fresh repository, leaves existing files alone when rerun, and still performs the GitHub-side bootstrap actions.
