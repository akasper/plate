# Documentation Index

This directory contains design decisions, research findings, technical architecture, and project guidance.

## Documentation Structure

```
docs/
├── adr/                          # Architecture Decision Records
├── audits/                       # Security, compliance, and team audits
├── bootstrap/                    # Repository setup and initialization
├── design/                       # Product design, UX, and specifications
├── marketing/                    # Release notes, announcements, messaging
├── migration/                    # Data migration, API deprecation guides
├── research/                     # Spike findings, evaluations, technical investigations
├── wiki/                         # Wiki source files for GitHub wiki
├── forward-port-plans/           # Guides for adopting features in downstream projects
└── playwright-e2e-guide.md       # Comprehensive E2E testing and demo GIF guide
```

---

## Quick Reference

### Testing & Quality

| Document | Purpose |
|----------|---------|
| **[Playwright E2E Guide](./playwright-e2e-guide.md)** | Complete guide to writing, running, and recording E2E tests. Covers local setup, test execution, demo GIF generation, CI integration, troubleshooting, and performance tuning. |
| **[Tests/E2E README](../tests/e2e/README.md)** | Quick reference for running tests locally, understanding results, and debugging with Inspector and traces. |
| **[Wiki: Playwright E2E](./wiki/playwright-e2e.md)** | Self-contained wiki guide covering E2E testing overview, quick start, writing tests, recording demos, CI integration, and resources. |

### Documentation & Features

| Document | Purpose |
|----------|---------|
| **[Wiki: Feature Showcase](./wiki/feature-showcase.md)** | How to capture and embed demo GIFs in documentation. Includes format standards, embedding syntax, examples, and GIF gallery index. |
| **[Forward-Port Plan: Playwright E2E](./forward-port-plans/playwright-e2e-adoption.md)** | Guide for adopting Playwright E2E testing in downstream projects from this template. |

### Architecture & Design

| Document | Purpose |
|----------|---------|
| **[bootstrap/](./bootstrap/)** | Repository setup guidance, including GitHub label configuration, branch protection, and wiki initialization. |
| **[design/](./design/)** | Product specifications, UX decisions, and user experience documentation. |

### Research & Investigation

| Document | Purpose |
|----------|---------|
| **[Playwright Asset Strategy](./research/playwright-asset-strategy.md)** | Policy for retaining, embedding, and expiring Playwright artifacts such as videos, traces, HTML reports, and curated GIFs. |
| **[Playwright GIF Generation](./research/playwright-gif-generation.md)** | Cross-platform FFmpeg-based approach for turning Playwright videos into small, embeddable demo GIFs. |
| **[research/](./research/)** | Technical spikes, evaluations, and research findings that informed design decisions. Examples include GIF generation performance analysis and custom agent packaging. |

### Project Operations

| Document | Purpose |
|----------|---------|
| **[adr/](./adr/)** | Architecture decision records documenting major technical choices and their rationale. |
| **[audits/](./audits/)** | Security reviews, compliance audits, and team health assessments. |
| **[marketing/](./marketing/)** | Release notes, project announcements, and external messaging. |
| **[migration/](./migration/)** | Data migration guides, API deprecation notices, and upgrade paths. |

---

## Getting Started

### New to PLATE?

1. Start with [`../README.md`](../README.md) for project overview
2. Review [`../AGENTS.md`](../AGENTS.md) for operating principles
3. Read [`../SPEC.md`](../SPEC.md) for product vision
4. Check [`../CURRENT.md`](../CURRENT.md) for what's implemented

### Setting Up E2E Testing

1. Read [Playwright E2E Guide](./playwright-e2e-guide.md) for complete setup
2. Run `npm run test:e2e` to verify installation
3. Read [tests/e2e/README.md](../tests/e2e/README.md) for local workflows
4. Write your first test using Page Object Model pattern

### Adding Demo GIFs to Docs

1. Write an E2E test for your feature
2. Record demo: `./scripts/e2e-record.sh feature-name --headed`
3. Generate GIF with interactive prompts
4. Commit GIF to `tests/e2e/fixtures/gifs/`
5. Embed in documentation using relative paths
6. Link to test file for transparency

### Forward-Porting to New Projects

1. Review [Forward-Port Plan](./forward-port-plans/playwright-e2e-adoption.md)
2. Copy `playwright.config.ts` and `tests/e2e/` structure
3. Copy recording scripts from `scripts/`
4. Set up `.github/workflows/test-e2e.yml`
5. Update documentation to match your project

---

## Documentation Standards

All documentation in this directory should:

- ✅ **Render correctly on GitHub** — Use standard Markdown, avoid unsupported syntax
- ✅ **Include working code examples** — Examples should be copy-paste ready
- ✅ **Use relative links** — All paths use `../` or `../../` for portability
- ✅ **Have troubleshooting sections** — Include common issues and solutions
- ✅ **Include screenshots or GIFs** — Visual aids improve clarity
- ✅ **Have clear calls-to-action** — End with next steps

### Link Conventions

**From docs/ to root:**
```markdown
[README](../README.md)
[AGENTS](../AGENTS.md)
[CURRENT](../CURRENT.md)
```

**From docs/wiki/ to docs/:**
```markdown
[E2E Guide](../playwright-e2e-guide.md)
[Tests README](../../tests/e2e/README.md)
```

**From CURRENT.md to tests:**
```markdown
[Test file](tests/e2e/specs/example.spec.ts)
[Demo GIF](tests/e2e/fixtures/gifs/example-demo.gif)
```

---

## Maintenance

### Adding New Documentation

1. Create file in appropriate subdirectory (e.g., `docs/research/topic.md`)
2. Add entry to this index with description
3. Update related documents with cross-references
4. Test all relative links before committing
5. Update CHANGELOG.md if it's a significant addition

### Updating Existing Documentation

1. Keep relative link structure intact
2. Test links after moving files
3. Update index if file location changes
4. Run `npm run lint` to catch broken links if available
5. Update CURRENT.md if documentation describes implemented behavior

### Archiving Old Documentation

1. Move to `docs/migration/` or `docs/research/archive/`
2. Update index with archive path
3. Update cross-references in other docs
4. Note deprecation date in file header

---

## Resources

- **[Playwright Docs](https://playwright.dev/)** — Official E2E testing framework
- **[GitHub Wiki Help](https://docs.github.com/en/communities/documenting-your-project-with-wikis)** — Wiki documentation best practices
- **[Markdown Guide](https://www.markdownguide.org/)** — Markdown syntax reference
- **[PLATE Template](https://github.com/akasper/plate_template)** — This repository

---

**Last updated:** 2026-05-27  
**Maintainer:** PLATE Template  
**Questions?** See [`../AGENTS.md`](../AGENTS.md) for support options.
