# docs/design/

This directory is the required artifact location for `Design` issues in PLATE.

## When to commit here

Every Design issue must close with at least one of:
1. A Markdown file in this directory (`docs/design/<feature-slug>.md`) — written design spec, API contract, data model, or decision record
2. An update to `docs/wiki/Features/<feature>.md` — for designs that surface in the public wiki
3. An Architecture Decision Record in `docs/adr/NNNN-<slug>.md` — for architectural decisions

No Design issue may be closed without a corresponding Documentation PR that commits at least one of the above.

## File naming

Use the kebab-case feature or system slug:

```
docs/design/onboarding-wizard.md
docs/design/culture-index-api-contract.md
docs/design/chat-room-ux.md
```

## File format

```markdown
# [Feature / System Name] — Design Spec

- **Issue:** #N
- **Designed by:** @username or agent session ID
- **Date:** YYYY-MM-DD
- **Status:** Draft | Approved | Superseded

## Problem

[What user or technical problem this design solves]

## Constraints

[Technical, brand, accessibility, security, budget constraints]

## Design Decision

[The chosen approach and rationale]

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| TBD | TBD |

## Artifact

[Wireframes, ASCII mockups, data models, API contract, or links to external design files]

## Open Questions

[Questions requiring follow-up research or human decision — link to `need:decision` issues]

## Acceptance Evidence

[How will we know this design has been implemented correctly?]
```

## Wiki sync

Design files in `docs/wiki/Features/` are synced to the GitHub wiki when `PLATE_WIKI_SYNC_ENABLED=true` and a Feature PR is merged. Design-only Documentation PRs are not automatically wiki-synced; add `need:wiki-sync` if the wiki should be updated.
