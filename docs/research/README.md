# docs/research/

This directory is the required artifact location for `Research` issues in PLATE.

## When to commit here

Every Research issue must close with either:
1. A Markdown file in this directory (`docs/research/<issue-slug>.md`), OR
2. An update to `SPEC.md` (e.g., `§Open Questions`, `§External Integrations`), OR
3. An Architecture Decision Record in `docs/adr/NNNN-<slug>.md`

No Research issue may be closed without a corresponding Documentation PR that commits at least one of the above.

## File naming

Use the kebab-case issue slug or a short descriptive name:

```
docs/research/culturebot-api-availability.md
docs/research/llm-provider-comparison.md
docs/research/slack-bot-permission-scopes.md
```

## File format

```markdown
# [Research Topic]

- **Issue:** #N
- **Researched by:** @username or agent session ID
- **Date:** YYYY-MM-DD
- **Status:** Completed | Superseded by ADR-NNNN

## Research Question

[What was asked]

## Sources

- [Source 1](url)
- [Source 2](url)

## Findings

[Detailed findings]

## Recommendation

[What should be done next; link to follow-up issue or ADR if applicable]
```

## Wiki sync

When `PLATE_WIKI_SYNC_ENABLED=true`, the `sync-wiki-on-merge.yml` workflow does **not** automatically sync `docs/research/` to the wiki. Research findings that should appear in the wiki should be summarized in `docs/wiki/` or `docs/features/` explicitly.
