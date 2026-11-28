# Refinement drafts: 1.0 security and supportability (Epic #1059)

**Parent Epic:** [#1059](https://github.com/akasper/plate/issues/1059)  
**Roadmap anchor:** [#654](https://github.com/akasper/plate/issues/654) (1.0 definition, 2026-10-04)  
**Milestone:** 1.0  
**Status:** Draft refinement only — does not edit issues, labels, or stub bodies.

---

## Overview

Epic #1059 covers `SECURITY.md`, token-scope documentation, a secret-redaction audit, troubleshooting content (#1063 owns it; #1065 links), and optionally `gh plate doctor` (#1064). Five child stubs: #1060–#1064.

This file records **gaps and ordering** for stubs that still need refinement. Where an open PR or merged artifact already defines scope, this doc **defers** to it and does not propose alternate paths, filenames, or command shapes.

---

## Discovery (2026-11-28)

| Issue | Open PR body match | Issue comments | In-repo artifact (not a PR) |
|---|---|---|---|
| #1060 | [**#1534**](https://github.com/akasper/plate/pull/1534) — root `SECURITY.md` + README link; `Closes #1060` | None | — |
| #1061 | [**#1535**](https://github.com/akasper/plate/pull/1535) — `docs/security/token-scopes.md`; PR states it **is the refinement** for #1061; `Closes #1061` | None | — |
| #1062 | None (only #1558 refs Epic) | None | — |
| #1063 | None | None | [`docs/wiki/Troubleshooting.md`](../wiki/Troubleshooting.md) — symptom notes; defers “fuller guide” to #1063 |
| #1064 | None | None | `gh plate runner doctor` only; wiki/catalog promise top-level `gh plate doctor` |

**Search method:** `gh pr list --state open --search "<n> in:body"` per stub; `gh api …/issues/<n>/comments` (all empty for #1060–#1064).

---

## Recommended order (unchanged intent from #1059)

1. #1060 via #1534 → 2. #1061 via #1535 → 3. #1062 audit → 4. #1064 and/or #1063 (parallel possible) → 5. #1063 links from README / #1065.

Cross-links: #1057 (supported versions, SECURITY wording); #1054 (branch protection / `pr-gates`); token cross-link from troubleshooting should use **`docs/security/token-scopes.md`** after #1535 merges.

---

## High-level gaps (orientation only — no exploit detail)

| Area | Gap | Where to look |
|---|---|---|
| Disclosure | Root policy in flight in #1534 | PR #1534 |
| Token matrix | In flight in #1535 | `docs/security/token-scopes.md` (PR branch) |
| Redaction | Helpers exist; no audit record yet | `github_client.py`, `tasks.py`, `issue_lifecycle_events.py`, `mcp_server.py`, workflows |
| Doctor | Docs promise `gh plate doctor`; CLI has `health` + `runner doctor` only | `cli.py`, `docs/wiki/Home.md` |
| Troubleshooting | Wiki has adopter symptoms only | `docs/wiki/Troubleshooting.md` |

---

## #1060 — SECURITY.md with disclosure path

### Source of truth

**[PR #1534](https://github.com/akasper/plate/pull/1534)** — do not duplicate or contradict its `SECURITY.md` or README wording in other drafts.

### Remaining gaps only (from #1534 open questions — not re-specified here)

1. Template payload: whether `src/plate_core/template_payload/` ships a `SECURITY.md` or pointer via import-payload.
2. Supported versions vs [#1057](https://github.com/akasper/plate/issues/1057) — #1534 deliberately stays on “latest release” until #1057 lands.
3. GitHub private vulnerability reporting enabled on the repo (human/settings; not in PR diff).

### Refinement note

Stub clearance for #1060 is tied to **merge of #1534** and Andrew’s choice to `Closes #1060`. Follow-ups above should be **new issues**, not a second root policy PR.

### Open questions for Andrew (#1060-only)

1. Template payload SECURITY copy — pointer vs full copy vs omit?  
   **Default:** Pointer stub in template payload linking adopters to their own policy + upstream PLATE policy.

2. File follow-ups as new issues after #1534 merge?  
   **Default:** Yes.

*(No proposed `SECURITY.md` content in this document.)*

---

## #1061 — Token-scope documentation

### Source of truth

**[PR #1535](https://github.com/akasper/plate/pull/1535)** and **`docs/security/token-scopes.md`** on that branch. The PR body states known stub scope is implemented there; human `need:security-review` remains before merge.

### What this draft adds (gaps not closed by #1535)

- **Epic wiring:** After merge, link `docs/security/token-scopes.md` from README and/or `SECURITY.md` if not already in #1534/#1535.
- **#1062 input:** Audit should use this file as the permissions baseline (no second token doc).
- **#1063 input:** Troubleshooting “auth/scopes” remedies should link here, not restate workflow tables.

### Open questions — defer to #1535 / doc § Open questions

Do **not** duplicate the six items in PR #1535 (fine-grained PAT mapping, org bootstrap role, `pages.yml` permissions, orchestrator stub, Copilot CI token, GraphQL vs REST messaging). Treat that PR + `docs/security/token-scopes.md` as authoritative; add answers via PR #1535 follow-up commits or a small Documentation PR after merge.

### One Epic-level question (not in #1535 body)

1. Clear `status:stub` on #1061 on #1535 merge vs keep open until README/`SECURITY.md` links land?  
   **Default:** Clear on merge if AC in stub is satisfied by the doc alone; link README in same or immediate follow-up.

*(No alternate path such as `docs/plate/security/` — rejected to avoid conflicting with #1535.)*

---

## #1062 — Audit: secret-redaction audit

**No open PR or issue comment refinement found.** Draft below is the refinement source until implementation PR exists.

### Proposed scope

Audit PLATE-controlled **output channels** (logs, comments, artifacts, MCP payloads, local JSONL) for accidental secret disclosure. Use static review + existing tests; no live secret injection into GitHub.

| Channel | Code / path | Existing control |
|---|---|---|
| `gh api` errors | `src/plate_core/github_client.py` | `_sanitize_error` |
| Task / blocker bodies | `src/plate_core/tasks.py` | `redact_sensitive` |
| Lifecycle JSONL | `src/plate_core/issue_lifecycle_events.py` | `scrub_issue_lifecycle_payload` |
| Babysit / wake text | `src/plate_core/pr_babysit.py` | Policy + extraction paths |
| MCP returns | `src/plate_core/mcp_server.py` | Spot-check tier-1 tools |
| Automation comments | `.github/workflows/` | Template / script review |
| Discussions | `src/plate_core/discussions.py` | `GhClient` |

**Artifact:** `docs/audits/secret-redaction-1059.md` (per AGENTS.md Audit loop) + Bug/Hardening issues per gap.

### Non-goals

Exploit reproduction, downstream adopter app code, weakening gates to pass audit.

### Draft acceptance criteria

- [ ] Audit record lists channels, result, follow-up issue IDs. It records code locations and status only, never sample secrets or captured secret values.
- [ ] No unmitigated high-severity gaps in PLATE emitters without documented human acceptance.
- [ ] Regression tests where review finds weak coverage (`tests/test_tasks.py`, `tests/test_github_client.py` baseline today).

### Dependencies

After **#1535** merges (permission baseline). Before #1063 “secrets in output” troubleshooting section.

### Open questions for Andrew

1. Accept documented medium-risk gaps for 1.0? **Default:** No high-severity; medium with issues OK.  
2. MCP depth — tier-1 tools full pass vs entire `mcp_server.py`? **Default:** Tier-1 + checklist for rest.  
3. CI log review in scope? **Default:** Yes for PLATE-shipped workflows.

---

## #1063 — Troubleshooting and doctor guide (owner)

**No open PR or issue comment refinement found.** Partial content exists on `main`.

### Existing artifact (source of truth for current wiki material)

[`docs/wiki/Troubleshooting.md`](../wiki/Troubleshooting.md) — install/upgrade, PEP 668, Windows babysit flashes (#1073). Header states the **fuller guide is #1063**.

Do not replace or relocate this file without an explicit #1063 implementation decision; **extend** it and/or add a README-linked hub that points here.

### Proposed scope (gaps vs stub AC)

- Map **`gh plate health`** / `HealthReport` fields (`src/plate_core/health.py`, `cmd_health`) to remedies: labels → `gh plate bootstrap --apply`; protection / stale `pr-gates` → branch-model docs + #1054; `.plate` layout; budget (#634); SPEC audit; adoption/self-migrate signals.
- Auth/scopes: link **`docs/security/token-scopes.md`** (#1535), not inline tables.
- Runners: `docs/migration/self-hosted-runners.md` + `gh plate runner doctor`.
- **Doctor:** Until #1064 ships, state clearly that **`gh plate doctor` is not implemented**; use `gh plate health` and `gh plate runner doctor`. Align `docs/wiki/Home.md` and catalog strings in a separate doc PR if 1.0 accepts health-only.

### Non-goals

Duplicate #1065 quickstart/concepts ([#1532](https://github.com/akasper/plate/pull/1532) is separate user-docs track).

### Draft acceptance criteria

- [ ] Stub AC: guide exists, README-linked, #1065 references this owner doc.
- [ ] Each major `cmd_health` line has a remedy or “informational only”.
- [ ] No false `gh plate doctor` claims.

### Dependencies

#1535 merge (scopes link); #1062 summary (high-level leaks section, no repro); #1064 optional for doctor section text.

### Open questions for Andrew

1. Expand **`docs/wiki/Troubleshooting.md`** in place vs new `docs/troubleshooting.md` hub + wiki sync? **Default:** Expand wiki in place; README links to `docs/wiki/Troubleshooting.md`.  
2. 1.0 bar if #1064 slips — health-only + doc fixes OK? **Default:** Yes.  
3. Merge symptom content with health-class index in one page or split “operator symptoms” vs “health report legend”? **Default:** One page with two top-level sections.

---

## #1064 — Feature: `gh plate doctor`

**No open PR or issue comment refinement found.**

### Proposed scope

Top-level `gh plate doctor` in `src/plate_core/cli.py`: wraps `get_health`, structured remedies, `--json` for agents; `--apply` only for allow-listed low-risk fixes (likely label/bootstrap paths only — mirror bootstrap safety). Distinct from **`gh plate runner doctor`** (`src/plate_core/runner.py`).

### Non-goals

Auto-fix branch protection, workflows, secrets, autonomy gates (`docs/agents/autonomous-mode.md`).

### Draft acceptance criteria

- [ ] Subcommand exists; docs (#1063) updated.
- [ ] `--apply` guardrails tested; exit non-zero on failure.
- [ ] Release fragment for Feature.
- [ ] New public surface registered: `gh plate doctor` (and any flags) added to the public-surface inventory (#1536), the CLI/MCP reference (#1538, drift check passes), and the `public_surface_stable.json` snapshot (#1541), or explicitly classified experimental there.

### Dependencies

After #1536, #1538 and #1541 merge (inventory, reference and snapshot must exist to update). #1063 doctor section follows this.

### Open questions for Andrew

1. Ship minimal doctor for 1.0 vs defer and fix wiki/catalog references only? **Default:** Ship minimal (health + remedies + narrow `--apply`).  
2. `--apply` allow-list day one? **Default:** Label sync / bootstrap-class fixes only.  
3. MCP `plate_doctor` same release? **Default:** Defer; use `gh plate doctor --json`.

---

## Cross-cutting questions (Epic #1059)

1. Refinement closure: edit stub bodies on GitHub after Andrew answers, or Documentation PR only? **Default:** Human clears stub labels per `agents/stub-issues.md`.  
2. Security review: per PR (#1534, #1535, #1062 audit PR). **Default:** Yes.

---

## Stub coverage

| Issue | This doc’s role |
|---|---|
| #1060 | Points to #1534; gaps only |
| #1061 | Points to #1535; Epic wiring only |
| #1062 | Full refinement draft |
| #1063 | Full draft; respects existing wiki page |
| #1064 | Full refinement draft |

---

## References

- Epic #1059, Release #654  
- PR #1534 (#1060), PR #1535 (#1061)  
- Wiki: `docs/wiki/Troubleshooting.md`, `docs/wiki/Home.md`  
- Style: `docs/curiosity/refinement-qa-pack-1009-new-repo-standard-workflows.md`