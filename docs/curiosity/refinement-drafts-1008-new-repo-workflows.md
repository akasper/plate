# Refinement Drafts: New-Repo Standard Workflows (Epic #1008)

**Parent Epic:** [#1008](https://github.com/akasper/plate/issues/1008) — New-repo standard workflows  
**Milestone:** New-repo standard workflows  
**Binding decisions:** `docs/curiosity/refinement-qa-pack-1009-new-repo-standard-workflows.md` (Question #1009, Andrew 2026-10-03)  
**Prepared for:** Andrew — refine stub children #1031–#1038 before `mark_ready`  
**Status:** Draft for review (docs-only); does not clear `status:stub` / `need:refinement` on issues  

---

## How to use this document

Andrew's answers in the #1009 pack are **binding**. This file proposes implementation-ready scope, acceptance criteria, and ordering for each stub child. It does not reopen settled Q&A. Open questions appear only where the pack leaves a real gap (artifact paths, schema detail, or sequencing nuance).

PLATE docs for this Epic land under **`docs/plate/`** per #1015. Today the plate repo still carries bootstrap guidance at `docs/bootstrap/` (for example `docs/bootstrap/starting-a-new-repository.md` and `docs/bootstrap/new-repository-checklist.md`); greenfield bootstrap is invoked via **`gh plate bootstrap`** in `src/plate_core/bootstrap.py` and `src/plate_core/cli.py` (#633). Phase-2 commands **`gh plate setup-ci`** and **`gh plate encode-team`** do not exist yet; health today is **`gh plate health`** / MCP **`plate_health`** in `src/plate_core/health.py`.

---

## Epic dependency graph (recommended land order)

```text
Phase 0 (external): #633 bootstrap, #1015 docs/plate namespacing, #1017 shell-first scripts

Parallel research (no cross-deps):
  #1031 (CI/CD taxonomy)          #1034 (philosophy questionnaire)

Design wave (depends on research):
  #1032 ← #1031                   #1035 ← #1034
  #1038 ← #633 docs + #1009 compose answer (can draft in parallel with #1032/#1035)

Features (depend on design + composition):
  #1033 ← #1031, #1032
  #1036 ← #1034, #1035
  #1037 ← #1033, #1036, #1038 (needs stable artifact paths from design)
```

| Order | Issue | Type | Blocks |
|------:|-------|------|--------|
| 1a | #1031 | Research | #1032, #1033 |
| 1b | #1034 | Research | #1035, #1036 |
| 2a | #1032 | Design | #1033 |
| 2b | #1035 | Design | #1036 |
| 2c | #1038 | Design | #1037, bootstrap doc updates |
| 3a | #1033 | Feature | #1037 |
| 3b | #1036 | Feature | #1037 |
| 4 | #1037 | Feature | — |

---

## Cross-cutting launch constraints (all children)

These follow from Epic #1008 and the #1009 pack; children must not contradict them.

- **Compose with bootstrap (#633):** standing structure first; CI/CD and philosophy discovery are phase 2, health-nudged—not a mega-bootstrap session.
- **Strict test-first:** discovery inventories assume agents create test stubs before implementation; CI is expected to fail when tests are missing (enforcement wiring may be later Features, but discovery language must say so).
- **Artifacts (Q10):** test inventory, CI/CD component manifest, team/philosophy summary, human Tasks for external setup, stub issues for unautomated tests. **Not** full GitHub Actions workflow files.
- **HITL:** optional opt-in only; comprehensive probe still **names** operator surfaces even when not automated.
- **Philosophy:** solopreneur default; always ask human count + methodology; record headcount but **do not** adapt gates, Q&A authority, or Epic planning scope; per-repo experience encoding; Q&A authority = repo owner; no role/`CODEOWNERS` encoding at launch.
- **`.plate`:** this Epic's refinement does not change `.plate` schema; implementation may propose extensions in their own PRs (#1035 explicitly defers schema).

---

## #1031 — Research: CI/CD test layer taxonomy and verification surface model

**Issue:** [#1031](https://github.com/akasper/plate/issues/1031)  
**Artifact:** `docs/plate/research/ci-cd-test-taxonomy.md`

### Proposed scope

- Define **unit**, **integration**, and **acceptance** layers under strict test-first, with PLATE-aligned examples (issue-linked Features, regression tests, Playwright where UI exists).
- Publish a **comprehensive probe checklist** of verification surfaces: web/API, desktop, game platforms (Roblox as reference uncommon stack), marketplace publish, hardware-adjacent flows, operator touchpoints—each mapped to inventory fields even when automation is deferred.
- Specify how **HITL** appears in the taxonomy: documented optional path, not a required fourth layer; contrast with automated layers.
- Tie inventory consequences to **test stub** expectations and CI posture (reference existing plate test layout under `tests/` and template e2e notes in `src/plate_core/template_payload/tests/e2e/README.md` without mandating a single stack).

### Non-goals

- Interview flow or CLI/MCP design (#1032, #1033).
- Generating workflow YAML or choosing specific GitHub Actions job graphs.
- First-class always-on HITL discovery (vision / later).

### Draft acceptance criteria

- [ ] `docs/plate/research/ci-cd-test-taxonomy.md` exists and is linked from the research index pattern used by other `docs/plate/research/` pages (create parent README if missing when #1015 lands).
- [ ] Each of unit, integration, and acceptance has a definition, typical tooling (GitHub-first, Playwright-for-UI, pytest-for-Python per #1009 Q3), and at least two concrete examples (one common web stack, one non-obvious surface).
- [ ] Comprehensive probe section lists non-obvious surfaces with **inventory field names** agents will fill in #1033.
- [ ] HITL is explicitly **opt-in**; doc states what is *not* scaffolded by default.
- [ ] Strict test-first section states agent obligation (stubs before implementation) and expected CI failure mode in principle terms.

### Dependencies

- **Upstream:** #1015 path convention (`docs/plate/`).
- **Downstream:** #1032, #1033.

### Open questions for Andrew

1. **Inventory schema depth:** Should the taxonomy doc prescribe a fixed markdown section outline for `test-inventory.md`, or only semantic layer definitions and let #1032 own the template?  
   **Recommended default:** #1031 defines semantics + probe checklist; #1032 owns the `test-inventory.md` section template (#1032 already lists artifact templates).

2. **Acceptance vs E2E naming:** Should the third layer be labeled strictly `acceptance` (Epic language) or allow alias `e2e` in adopters' repos?  
   **Recommended default:** Canonical label `acceptance`; allow optional `e2e` subheading in inventory for teams that use that term.

---

## #1032 — Design: CI/CD discovery interview flow

**Issue:** [#1032](https://github.com/akasper/plate/issues/1032)  
**Artifact:** `docs/plate/design/ci-cd-discovery-flow.md`

### Proposed scope

- Agent-guided **interview order**: repo signals (languages in tree, existing `.github/workflows/`, product type hints) → comprehensive probe → stack branch (common defaults vs uncommon research path) → component naming → optional HITL opt-in → artifact emission plan.
- **Decision points** for common stacks: GitHub Actions, Playwright when browser/UI exists, pytest for Python, shell scripts per #1017 unless Windows declared in `.plate` `platform` (read-only reference to `src/plate_core/plate_config.py` platform key—no schema change).
- **Uncommon-stack branch:** research-based propose (Roblox example): agent documents findings in inventory, may open Research issues—no blessed default forced.
- **Outputs mapping:** `docs/plate/ci-cd/test-inventory.md`, component manifest location (per resolved Q below), stub issues for unautomated tests, human **Task** issues for secrets/accounts/publish—**no** workflow file generation.
- Separate **always-on probe** from **opt-in HITL** questions (per Q2 answer C).

### Non-goals

- Implementing `gh plate setup-ci` or MCP (#1033).
- Philosophy encoding (#1034–#1036).
- Team-size or role adaptation.

### Draft acceptance criteria

- [ ] `docs/plate/design/ci-cd-discovery-flow.md` includes a flow diagram or numbered stages with entry/exit criteria.
- [ ] Common-stack default table lists GitHub-first components and override rules when the repo already has conflicting CI.
- [ ] Uncommon-stack branch specifies minimum research outputs (what the agent must cite before proposing tooling).
- [ ] HITL path is a distinct optional stage; doc lists Task issue templates/titles for human verification.
- [ ] Artifact template section names files under `docs/plate/ci-cd/` and manifest rules; explicitly excludes `.github/workflows/*.yml` generation.
- [ ] Cross-reference #1031 taxonomy field names for inventory consistency.

### Dependencies

- **Upstream:** #1031.
- **Downstream:** #1033, #1038 (user journey copy).

### Open questions for Andrew

1. **Component manifest location:** Q10 checked "`.plate` extension or separate." Where should discovery write the manifest at launch?  
   **Recommended default:** `docs/plate/ci-cd/component-manifest.json` (human-diffable, no `.plate` schema change in this Epic); optional later sync to `.plate` extension in a follow-up Feature.

2. **Pre-existing product CI:** When `gh plate bootstrap --adopt` repos already have workflows, should discovery **merge** into inventory only, or also emit a `need:human-review` Task to reconcile PLATE gates with product CI?  
   **Recommended default:** Inventory + Task for reconcile; do not mutate existing workflow files in #1033.

3. **Stub issue typing:** Should unautomated test stubs be `Feature` stubs with `area:tests`, or a dedicated label pattern?  
   **Recommended default:** `Feature` + `status:stub` + `area:tests`, title prefix `Test: …`, matching PLATE stub process in AGENTS.md.

---

## #1033 — Feature: CI/CD discovery workflow for new repositories

**Issue:** [#1033](https://github.com/akasper/plate/issues/1033)  
**Surfaces (working names):** `gh plate setup-ci` (CLI subcommand in `src/plate_core/cli.py`), MCP **`plate_discover_ci_cd`** (register beside `plate_health` in `src/plate_core/mcp_server.py`)

### Proposed scope

- Interactive workflow implementing #1032 design: TUI/Q&A consistent with PLATE native forms (per AGENTS.md Question guidance).
- Write **`docs/plate/ci-cd/test-inventory.md`** and component manifest per design.
- Enforce **strict test-first** language in generated inventory (and tests that generated content includes required layers).
- Implement common defaults + uncommon research path with automated tests under `tests/` (mirror patterns from `tests/test_bootstrap.py`, `tests/test_health.py`).
- On opt-in HITL: create GitHub **Task** issues via `gh` API (pattern existing issue/PR automation in plate_core).
- Open **stub issues** for unautomated tests (Playwright, etc.) with PLATE label set.
- **Do not** write or modify `.github/workflows/*`.

### Non-goals

- `gh plate encode-team` / philosophy (#1036).
- Full CI workflow implementation Features.
- Role encoding, team-size gates, first-class HITL.

### Draft acceptance criteria

- [ ] CLI: `gh plate setup-ci` exists, documented in help; dry-run mode lists planned artifacts without writing (parity with `gh plate bootstrap` dry-run pattern).
- [ ] MCP: `plate_discover_ci_cd` returns structured result (paths written, issues created, errors).
- [ ] Integration tests cover: Python repo path → pytest default; UI flag → Playwright named; opt-in HITL → Task created, no Task when declined; uncommon path → research notes section present.
- [ ] Written files live only under `docs/plate/ci-cd/` plus GitHub issues; no workflow YAML in diff.
- [ ] Release fragment in `.agentic/releases/unreleased/` per Feature PR rules.
- [ ] Per-feature change documents verification commands in fragment summary.

### Dependencies

- **Upstream:** #1031, #1032; bootstrap complete (#633) in adopting repo.
- **Downstream:** #1037 (health checks for missing `test-inventory.md`).

### Open questions for Andrew

1. **Idempotency:** Re-running `setup-ci` should merge, overwrite, or refuse when inventory exists?  
   **Recommended default:** Prompt: update in place with backup section in inventory titled `Previous run`; tests cover second run.

2. **MCP vs CLI parity:** Must MCP run the full interview, or may it accept a pre-filled JSON spec for agents?  
   **Recommended default:** Full parity for v1; optional `answers_json` escape hatch documented as unstable.

---

## #1034 — Research: Development ecosystem questionnaire

**Issue:** [#1034](https://github.com/akasper/plate/issues/1034)  
**Artifact:** `docs/plate/research/dev-philosophy-questionnaire.md`

### Proposed scope

- Specify **default questions**: (1) how many humans on the project, (2) development methodology (or none)—single bundled decision per Q5/Q8 answers.
- **Solopreneur default** when skipped or empty; document literal default text recorded in summary.
- **Per-repo experience** question set (levels and wording) for #1035 to map to verbosity, auto-stub risk, review expectations.
- State **launch authority rule:** repo owner answers product Q&A; no role matrix.
- Explicit **non-adaptive** rules: headcount recorded only; no gate/authority/planning retuning.

### Non-goals

- Storage layout and AGENTS.md patch rules (#1035).
- CLI/MCP implementation (#1036).
- Team-size adaptive behavior or role encoding (vision / later).

### Draft acceptance criteria

- [ ] `docs/plate/research/dev-philosophy-questionnaire.md` lists every question with rationale, default, and valid answer shapes.
- [ ] Methodology question covers Scrum/Kanban/Shape Up/unstructured/none without mandating one methodology.
- [ ] Experience question aligned with Andrew's per-repo encoding answer (Q6).
- [ ] Doc section "Recorded but not acted on" covers headcount and methodology vs experience adaptations.
- [ ] Repo-owner authority called out; links to Epic vision / later for role encoding.

### Dependencies

- **Upstream:** #1009 pack Theme B.
- **Downstream:** #1035, #1036.

### Open questions for Andrew

1. **Experience scale:** Fixed enum (`junior` | `mid` | `senior` | `founding`) or free text?  
   **Recommended default:** Enum of four values plus optional free-text note field in summary only.

2. **Skipped questions:** If human count is skipped, record `1 (assumed solopreneur)` or leave field absent?  
   **Recommended default:** Record explicit `1 (default assumption per #1009)`.

---

## #1035 — Design: Philosophy encoding targets and experience adaptation

**Issue:** [#1035](https://github.com/akasper/plate/issues/1035)  
**Artifact:** `docs/plate/design/philosophy-encoding-model.md`

### Proposed scope

- **Storage targets:** `docs/plate/team.md` and/or `AGENTS.md` section—field mapping from #1034 answers.
- **Experience adaptations:** concrete, testable deltas (Q&A verbosity tiers, auto-stub generation risk flags, review expectation bullets) keyed off experience enum; no change to merge policy or label-check workflows.
- Document that **headcount and methodology** are informational in summary and agent prompts, not inputs to `plate_health` gate logic at launch.
- **No** `CODEOWNERS` role map, no `.plate` team-size schema in this design.

### Non-goals

- Implementing encode workflow (#1036).
- CI/CD artifacts (#1033).
- Post-launch role encoding.

### Draft acceptance criteria

- [ ] Design doc names primary file (`docs/plate/team.md` recommended) and optional `AGENTS.md` excerpt pattern (heading + block quote) without requiring `.plate` edits.
- [ ] Table maps each #1034 answer to storage location and consumer (agent prompt, health display-only, etc.).
- [ ] Experience adaptation matrix has at least three behavioral dimensions × four experience levels with neutral "senior" baseline.
- [ ] Explicit "does not change" list: branch protection, Q&A authority, Epic milestone rules, autonomous mode eligibility.
- [ ] Role encoding and team-size adaptation listed under out-of-scope / vision.

### Dependencies

- **Upstream:** #1034.
- **Downstream:** #1036, #1037.

### Open questions for Andrew

1. **AGENTS.md vs team.md split:** Q10 allows both. Should philosophy live primarily in `docs/plate/team.md` with a short pointer section in `AGENTS.md`?  
   **Recommended default:** Canonical `docs/plate/team.md`; `AGENTS.md` gets a "## Team context" stub linking to that file (pointer only, no duplication of fields).

2. **Experience adaptations enforcement:** Should adaptations be **documentation-only** in v1, or should `encode-team` patch agent-facing files (e.g. `.agentic/skills.yml` snippets)?  
   **Recommended default:** v1 writes `team.md` + optional single bounded subsection in `AGENTS.md`; defer skills.yml mutation to a follow-up if needed.

---

## #1036 — Feature: Development philosophy encoding workflow

**Issue:** [#1036](https://github.com/akasper/plate/issues/1036)  
**Surfaces:** `gh plate encode-team`, MCP **`plate_encode_team_philosophy`**

### Proposed scope

- Implement #1035: ask default + experience questions; write **`docs/plate/team.md`** (and pointer in `AGENTS.md` if design specifies).
- Apply experience adaptations as designed (prompt text or bounded AGENTS section).
- **Do not** alter review gates, Q&A routing, or Epic planning from headcount.
- **Do not** create `CODEOWNERS` or role maps.
- Tests prove headcount recorded unchanged when gates queried via existing health/autonomy paths.

### Non-goals

- `setup-ci` (#1033).
- Role/team-size vision features.

### Draft acceptance criteria

- [ ] CLI `gh plate encode-team` and MCP tool registered with schema in `mcp_server.py`.
- [ ] Writes `docs/plate/team.md` with human count, methodology, experience, authority statement (repo owner).
- [ ] Tests: skipping questions applies solopreneur default; experience tier changes adaptation text; headcount does not change outputs of unrelated gate functions (snapshot or mock tests).
- [ ] No `CODEOWNERS` or `.plate` schema changes in PR.
- [ ] Release fragment under `.agentic/releases/unreleased/`.

### Dependencies

- **Upstream:** #1034, #1035.
- **Downstream:** #1037.

### Open questions for Andrew

1. **Order relative to setup-ci:** May phase-2 commands run in either order, or should health nudge CI first?  
   **Recommended default:** Independent; health warns on each missing artifact separately (#1037).

---

## #1037 — Feature: Health nudges for CI and philosophy discovery

**Issue:** [#1037](https://github.com/akasper/plate/issues/1037)  
**Touchpoints:** `src/plate_core/health.py`, `get_health()` report shape, CLI `gh plate health`, MCP `plate_health`

### Proposed scope

- Extend health report with **warnings** (not hard errors) when:
  - `docs/plate/ci-cd/test-inventory.md` is missing in the default branch checkout (or remote via API if health already probes remote for Goals—follow `_remote_goals_page_present` patterns in `health.py`).
  - `docs/plate/team.md` (or design-selected summary path) is missing.
- Warning text names **`gh plate setup-ci`** and **`gh plate encode-team`** explicitly.
- Nudges apply post-bootstrap only: suppress or soften when bootstrap adoption incomplete (reuse existing bootstrap readiness signals if present in health report).
- Compose with #633: nudges do **not** re-run bootstrap.

### Non-goals

- Implementing discovery interviews (#1033, #1036).
- Failing plate-pr-gates or blocking merges on missing inventory.

### Draft acceptance criteria

- [ ] `tests/test_health.py` covers missing inventory, missing team summary, both present (no new warnings).
- [ ] JSON/text health output includes stable machine keys (e.g. `ci_discovery_pending`, `philosophy_encoding_pending`) documented in health help or schema.
- [ ] Warning messages include exact CLI commands; MCP `plate_health` returns same fields.
- [ ] No bootstrap re-invocation side effects.
- [ ] Release fragment for Feature PR.

### Dependencies

- **Upstream:** #1038 (artifact paths), #1033 and #1036 (commands must exist—or health gates feature-flagged until they land).
- **Downstream:** none.

### Open questions for Andrew

1. **Remote vs local check:** Should health inspect **local working tree** only, or default-branch GitHub contents (like Goals page)?  
   **Recommended default:** Prefer local files when `repo_root` set; optional remote check when running in agent context without checkout (match Goals dual behavior in #1022).

2. **Severity:** Warnings vs informational `suggestions` array?  
   **Recommended default:** Warnings in existing `errors`/`warnings` taxonomy health already exposes—verify field name in `HealthReport` dataclass before implement.

---

## #1038 — Design: Bootstrap and discovery composition

**Issue:** [#1038](https://github.com/akasper/plate/issues/1038)  
**Artifact:** `docs/plate/design/bootstrap-discovery-composition.md`

### Proposed scope

- Document **phase 1 / phase 2** journey aligned with #1009 Q9 answer A:
  - Phase 1: `gh plate bootstrap` / `import-payload` + bootstrap (#633)—references `docs/bootstrap/starting-a-new-repository.md`, `docs/bootstrap/new-repository-checklist.md`, and `src/plate_core/bootstrap.py` report actions.
  - Phase 2: health-nudged `gh plate setup-ci` and `gh plate encode-team`.
- List **bootstrap doc updates** (which files gain "after bootstrap, run …" without folding interviews into bootstrap).
- State explicit **non-merge** rule: discovery questions are not asked inside `run_bootstrap()` session.
- Adopter vs greenfield nuances (`--greenfield` vs `--adopt`).

### Non-goals

- Changing bootstrap implementation in #1038 PR (design doc only for this issue type).
- Implementing health or CLI (#1037, #1033, #1036).

### Draft acceptance criteria

- [ ] `docs/plate/design/bootstrap-discovery-composition.md` describes sequences with timing (immediate post-bootstrap vs later).
- [ ] Enumerates doc files to update when implementing composition (minimum: `docs/bootstrap/starting-a-new-repository.md`, `docs/bootstrap/new-repository-checklist.md`; post-#1015 mirrors under `docs/plate/bootstrap/` if migrated).
- [ ] States health as the nudge mechanism (#1037) without duplicating full health spec.
- [ ] Failure/dry-run behaviors reference bootstrap dry-run vs setup-ci dry-run.
- [ ] Cross-links Epic #1008 success criteria checklist.

### Dependencies

- **Upstream:** #633 behavior, #1009 compose answer.
- **Downstream:** #1037, technical writing tasks in bootstrap PRs.

### Open questions for Andrew

1. **Checklist placement:** Should phase-2 commands appear on `docs/bootstrap/new-repository-checklist.md` as required steps or optional "when ready" steps?  
   **Recommended default:** Optional but recommended post-bootstrap steps with health reminder—not blocking merge to `release` integration branch.

2. **Greenfield seed issues:** Should bootstrap continue to seed Epic stubs only, leaving discovery entirely manual via health?  
   **Recommended default:** Yes—no new seeded issues for setup-ci in bootstrap (#633 scope frozen).

---

## Epic #1008 — consolidated open questions (Andrew)

| # | Topic | Recommended default |
|---|--------|---------------------|
| 1 | Component manifest path | `docs/plate/ci-cd/component-manifest.json` |
| 2 | Re-run `setup-ci` behavior | Update in place with documented previous run |
| 3 | `acceptance` vs `e2e` labeling | Canonical `acceptance`; optional `e2e` subheading |
| 4 | Experience enum | junior / mid / senior / founding + optional note |
| 5 | Skipped human count | Record `1 (default assumption)` |
| 6 | team.md vs AGENTS.md | Canonical `team.md`; pointer section in AGENTS.md |
| 7 | Experience v1 enforcement surface | `team.md` + bounded AGENTS section only |
| 8 | setup-ci vs encode-team order | Independent; separate health warnings |
| 9 | Health file probe scope | Local first; remote parity like Goals (#1022) |
| 10 | Checklist optional vs required | Optional recommended steps after bootstrap |
| 11 | Pre-existing CI adoption | Inventory + human Task; no workflow edits |
| 12 | Unautomated test stub labels | Feature + status:stub + area:tests |

---

## References

- Epic #1008: https://github.com/akasper/plate/issues/1008  
- Question #1009 / pack: `docs/curiosity/refinement-qa-pack-1009-new-repo-standard-workflows.md`  
- Bootstrap: #633, `src/plate_core/bootstrap.py`, `docs/bootstrap/starting-a-new-repository.md`  
- Health: `src/plate_core/health.py`, MCP `plate_health`  
- Docs namespace: #1015, `src/plate_core/process_docs.py`  
- Shell default: #1017  
- Stub process: AGENTS.md (Research / Design / Feature work loops)  