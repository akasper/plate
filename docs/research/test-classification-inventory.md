---
title: Research: Test Classification & Feature-Proof Inventory for Test Coverage Audit (Epic #350)
issue: 361
epic: 350
status: in-progress
---

# Research: Test Classification & Feature-Proof Inventory (Epic #350)

**Issue:** #361 (Research child of Epic #350 "Test Coverage Audit")

**Conducted by:** Grok (autonomous progress on Epic #350)

**Date:** 2026-06-06 (initial skeleton) + follow-on deep pass

**Status:** In progress (deep inventory complete for core + e2e; classification taxonomy defined; gaps prioritized; initial convention draft; examples started in parallel with Design child #362)

## Summary / Answer to the Informational Goal

Tests are the single source of truth for implemented features and capabilities. This Research delivers:

- A **classification taxonomy**: feature-proof (directly proves a documented claim/surface), supporting (regression, migration, hygiene), infra (fakes, harness internals).
- **Full (deep-pass) inventory** of all tests/ (Python + Playwright e2e) cross-referenced to claims in Goals.md, SPEC.md (including beta roadmap), design docs (Acceptance Evidence focus), e2e/README, README, AGENTS.md, research docs, and source (mcp_server.py stubs, etc.).
- **Prioritized actionable gaps** for #364 (and follow-ups).
- **Draft convention** for "Acceptance Evidence" sections (per human direction on #350) + example applications (to be completed in #362).
- **Companion artifact** to the living audit report in `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md`.

The inventory confirms strong dogfooding (most Epic/Feature-named tests are feature-proof), but incomplete bidirectional links and several high-visibility gaps in the beta roadmap claims (planning engine, full contemplation contract, etc.).

See the sibling audit report for the summarized tables; this doc provides the detailed rationale, taxonomy, and research outputs.

## Classification Taxonomy

- **Feature-proof**: The test (or spec) directly exercises + asserts behavior or output that matches a documented, observable claim about a user/agent-facing capability, process rule, or surface. Examples: health reports goals_page_present + plate_config; e2e plugin-structure certifies no-vendor-terms + required MCP tools; contemplation test verifies citation-based close_signal_met per the design contract. These are the primary targets for "Proving tests:" citations.
- **Supporting**: Tests specific past bugs/regressions, deprecation/migration hygiene, cutover verification, or narrow internal guards that support but do not directly prove the high-level documented feature. E.g., current_md_stale_reference_audit, template cutover tests, some cost/delegation edge cases.
- **Infra**: Pure test infrastructure, GH client fakes/mocks, conftest, serialization helpers, or harness setup that enable other tests but are not claims themselves. E.g., GhClientResilienceTests (except when they prove documented resilience), many _FakeClient patterns.

Borderline cases (e.g., a test for a stub implementation) are called out with rationale; human Q&A may be used for final calls.

## Inventory Highlights (Deep Pass Additions)

Core Python (additions beyond skeleton broad pass; see audit report for full table):

- **test_contemplation.py** (ContemplationEngineTests): Feature-proof (partial). Covers close_signal requires citations + checklist verification, prose answer does not close, revision invalidates, blocking resumption posts comment with USAGE REPORT. Directly maps to docs/design/contemplation-engine-contract.md Acceptance Evidence and SPEC beta "Contemplation Engine v2". Gap: full non-destructive transcript + all forward-progress artifact types per the research enumeration doc.
- **test_curiosity_answers.py** (TestCuriosityAnswers): Feature-proof. parse/build/update/get/backfill for Answer Model (committed + GitHub). Maps to design/curiosity-answer-model.md, informational-goals-model, AGENTS QANDA.
- **test_features.py** (FeatureDetectionTests): Feature-proof. get_features flags (plugin, catalog, current-md, playwright, autonomous), detect_playwright heuristic. Maps to README "gh plate features", SPEC surfaces table, e2e harness claims.
- **test_mcp.py** (McpTests + many): Largely feature-proof for the MCP surface contract. Extensive dispatch tests for health, epic_status, agents/skills, features, bootstrap, config, plan_epic (stub), pr_babysit, curiosity tools, what_next, etc. + tool list expectations. Proves the documented tool surfaces in README/SPEC.
- **test_github_client.py**: Mostly infra + supporting (serialization, resilience #270, discussions). Some overlap with documented resilience in health/AGENTS.
- Others (baseline_catalog, costs, delegation, epic89_*, current_md_*, cut_release, template_payload*): Mix of feature-proof for their slice (catalog, .plate config per its design's Evidence citation, delegation) + supporting (migrations, cutovers).

E2E / Harness: See audit report (plugin-structure is the strongest feature-proof for CLI-agnostic + catalog claims; others support host flows and harness maintenance).

**tests/README.md**: Core process claim (evidence model: Unit/Integration/E2E/Regression/Manual + "link to the tests... that prove it"). Feature-proof for the philosophy; should be referenced from AGENTS and design conventions.

Full cross-refs and per-test notes are maintained in the living `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md` (expanded during this Research).

## Key Documented Claims (Sampled + Evidence Sections)

(Expanded from skeleton using design grep + source reads.)

- **Goals.md**: Test-First is Non-Negotiable; health/epic visibility; <15min adoption; 70-90% agent-driven; GitHub SSoT; durability of knowledge via answers/artifacts.
- **SPEC.md**: Surfaces table + exact MCP/CLI commands; test-first + verifiable progress via fragments; beta roadmap (explicit list including planning engine stub replacement, Contemplation v2, .plate config, release tooling, health expansion, E2E polish, observability/costs, catalog, etc.); target workflows.
- **Design docs Acceptance Evidence** (standardization target for #362):
  - Strong/citing tests: release-ceremony-refinement.md (lists test_release.py + test_cut_release + test_bootstrap + test_native... + bootstrap + fragments + AGENTS + tests pass), plate-root-config...md (explicitly `tests/test_epic89_plate_config.py`), markers.md, cutover.md, agent-skill-registry.md (load_baseline_catalog tests), baseline-agents-*.md, mcp-agent-skill..., single-agent-delegation, contemplation-engine-contract.md (criteria, references research), curiosity-answer-model.md, qanda-*.md (some E2E + tool expectations).
  - Weaker (criteria or "implemented when" without test citations): task-issue-type..., informational-goals-model.md, information-audit-contract.md, native-github-pr-integration.md, qanda-mcp-cli-surfaces.md, plugin-foundation..., plates-core-marker-contract..., plate-template-cutover-plan.md (some), design/README.md (wiki sync), others.
  - Opportunity realized in this Research + #362: Mandate "Proving tests: `tests/test_xxx.py:Class.method` (and e2e spec if applicable). See audit report for matrix." + update all high-signal ones.
- **e2e/README + harness**: Certifies "CLI-agnostic claims" (Epic #205 lineage); structure tests are host-independent simulation; update expectations when adding MCP/tools.
- **AGENTS.md + tests/README**: Full process rules (test-first, artifacts, PR process, babysit, stubs, labels, fragments, etc.) are claims that many tests (native PR integration, release, health, mcp dispatch, current_md audits, template cutover) prove/enforce.
- **Source claims**: mcp_server.py _plan_epic_stub + _what_next (v1 heuristics); contemplation contract in design; etc.

## Prioritized Gaps (Actionable for #364 + follow-ups)

1. **Interactive epic planning (high)**: _plan_epic_stub + test only prove the stub interface + schema (SPEC explicitly flags as to-be-replaced with full flow, child stubs, SESSION_STATE, Q&A integration). No test for the "guided interactive" behavior described in AGENTS and beta roadmap.
2. **Contemplation v2 full contract (high)**: Partial in test_contemplation.py + curiosity_answers. Missing full coverage per docs/design/contemplation-engine-contract.md + its research enumeration (transcript for all types, complete artifact creation, strict verified closure, integration with plan_epic state).
3. **Bidirectional links + Evidence convention (high, owned by #362 + this Research)**: Inconsistent application across ~20 design docs. Few tests explicitly declare the claim (via docstring or module comment).
4. **E2E compound flows (medium)**: Strong for structure/catalog; thin for full babysit (branch update strategies + resolve), release ceremony end-to-end, Q&A+contemplate loop producing artifacts.
5. **Template payload / adopter claims (medium)**: Mirrored harness + docs claim inheritance of capabilities; supporting cutover tests but no full matrix audit like the root one.
6. **Tooling / repeatability (medium-high, owned by #363)**: No `plate_*_audit` surface yet; manual today.
7. **Lower**: Some observability (costs), deeper CLI, migration guards, github_client resilience (where not explicitly claimed as feature).

See the audit report for the living prioritized list + mappings back to specific claims/tests.

## Draft Convention for Acceptance Evidence (for #362)

**Recommended format** (to be refined in Design #362 and applied):

```markdown
## Acceptance Evidence

- Design/research artifact committed and referenced from the Epic/parent.
- Proving tests: 
  - `tests/test_foo.py:TestBar.test_baz` (core contract + citation logic)
  - `tests/e2e/plugin-structure.spec.ts` (CLI-agnostic surface)
  - (See `docs/audits/test-coverage-audit-*.md` and Research #361 classification matrix for full bidirectional cross-refs.)
- Evidence in implementing PR(s) + fragment(s) under `.agentic/releases/unreleased/` (for process changes).
- All tests (unit + relevant e2e) + doc updates pass; manual dry-run of the described flow succeeds.
- Updated AGENTS.md / tests/README.md / agent guidance / catalog as required.
- No unresolved `need:*` on the parent (or explicitly accepted).
```

Update the design template (docs/design/README.md) and audit-report-template.md.

Example applications started in this pass (more in #362): contemplation-engine-contract.md, release-ceremony-refinement.md (already good), etc.

## Research Outputs & Traceability

- Primary: This `docs/research/test-classification-inventory.md` (per AGENTS.md for Research issues).
- Living summary + tables: `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md` (expanded).
- Progress posted to GitHub #361 (and parent #350).
- Will feed #362 (convention + doc updates), #364 (specific gap closures with tests + Evidence links), #363 (tooling that can consume/reproduce the classification).

This Research closes the "inventory + classification first" directive from the Epic planning session. No major blockers encountered yet (classifications are evidence-based with explicit rationale for partials/borderlines). Specific Q&A may be raised for edge cases or priority ordering in #364.

**Next autonomous step**: Apply initial convention examples to 2-3 docs (feeding #362), then move to implementing the tooling skeleton in #363 (grounded in the matrix) or specific small gap closures if low-risk. When human input needed on classification edge cases or gap priorities, interactive Q&A will be engaged per the qanda process (Question issue or direct here).

Closes #361 (upon PR with the artifacts + any convention examples).