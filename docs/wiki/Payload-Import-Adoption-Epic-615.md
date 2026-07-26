# Payload import / adoption (Epic #615) — status summary

**Status (2026-07-26):** Core adoption surfaces **shipped** on `release`; Epic remains **open** until human-gated residual **#622** (agentic escape hatch for hard merges) is resolved or explicitly deferred.

**Epic:** #615 — Safe first-class PLATE template payload import for adoption into existing repos.

## Problem (original)

Greenfield bootstrap assumed template-shaped trees. Mature repos needed a safe, reviewable way to import the template payload without improvising `cp` across turns.

## Delivered children (closed / implemented)

| Issue | Outcome |
|---|---|
| **#616** | `gh plate import-payload` / `plate_import_payload` — local dry-run/apply, strategies safe\|conservative\|force |
| **#617** | Manifest `path_rules` conflict strategies (install_as, conflict, overwrite) |
| **#618** | Seed minimal `CURRENT.md` when absent |
| **#619** | Bootstrap adoption mode (`--adopt` / auto-detect mature repos) |
| **#620** | Shared payload planner for local + remote/bootstrap paths |
| **#621** | Payload discoverability CLI/MCP + `scripts/plate/` namespacing |

Fragments live under `.agentic/releases/unreleased/` (`616-*` … `621-*`) and adoption narrative in `docs/migration/adoption-guide.md`.

## Operator path (current)

```bash
gh plate import-payload --dry-run --strategy conservative --json
gh plate import-payload --apply --strategy conservative
gh plate bootstrap --repo OWNER/REPO --adopt --apply
gh plate health
```

Prefer **conservative** for mature trees; never `force` without human approval on product-owned roots.

## Open residual

| Issue | Blocker | Notes |
|---|---|---|
| **#622** | `need:human-review` | Agentic escape hatch: rich plan + diffs/worktree + optional draft PR / delegated review for irreducible hard conflicts. **Agents must not complete this as a silent full-auto overwrite path**; human judgment stays on complex merges. |

Until #622 lands, hard cases still use: import dry-run report → human-approved selective apply → optional draft PR opened by human/agent with explicit review checklist.

## Non-goals

- Marketplace publish human Tasks (#380/#381)
- Claiming frictionless <30m for every monorepo without review
- Auto-overwrite of high-value product files under `force` without approval

## Links

- Epic #615; children #616–#622
- Design/migration: `docs/migration/adoption-guide.md`
- Related Epic #633 (frictionless integration) may absorb remaining onboarding polish
