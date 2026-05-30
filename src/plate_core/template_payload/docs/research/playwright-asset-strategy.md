# Playwright Asset Retention, Storage, and Embedding Strategy

- **Issue:** #134
- **Researched by:** Copilot / PLATE automation
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

What is the right long-term strategy for retaining, storing, and embedding Playwright E2E artifacts so feature PRs can ship durable "feature in action" evidence without bloating the repo or depending on short-lived CI artifacts?

## Sources

- `docs/design/playwright-ci-design.md`
- `docs/research/gif-generation-spike.md`
- `tests/spike-videos/TEST_RESULTS.md`
- `CURRENT.md`
- Playwright docs for `video`, `trace`, and screenshot retention
- GitHub Actions artifact retention defaults

## Findings

The artifact types have different jobs:

| Artifact | Best home | Why |
|---|---|---|
| GIF | Committed repo file | Small, embeddable, durable, easy to render in GitHub markdown |
| Video (`.webm`) | CI artifact only | Good for debugging, too bulky for source control |
| Trace | CI artifact only | Best for step-through debugging, not directly embeddable |
| HTML report | CI artifact only | Useful for review, but transient and large |
| Screenshot | CI artifact or committed only when curated | Good for static evidence, but less useful than GIF for motion |

### Recommended default policy

1. Keep raw Playwright videos, traces, and HTML reports in GitHub Actions artifacts.
2. Commit only curated GIFs for user-visible feature evidence.
3. Embed GIFs in PR bodies, `CURRENT.md`, wiki pages, and release notes.
4. Link trace/report artifacts from PR comments for debugging.
5. Keep artifact retention bounded; 30-90 days is enough for CI diagnostics.

### Repository layout

- Use `tests/e2e/fixtures/gifs/` for committed demo GIFs in the template.
- Keep transient CI outputs out of source control.
- If a downstream repo wants a broader gallery, add `docs/evidence/` and treat it as curated, human-reviewed content only.

### When a GIF is required

Use a committed GIF when the PR changes anything a reviewer can observe in the UI:

- new or changed screens
- onboarding flows
- interactive widgets
- bug fixes with visible behavior
- docs or marketing pages where visual proof helps

Trace + report links are sufficient for:

- backend-only changes
- infrastructure
- CI changes
- refactors with no visual difference
- test-only changes

### Migration guidance

For existing PLATE repos:

1. Keep existing committed demo GIFs if they are still useful.
2. Move raw videos and traces to CI artifacts.
3. Add or update `CURRENT.md` with links to the curated evidence.
4. Add `.gitignore` entries for transient Playwright outputs if a repo currently checks them in.

## Recommendation

Use a dual-track model:

- **Durable evidence:** curated GIFs committed to the repo
- **Debug evidence:** videos, traces, and reports retained as CI artifacts

That gives PLATE the best balance of reviewability, reproducibility, and cost control.
