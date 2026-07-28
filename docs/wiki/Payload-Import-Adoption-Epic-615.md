# Payload import / adoption (Epic #615) — closeout summary

**Status (2026-07-26):** **Complete** on `release`. All children **#616–#622** closed with `status:implemented`; this Epic closes via Documentation PR.

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
| **#622** | Agentic escape hatch: `plan.json` + `PLAN.md` + `DRAFT_PR_BODY.md` via `--escape-hatch` / `--escape-hatch-on-conflict` (and MCP); never silent force on high-value paths |

Fragments live under `.agentic/releases/unreleased/` (`616-*` … `622-*`) and adoption narrative in `docs/migration/adoption-guide.md`.

## Operator path (current)

```bash
gh plate import-payload --dry-run --strategy conservative --json
gh plate import-payload --apply --strategy conservative
# Hard conflicts → reviewable plan + draft PR body (no auto-force):
gh plate import-payload --strategy conservative --escape-hatch-on-conflict --json
gh plate bootstrap --repo OWNER/REPO --adopt --apply
gh plate health
```

Prefer **conservative** for mature trees; never `force` without human approval on product-owned roots. On irreducible conflicts, emit escape-hatch artifacts and open a human-reviewed draft PR from `DRAFT_PR_BODY.md`.

## Residual (out of epic scope / follow-on)

| Item | Notes |
|---|---|
| Auto draft-PR create + worktree apply | Explicit follow-up under #622 notes; still human-gated |
| Epic #633 | Frictionless <30m onboarding polish may absorb remaining UX |
| Epic #649 | Self-update / self-migrate for adopters (separate track) |

## Non-goals (unchanged)

- Marketplace publish human Tasks (#380/#381)
- Claiming frictionless <30m for every monorepo without review
- Auto-overwrite of high-value product files under `force` without approval

## Links

- Epic #615; children #616–#622 (all closed)
- Design/migration: `docs/migration/adoption-guide.md`
- Related: #633 (frictionless integration), #649 (self-updating adopters)
