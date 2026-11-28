# Refinement Drafts: New-Repo Standard Workflows (Epic #1008)

**Parent Epic:** [#1008](https://github.com/akasper/plate/issues/1008)  
**Milestone:** New-repo standard workflows  
**Product decisions (binding):** `docs/curiosity/refinement-qa-pack-1009-new-repo-standard-workflows.md` (Question #1009, Andrew 2026-10-03)  
**Refinement proposals (canonical):** plate-lifecycle comments on stub issues #1031–#1038 (~2026-11-28 15:28Z). **This file indexes those comments and records only gaps not already settled there.**  
**Status:** Docs-only companion to PR review; does not clear `status:stub` / `need:refinement`.

---

## Source of truth

| Issue | plate-lifecycle refinement comment |
|------:|-----------------------------------|
| #1031 | https://github.com/akasper/plate/issues/1031#issuecomment-7241496447 |
| #1032 | https://github.com/akasper/plate/issues/1032#issuecomment-7241496863 |
| #1033 | https://github.com/akasper/plate/issues/1033#issuecomment-7241497213 |
| #1034 | https://github.com/akasper/plate/issues/1034#issuecomment-7241497571 |
| #1035 | https://github.com/akasper/plate/issues/1035#issuecomment-7241497879 |
| #1036 | https://github.com/akasper/plate/issues/1036#issuecomment-7241498166 |
| #1037 | https://github.com/akasper/plate/issues/1037#issuecomment-7241498506 |
| #1038 | https://github.com/akasper/plate/issues/1038#issuecomment-7241498838 |

Implementers and `mark_ready` should treat each linked comment as the authoritative scope, acceptance criteria, likely files, dependencies, and risks. The #1009 pack remains binding for product intent Andrew already answered; do not reopen those themes.

---

## Recommended land order

From the same plate-lifecycle comments (repeated on every issue):

1. **#1038** — bootstrap / discovery composition (operator story first)  
2. **#1031** and **#1034** in parallel (research)  
3. **#1032** and **#1035** (design)  
4. **#1033** and **#1036** (features)  
5. **#1037** last — after open [PR #1528](https://github.com/akasper/plate/pull/1528) merges ([mandatory adoption health / `adoption_complete`](https://github.com/akasper/plate/pull/1528))

External prerequisites: #633 bootstrap, #1015 `docs/plate/` namespacing, #1017 shell-first scripts.

---

## Q10 artifacts split (Epic scope)

Andrew's Q10 checklist spans CI and philosophy tracks. **Ownership:**

| Artifact | Owner | Notes |
|----------|--------|--------|
| Test inventory (`docs/plate/ci-cd/test-inventory.md`) | #1032 design → #1033 impl | Strict test-first layers per #1031 |
| CI/CD component manifest | **#1032** (path/format) → #1033 writes | Not `.plate` schema change in this Epic |
| Stub issues for unautomated tests | **#1032** templates → #1033 creates | `docs/agents/stub-issues.md`, `src/plate_core/planning.py` patterns |
| Human **Task** issues (secrets, publish, external setup) | **#1032** → #1033 | |
| Team/philosophy summary (`docs/plate/team.md`, optional `AGENTS.md` section) | #1034–#1036 | **Not** owned by #1032 / #1033 |

Full CI workflow files remain **out of scope** for discovery (Q10).

---

## Cross-cutting constraints (#1009 + comments)

- Phase 1: `gh plate bootstrap` / import-payload + bootstrap (`src/plate_core/bootstrap.py`, #633). Phase 2: `gh plate setup-ci`, `gh plate encode-team`, health nudges (#1038).
- Strict test-first, comprehensive probe, HITL opt-in only, GitHub-first + Playwright-where-possible, uncommon-stack research path (Roblox example).
- Philosophy: solopreneur default; human count + methodology questions; per-repo experience; repo-owner authority; no role/`CODEOWNERS`/team-size gate adaptation at launch.
- No `.plate` schema change as part of Epic refinement (implementation Features may propose later).

---

## Per-issue index (see linked comment for full text)

### [#1031](https://github.com/akasper/plate/issues/1031) — Research: CI/CD test layer taxonomy

**Comment:** https://github.com/akasper/plate/issues/1031#issuecomment-7241496447  
**Artifact:** `docs/plate/research/ci-cd-test-taxonomy.md` (+ payload mirror under `src/plate_core/template_payload/docs/plate/research/`).

**Additional open questions (not in comment):** _(none — use maintainer questions in the comment only.)_

---

### [#1032](https://github.com/akasper/plate/issues/1032) — Design: CI/CD discovery interview flow

**Comment:** https://github.com/akasper/plate/issues/1032#issuecomment-7241496863  
**Artifact:** `docs/plate/design/ci-cd-discovery-flow.md`

**Owns the four CI-side Q10 artifacts:** test inventory template, component manifest location/format, stub-issue pattern, human Task pattern; team/philosophy summary explicitly belongs to philosophy track (#1034–#1036).

**Maintainer open questions (from comment):** manifest path (`.plate` extension vs separate file); dry-run vs `--apply` for GitHub issue creation (Tasks/stubs).

---

### [#1033](https://github.com/akasper/plate/issues/1033) — Feature: CI/CD discovery workflow

**Comment:** https://github.com/akasper/plate/issues/1033#issuecomment-7241497213

**Implementation notes (from comment, align with open PRs):**

- `gh plate setup-ci` — **not** `gh plate ci audit`; new module e.g. `src/plate_core/ci_cd_discovery.py`.
- MCP **`plate_discover_ci_cd`**: register via **`MCP_TOOL_HANDLERS`** in `src/plate_core/mcp_server.py` plus `src/plate_core/mcp/tool_definitions.py` and `src/plate_core/mcp/tool_profiles.py` **after** [PR #1544](https://github.com/akasper/plate/pull/1544) lands — not the legacy `elif` dispatch chain.
- Any new public CLI/MCP surface must also update: [PR #1536](https://github.com/akasper/plate/pull/1536) public-surface inventory (`docs/plate/research/public-surface-inventory.md`), [PR #1538](https://github.com/akasper/plate/pull/1538) generated `docs/cli-mcp-reference.md`, and the [PR #1541](https://github.com/akasper/plate/pull/1541) snapshot `tests/fixtures/public_surface_stable.json` (and related generator checks when those PRs land).

**Maintainer open questions (from comment):** final manifest location; idempotent re-run merge vs replace; MCP tool naming vs `plate_discover_ci_cd`.

---

### [#1034](https://github.com/akasper/plate/issues/1034) — Research: Development ecosystem questionnaire

**Comment:** https://github.com/akasper/plate/issues/1034#issuecomment-7241497571  
**Artifact:** `docs/plate/research/dev-philosophy-questionnaire.md`

**Maintainer open questions (from comment):** experience as single repo-level knob vs per-persona; methodology free text vs enumerated list.

---

### [#1035](https://github.com/akasper/plate/issues/1035) — Design: Philosophy encoding model

**Comment:** https://github.com/akasper/plate/issues/1035#issuecomment-7241497879  
**Artifact:** `docs/plate/design/philosophy-encoding-model.md`

**Maintainer open questions (from comment):** machine-readable experience (e.g. YAML front matter in `team.md`); which adaptation dimensions ship in v1 vs documented-only placeholders.

---

### [#1036](https://github.com/akasper/plate/issues/1036) — Feature: Philosophy encoding workflow

**Comment:** https://github.com/akasper/plate/issues/1036#issuecomment-7241498166

**Implementation notes (from comment, align with open PRs):**

- `gh plate encode-team` and MCP **`plate_encode_team_philosophy`**; module e.g. `src/plate_core/team_philosophy.py`.
- Same MCP registration path as #1033: **`MCP_TOOL_HANDLERS`**, `tool_definitions`, `tool_profiles` after **#1544**; update public-surface inventory, CLI/MCP reference, and **`tests/fixtures/public_surface_stable.json`** per **#1536** / **#1538** / **#1541** (the snapshot is #1541's).

**Maintainer open questions (from comment):** idempotent merge for `AGENTS.md` philosophy section; `encode-team` vs `encode-philosophy` naming.

---

### [#1037](https://github.com/akasper/plate/issues/1037) — Feature: Health nudges

**Comment:** https://github.com/akasper/plate/issues/1037#issuecomment-7241498506

**Implementation notes (from comment + [PR #1528](https://github.com/akasper/plate/pull/1528)):**

- **Land after #1528.** Extend `get_health()` / `HealthReport` in `src/plate_core/health.py` and tests in `tests/test_health.py` without regressing **`adoption_complete`**, **`adoption_complete_gaps`**, **`adoption_complete_fix_command`**, **`adoption_next_command`**, **`release_standing_health`**, **`branch_protection_pr_reviews_required`**, or `_health_exit_code()` behavior (in `src/plate_core/cli.py`) from #1528.
- JSON shape: use `HealthReport.to_dict()` / `asdict` fields (same pattern as adoption verdicts). Prefer dedicated optional boolean or gap-list fields **or** append human-readable entries to existing **`plate_repo_signals`** — do not introduce a parallel ad hoc JSON schema.
- Warn when missing `docs/plate/ci-cd/test-inventory.md` and `docs/plate/team.md`; message names `gh plate setup-ci` and `gh plate encode-team`. Optional tie-in: `src/plate_core/what_next.py`.
- Warn-only for mature repos; coordinate with comment on suppression when `adoption_core_ready` / adoption incomplete.

**Maintainer open questions (from comment):** warn vs advisory vs skip when adoption not complete; suppression without `.plate` changes (defer or env).

---

### [#1038](https://github.com/akasper/plate/issues/1038) — Design: Bootstrap and discovery composition

**Comment:** https://github.com/akasper/plate/issues/1038#issuecomment-7241498838  
**Artifact:** `docs/plate/design/bootstrap-discovery-composition.md`

**Doc touch list (from comment):** `docs/bootstrap/starting-a-new-repository.md`, `docs/bootstrap/new-repository-checklist.md`, payload mirrors under `src/plate_core/template_payload/docs/bootstrap/`; reference `src/plate_core/adoption.py`, `what_next.py`.

**Maintainer open questions (from comment):** `what_next` rank `setup-ci` vs `encode-team`; whether both phase-2 workflows are required for “adoption complete” or optional enhancements (distinct from **`adoption_complete`** in #1528 — clarify in design doc).

---

## Epic-level open questions (Andrew / maintainer)

Consolidated **only** from plate-lifecycle comment “Open questions for the maintainer” sections (no duplicate recommended defaults that conflict with issue text):

| Area | Questions |
|------|-----------|
| #1031 | Acceptance tests vs deployed/staging target; minimum inventory columns |
| #1032 | Manifest path/format; dry-run vs apply for issue creation |
| #1033 | Manifest location; idempotency; MCP tool naming |
| #1034 | Experience knob shape; methodology enum vs free text |
| #1035 | Machine-readable experience; v1 adaptation dimensions |
| #1036 | AGENTS.md merge strategy; command naming |
| #1037 | Warn severity; suppression without `.plate` |
| #1038 | `what_next` ordering; required vs optional phase 2 vs #1528 `adoption_complete` |

---

## References

- Q&A pack: `docs/curiosity/refinement-qa-pack-1009-new-repo-standard-workflows.md`  
- Bootstrap: #633, `docs/bootstrap/starting-a-new-repository.md`, `src/plate_core/bootstrap.py`  
- Health (pre–#1037): `src/plate_core/health.py`, `plate_health`; adoption JSON fields: PR #1528  
- Public surfaces: PRs #1536, #1538; MCP handler map: PR #1544  
- Stub process: `docs/agents/stub-issues.md`, AGENTS.md  