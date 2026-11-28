# Refinement drafts: 1.0 user documentation (Epic #1065)

**Parent Epic:** [#1065](https://github.com/akasper/plate/issues/1065)  
**Roadmap anchor:** [#654](https://github.com/akasper/plate/issues/654) (1.0 definition, 2026-10-04 — user docs bar)  
**Milestone:** 1.0  
**Status:** Draft refinement only — does not edit issues, labels, or stub bodies.

---

## Overview

Epic #1065 delivers a short **human** docs set: quickstart, concepts, CLI/MCP reference, upgrade guide, plus a **link** to troubleshooting (owned by [#1063](https://github.com/akasper/plate/issues/1063) under Epic #1059; content lives in [`docs/wiki/Troubleshooting.md`](../wiki/Troubleshooting.md) — do not duplicate here).

Child stubs: #1066 (quickstart), #1067 (concepts), #1068 (reference), #1069 (upgrade guide).

This file records **gaps, dependencies, and ordering** only. Where an open PR already defines paths and acceptance criteria, this doc **defers** to that PR and does not propose conflicting filenames or layouts.

**Monorepo layout default (this repo):** top-level user docs under `docs/` (`docs/quickstart.md`, `docs/concepts.md`, `docs/cli-mcp-reference.md`, `docs/upgrade-guide.md`). Adopters with namespaced import (#1015) mirror the same filenames under `docs/plate/`; cross-links in user docs should say so once in a short “adopter paths” note — not four different layouts.

---

## Discovery (2026-11-28)

| Issue / Epic | Open PR body match | Issue comments | In-repo artifact on `release-minor` |
|---|---|---|---|
| #1065 (Epic) | [#1532](https://github.com/akasper/plate/pull/1532) refs parent | None | README install pins **0.12.0**; no unified “User documentation” table until #1532/#1533 merge |
| #1066 | [**#1533**](https://github.com/akasper/plate/pull/1533) — `docs/quickstart.md` + README; `Refs #1066` | None | [`docs/migration/adoption-guide.md`](../migration/adoption-guide.md) still cites **0.10.0** (drift vs README) |
| #1067 | [**#1532**](https://github.com/akasper/plate/pull/1532) — `docs/concepts.md` + README table; `Refs #1067` | None | — |
| #1068 | [**#1538**](https://github.com/akasper/plate/pull/1538) — `docs/cli-mcp-reference.md`, `scripts/generate-cli-mcp-reference.py`, drift test; `Closes #1068` (stacked on #1536) | None | — |
| #1069 | None | None | Upgrade prose scattered: README “Keeping Your Fork Current”, [`namespace-docs-migration.md`](../migration/namespace-docs-migration.md), wiki Troubleshooting § upgrade |
| (compat input) | [#1536](https://github.com/akasper/plate/pull/1536) — inventory; [#1541](https://github.com/akasper/plate/pull/1541) — stable snapshot | — | Reference + upgrade guide **depend** on inventory for stable surface names |
| (troubleshooting) | #1558 refs #1063 only | None | [#1063](https://github.com/akasper/plate/issues/1063) owner: extend wiki, not Epic #1065 body |

**Search method:** `gh pr list --state open --search "<n> in:body"` per stub (#1066–#1069, #1065); issue comments empty for all four children.

**Not duplicated:** SECURITY.md ([#1534](https://github.com/akasper/plate/pull/1534)) — security Epic #1059, not user-docs scope except README cross-link if needed.

---

## Recommended order (Epic #1065)

1. **#1067 / #1532** and **#1066 / #1533** in parallel (no code dependency; both should agree on pin table and README hub).
2. **#1536** → **#1538** (#1068) merge stack; then add README link to `docs/cli-mcp-reference.md` if not already in a merged PR.
3. **#1069** upgrade guide after quickstart pin discipline is settled (reuse same verify commands); link deprecations when [#1057](https://github.com/akasper/plate/issues/1057) policy lands.
4. **Epic closure wiring:** README user-docs table includes troubleshooting → `docs/wiki/Troubleshooting.md` (#1063); optional single “start here” sentence pointing quickstart → concepts → reference.
5. **#1070** live adopter proof exercises quickstart path (validation, not a replacement doc).

Cross-links: `#1063` troubleshooting; `#1055`/`#1056` public surface; `#649` self-migrate; `#1015` namespaced docs paths.

---

## Epic-level gaps (orientation)

| Gap | Owner / source |
|---|---|
| README hub for all five surfaces (four docs + troubleshooting link) | Coordinate across #1532, #1533, #1069 PR, human edit |
| Pin consistency across user docs | README **0.12.0** vs adoption-guide **0.10.0** — fix in adoption-guide or quickstart “see also” (separate small doc PR; not this planning file) |
| Stub labels remain until Andrew clears per `agents/stub-issues.md` | Implementation PRs may ship content while stubs stay `status:stub` |
| 1.0 verification | #1070 third-party proof; quickstart is rehearsal script |

---

## #1066 — Documentation: quickstart

### Source of truth

**[PR #1533](https://github.com/akasper/plate/pull/1533)** — `docs/quickstart.md` on branch `cursor/quickstart-1066`. Do not author a second quickstart path (for example `docs/plate/quickstart.md` in this monorepo).

### What #1533 already covers (do not re-specify)

Install pin, greenfield vs adoption, `import-payload`, `bootstrap --adopt`, `health`, `what-next`, first Feature PR (`release status`, `pr preflight` / `pr create`, `pr babysit`), release `cut` / `finalize` overview; command index dry-run verified in PR body.

### Gaps only (remaining refinement / follow-up)

- **README link:** quickstart must appear in the user-docs table (#1532 started the table; ensure #1533 merge includes quickstart row).
- **Adoption-guide drift:** [`docs/migration/adoption-guide.md`](../migration/adoption-guide.md) prerequisites still pin **0.10.0**; quickstart/README use **0.12.0**. Either update adoption-guide in the #1533 stack or a immediate follow-up Documentation PR (avoid two competing pin tables in user-facing paths).
- **#1070 rehearsal:** quickstart should list the minimal command sequence third-party adopters will time; link `docs/migration/adoption-guide.md` for extended adoption, not duplicate it.
- **First Q&A live seed:** #1533 defers `adopt --apply-first-qa` when runner not injectable — acceptable for 1.0 if called out; #1070 may require explicit human step.
- **Stub clearance:** #1533 adds a release fragment; stub AC “linked from README” is met on merge; `status:stub` clearance is human.

### Draft acceptance criteria (gaps layered on stub)

- [ ] `docs/quickstart.md` merged via #1533; README links it.
- [ ] Operator can complete install → `health` → first value **without reading `AGENTS.md`** (stub AC).
- [ ] No user-doc path cites obsolete **0.8.0** pins (Epic #1065 success criterion); quickstart matches README **0.12.0** table.
- [ ] Troubleshooting link points to #1063 owner doc, not inline duplicate.

### Dependencies

None blocking merge of #1533; adoption-guide pin fix soft-depends on Andrew’s choice of single “current pin” source (README vs quickstart only).

### Open questions for Andrew (#1066)

1. Does shipping #1533 satisfy refinement without a separate “refinement PR” that only edits the issue body?  
   **Default:** Yes — content PR is the artifact; human clears stub labels after review.

2. Headline time budget in user docs: **&lt;15m** (SPEC bootstrap) vs **30m** adoption proof (#633 / #1070)?  
   **Default:** Quickstart says “under 30m adoption path”; footnote SPEC greenfield metric where it differs (#1533 open question).

3. Minimal first-Q&A subsection in quickstart for #1070?  
   **Default:** One short “optional seed” paragraph linking adoption-guide §4 unless proof requires inline steps.

4. Align `docs/migration/adoption-guide.md` pins in #1533 vs follow-up?  
   **Default:** Follow-up Documentation PR immediately after #1533 merge (keeps #1533 diff focused).

*(Defer PR #1533 open questions on SPEC MCP install line and CONTRIBUTING branch prose to that PR — not duplicated here.)*

---

## #1067 — Documentation: concepts guide

### Source of truth

**[PR #1532](https://github.com/akasper/plate/pull/1532)** — `docs/concepts.md` on branch `cursor/concepts-1067-198c`.

### What #1532 already covers

Human-oriented model: issues, labels, release tracks, fragments, PR lifecycle, babysitting, Tasks, `.plate` — sourced from `SPEC.md`, `AGENTS.md`, `docs/agents/*`, `docs/design/*`, `.github/labels.yml`.

### Gaps only

- **README user-docs table:** #1532 adds concepts link; ensure quickstart (#1533) and reference (#1538) rows land in same table without conflicting column names.
- **SPEC alignment:** terms must match labels registry; PR notes `Documentation` label description vs issue-type usage — optional follow-up on `.github/labels.yml`, not concepts prose.
- **Epic #1065 “not AGENTS.md”:** concepts should remain approachable; deep agent ceremony stays in `docs/agents/*` with links only.
- **Stub clearance:** #1532 explicitly does not clear stub labels on GitHub.

### Draft acceptance criteria (gaps layered on stub)

- [ ] `docs/concepts.md` merged via #1532; README links it (stub AC).
- [ ] Terminology traceable to `SPEC.md` and `.github/labels.yml` (stub AC “match SPEC and labels”).
- [ ] No contradiction with multi-track branch model in `docs/design/release-ceremony-refinement.md` (document “ask `gh plate release status`” as the chooser).

### Dependencies

Soft: #1532 can merge before #1538; add one sentence in concepts pointing to `docs/cli-mcp-reference.md` after #1538 merges.

### Open questions for Andrew (#1067)

1. Epic-close base branch wording: legacy `release` vs `release-minor` / multi-track — concepts documents both today; pick one “default for this monorepo” sentence?  
   **Default:** “Run `gh plate release status` for integration base” (#1532 Q2 default).

2. User-docs path for adopters (#1015): standardize hub under `docs/plate/` on import only, monorepo stays `docs/concepts.md`?  
   **Default:** Yes (#1532 Q4 default).

3. Clear #1067 stub on #1532 merge vs wait for README table complete?  
   **Default:** Clear when concepts + README link merged; table completion can follow in #1533/#1538.

*(Other #1532 open questions: Documentation label registry, Major/Minor/Patch CI enforcement — defer to that PR.)*

---

## #1068 — Documentation: CLI and MCP reference

### Source of truth

**[PR #1538](https://github.com/akasper/plate/pull/1538)** — generated [`docs/cli-mcp-reference.md`](../cli-mcp-reference.md) (on PR branch), `scripts/generate-cli-mcp-reference.py`, `plate_core.cli_mcp_reference`, `tests/test_cli_mcp_reference.py`. **Do not hand-write** a parallel reference doc.

Stable membership comes from [**#1536**](https://github.com/akasper/plate/pull/1536) / `docs/plate/research/public-surface-inventory.md`. Contract tests in [**#1541**](https://github.com/akasper/plate/pull/1541) are adjacent compat work, not a second reference.

### What #1538 already implements (stub AC)

- Lists stable CLI leaf invocations and MCP tools with generation + `--check` drift path (stub AC).
- PR body states issue refinement is satisfied by implementation (`Closes #1068`).

### Gaps only (post-#1538 / Epic wiring)

- **Merge order:** #1538 targets `plate/1056-public-surface-inventory`; retarget to `release-minor` after #1536 merges (per PR note).
- **README link:** Epic #1065 success criterion — add `docs/cli-mcp-reference.md` to user-docs table when merged (if not in #1538 diff).
- **CI:** optional wire `python3 scripts/generate-cli-mcp-reference.py --check` in `.github/workflows/ci.yml` (#1538 open question).
- **Inventory-first workflow:** when stable classification changes, update #1536 inventory then regenerate reference (document in upgrade guide § “tooling/docs drift”).

### Draft acceptance criteria (Epic-only extras)

- [ ] Generated reference is the **only** maintained command/tool catalog for adopters (quickstart/concepts link here; no duplicate tables).
- [ ] Drift check runs in CI or documented maintainer step before release cut (pick one in #1538 follow-up).

### Dependencies

**Hard:** #1536 merged before #1538. **Soft:** #1541 for deprecation JSON when upgrade guide cites removed surfaces.

### Open questions for Andrew (#1068)

1. Wire generator `--check` in CI on every PR?  
   **Default:** Yes alongside other surface generators (#1538 Q1 default).

2. Classify undispatched MCP tools in inventory before 1.0 freeze?  
   **Default:** Yes — inventory PR #1536 open questions; reference regenerates after inventory edit.

3. Stub closure: #1538 uses `Closes #1068` — accept implementation-as-refinement?  
   **Default:** Yes.

4. README stable-surface summary table vs full generated doc — keep README short pointer only?  
   **Default:** README pointer + full `docs/cli-mcp-reference.md`.

*(Do not duplicate #1538 questions on regex MCP parsing or `plate_release_media_*` stable classification — see that PR.)*

---

## #1069 — Documentation: upgrade guide

**No open PR or issue comment refinement found.** Draft below is the refinement source until an implementation PR exists.

### Proposed artifact

**`docs/upgrade-guide.md`** at repo root docs (monorepo). Same file name under `docs/plate/` for namespaced adopters (#1015). **Do not** fold into `adoption-guide.md` (first-time adopt) or replace README “Keeping Your Fork Current” wholesale — link and specialize.

### Proposed scope (human operator)

| Section | Content source (link, do not copy wholesale) |
|---|---|
| Before you upgrade | Pin verify: `pip` + `gh extension` + `gh plate self-migrate --verify --json` (README table) |
| Patch / minor (plate-core + gh-plate) | `pip install -U 'plate-core==X.Y.Z'`, `gh extension upgrade plate`, reinstall path after gh-plate history rewrite ([`Troubleshooting.md`](../wiki/Troubleshooting.md)) |
| PLATE payload / markers | `gh plate self-migrate --plan` / `--apply`, `gh plate import-payload`, marker merge per README § Keeping Your Fork Current |
| Docs namespace (0.8.x → namespaced) | `gh plate migrate-docs-namespace` — [`namespace-docs-migration.md`](../migration/namespace-docs-migration.md) |
| Breaking / deprecated surfaces | Point to #1057 policy when published; until then link `docs/plate/research/public-surface-inventory.md`, `tests/fixtures/public_surface_deprecations.json` (#1541), and release notes under `.agentic/releases/v*/` |
| 0.x → 1.0 checklist | Multi-track branches, fragment layout, label changes — release notes + self-migrate plan; **no** fixed calendar; semver per #654 |

### Non-goals

- Marketing / docs site (#641).
- Rewriting `AGENTS.md` / `SPEC.md`.
- Troubleshooting remedies (link #1063 wiki).
- Duplicating full CLI/MCP lists (link `docs/cli-mcp-reference.md`).

### Draft acceptance criteria

- [ ] `docs/upgrade-guide.md` exists; README user-docs table links it (stub AC).
- [ ] Covers **0.x → 1.0** and **minor-to-minor** paths (stub AC).
- [ ] Each listed breaking/deprecated item references a **release note fragment or inventory/stable deprecation entry**, not prose-only memory (stub AC spirit).
- [ ] Cross-links: `migrate-docs-namespace`, self-migrate, compatibility policy #1057 placeholder (“policy pending #1057”).
- [ ] Pin examples use current public pin from README at merge time (today **0.12.0**).

### Dependencies

| Dependency | Why |
|---|---|
| #1533 / quickstart | Shared pin verify vocabulary |
| #1538 / reference | “What changed” surface names |
| #1536 + #1541 | Stable/deprecated CLI & MCP lists |
| #1057 | Formal deprecation policy link (can ship guide with “pending” callout) |
| #649 | Self-migrate behavior truth |
| #1029 | Namespace migration command availability |

**Order:** Start draft after #1533 merge (pin table); finalize breaking-change section after #1536 + #1057 or ship with inventory-only citations.

### Open questions for Andrew (#1069)

1. Release-by-release breaking section vs single “0.x→1.0” narrative?  
   **Default:** Table keyed by **released** versions under `.agentic/releases/v*/` plus “upcoming” pointer to `release-minor` fragments.

2. Automate excerpt from release notes into upgrade guide?  
   **Default:** Manual curated guide for 1.0; optional later generator (out of scope).

3. Include `gh plate config upgrade --apply` for `.plate` schema?  
   **Default:** Yes — short subsection with link to migration docs.

4. Stub risk `risk:medium` — split “operator upgrade” vs “payload/template upgrade” into two pages?  
   **Default:** One `docs/upgrade-guide.md` with two top-level parts.

---

## Cross-cutting questions (Epic #1065)

1. Single README **User documentation** table owner — which PR merges last must reconcile links?  
   **Default:** Whoever merges last runs a tiny Documentation PR if needed; #1532 defines table shape.

2. Namespaced adopters: import-payload copies user docs to `docs/plate/` — does template_payload gain copies of the four files at 1.0?  
   **Default:** Yes in template payload follow-up; monorepo paths stay `docs/*.md`.

3. Epic #1065 success: “verified by third-party adopter proof” — is quickstart the literal script for #1070?  
   **Default:** Yes; upgrade guide is out-of-band for proof unless proof includes upgrade scenario.

4. Refinement closure: edit stub bodies on GitHub vs planning docs only?  
   **Default:** Human clears stub labels per `agents/stub-issues.md`; this file is planning input.

5. Troubleshooting placement in README table — link `docs/wiki/Troubleshooting.md` until #1063 expands content?  
   **Default:** Yes; #1065 Epic body already assigns ownership to #1063.

---

## Stub coverage summary

| Issue | This doc’s role |
|---|---|
| #1066 | Points to #1533; gaps (pins, #1070, adoption-guide drift) |
| #1067 | Points to #1532; README/table wiring |
| #1068 | Points to #1538; merge/CI/README gaps only |
| #1069 | Full refinement draft |

---

## References

- Epic [#1065](https://github.com/akasper/plate/issues/1065), Release [#654](https://github.com/akasper/plate/issues/654)  
- PR [#1532](https://github.com/akasper/plate/pull/1532) (#1067), [#1533](https://github.com/akasper/plate/pull/1533) (#1066), [#1536](https://github.com/akasper/plate/pull/1536), [#1538](https://github.com/akasper/plate/pull/1538) (#1068), [#1541](https://github.com/akasper/plate/pull/1541)  
- Troubleshooting owner [#1063](https://github.com/akasper/plate/issues/1063) — [`docs/wiki/Troubleshooting.md`](../wiki/Troubleshooting.md)  
- Style: [`refinement-drafts-1059-security-supportability.md`](refinement-drafts-1059-security-supportability.md) (PR [#1558](https://github.com/akasper/plate/pull/1558))  
- Migration depth: [`adoption-guide.md`](../migration/adoption-guide.md), [`namespace-docs-migration.md`](../migration/namespace-docs-migration.md)