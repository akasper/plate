# Bootstrap Artifact Inventory

- **Issue:** #414
- **Researched by:** Copilot session 23eb9967-e96f-472f-af48-937d241267de
- **Date:** 2026-06-09
- **Status:** Completed

## Research Question

Which PLATE template artifacts should `gh plate bootstrap --apply` create in a new repository?

## Sources

- `src/plate_core/data/template_payload_manifest.yml`
- `src/plate_core/template_payload/README.md`
- `src/plate_core/template_payload/docs/bootstrap/new-repository-checklist.md`
- `src/plate_core/template_payload/AGENTS.md`
- `src/plate_core/template_payload/docs/wiki/Goals.md`

## Findings

The template payload already defines the repository-level scaffold that downstream repos should receive. The manifest includes `AGENTS.md`, `SPEC.md`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `package.json`, `playwright.config.ts`, `.github/**`, `.agentic/**`, `docs/**`, `scripts/**`, `tests/e2e/**`, and supporting fixtures.

That payload is the authoritative source for downstream bootstrap content, while `gh plate bootstrap --apply` remains responsible for GitHub-side state such as labels, wiki enablement, branch protection, and starter issues.

## Recommendation

Treat the checked-in template payload as the canonical artifact inventory for repository initialization, and upload those selected files into new repositories during bootstrap.
