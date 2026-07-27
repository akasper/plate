# PLATE Audit Report: Test Coverage Inventory & Classification (Epic #350)

| Field | Value |
|---|---|
| Audit Date | 2026-06-06 |
| Auditor | Grok (planning session continuation for Epic #350) |
| Scope | Broad inventory + classification of all tests under `tests/` (Python core + e2e Playwright harness). Cross-reference to documented claims in `docs/wiki/Goals.md`, `SPEC.md`, design docs (esp. "Acceptance Evidence" sections per direction), e2e/README, README, AGENTS.md, and related research. Initial gap identification. |
| Commit / Release | Current on `release` branch (post #351 stub definition); aligns with active Information Audit (#218) and beta roadmap in SPEC. |
| Related | Epic #350 (Test Coverage Audit), sibling #349 (Human Action Items), Feature #351 (Stubs), Epic #218 (Information Audits), release-ceremony-refinement design, various Epic/Feature-named tests. |

## Summary

Tests are the single source of truth for implemented features and capabilities (per human input on #350). PLATE already has a strong base of traceable, named tests (many explicitly tied to Epics/Features) and an e2e harness that certifies high-level claims (CLI-agnostic plugin structure, catalog discovery). The `tests/README.md` codifies the desired evidence model: "every implemented feature should link to the tests... that prove it works."

**High-level findings**:
- **~25-30 core Python unit/integration tests** + 3 primary e2e specs + supporting harness files. Strong coverage for core surfaces (health, epics, release, babysit, bootstrap, MCP dispatch, native PR integration, information audit, .plate config, contemplation/curiosity answers, costs, delegation, template payload).
- **Classification (broad first pass)**: Majority of Epic/Feature-named tests and surface-specific tests qualify as **feature-proof** (directly exercise and assert documented user/agent-facing or process capabilities). A smaller set are **supporting** (deprecation guards, migration cutovers, specific regression, internal client mocks) or **infra** (GitHub client fakes, conftest patterns).
- **Bidirectional traceability**: Improving but incomplete. Some design docs (e.g. release-ceremony-refinement.md, plate-root-config-schema-lifecycle.md) already list specific proving tests in "Acceptance Evidence". Many others have placeholder or weak "tests pass / design committed" language. Tests rarely contain explicit back-references to the exact claim they prove (beyond module names and docstrings like "Tests for plate_core.release module" or "Initial tests for Core Information Audit engine (Epic #218 / Feature #221)").
- **Gaps surfaced on first pass** (expected per human point 4): Interactive epic planning engine (still stub in mcp_server.py per SPEC beta roadmap), full Contemplation Engine v2 contract (research notes gaps in test_curiosity_answers.py and missing dedicated coverage for contract evaluation/closure), some e2e depth beyond structure/catalog/host-install, explicit cross-links in most design "Acceptance Evidence" sections, and no repeatable classification/audit tooling yet (this Epic seeds it).
- **Alignment**: Excellent with existing Information Audit machinery (the 221 test + audit_tools.py prove the "discover unknowns from Goals" path; this Epic complements with "prove known implemented claims"). Strong dogfooding culture (tests often named after the capability they protect).

This skeleton report serves as the starting artifact. Future passes (via child Research work) will deepen classification, add more test reads, propose concrete convention updates, and close gaps via child Features/PRs.

## Test Inventory & Classification (Broad Pass)

**Legend**:
- **Feature-proof**: Directly demonstrates/proves a documented capability or surface (e.g. "health reports X", "babysit resolves actionable threads", "bootstrap seeds Goals", "e2e certifies CLI-agnostic structure", "information audit produces proposals grounded in Goals"). These are the primary targets for bidirectional references.
- **Supporting**: Regression guards, migration/deprecation hygiene, specific past-bug prevention, cutover verification, internal helpers.
- **Infra**: Test infrastructure, fakes, shared utilities, client mocks (important but not user-facing claims).

### Core Python Tests (tests/test_*.py)

| Test File | Primary Focus / What it "proves" | Classification | Linked Documented Claims / Surfaces | Notes / Initial Gaps |
|-----------|----------------------------------|----------------|-------------------------------------|----------------------|
| test_health.py | HealthReport, get_health (labels, protection, epic count, goals_page_present, plate_config detection, partial-failure resilience/errors list, status pass/warn) | Feature-proof | "Health check" (README, SPEC surfaces table, health.py, AGENTS health/epic status, Goals wiki convention); resilience (#270) | Excellent; already exercises goals_page_present and plate_config signals. Good model for future signals. |
| test_release.py | Release fragments, _list_versions (flat + dir layouts), get_release_status, notes diff, target epic guidance | Feature-proof | Release ceremony / tooling (SPEC beta roadmap "First-Class Release Tooling", release-ceremony-refinement.md Acceptance Evidence explicitly lists this + test_cut_release + test_bootstrap + test_native_..., AGENTS release loop, .agentic/releases/) | Strong; design doc already models the desired "Acceptance Evidence cites tests" pattern. |
| test_pr_babysit.py | babysit_pr, resolve_review_thread, _extract_actionable_threads (filters resolved/outdated), _detect_base_branch_out_of_sync, agent match (devin, OpenHands) | Feature-proof | PR babysit / feedback resolution (AGENTS §babysit detailed loop + base branch strategies, README MCP list, research/babysit-base-branch...md, SPEC supporting items) | Core of autonomous PR health. Local-rebase strategy noted as not-yet in some docs (see SPEC Feature item). |
| test_epics.py | get_epic_status (open count, child counts), project V2 items (GraphQL) | Feature-proof | Epic tracking / native milestones (SPEC, health integration, AGENTS Epic-close ceremony, native-github-pr-integration design) | Proves the "Milestones are the canonical Epic container". |
| test_bootstrap.py | run_bootstrap (dry-run actions: enable-wiki, branch-protection, seed-initial-questions, Goals handling) | Feature-proof | Bootstrap / new-repo checklist (SPEC Target Workflows, docs/bootstrap/new-repository-checklist.md, design docs, Goals seeding for #218/#224) | Ties directly to Information Audit (Goals page nudge) and health signals. |
| test_mcp.py | MCP tool dispatch (_handle_tools_call for plate_health and others), surfaces, structured payloads | Feature-proof | MCP server / tool surfaces (SPEC "plate-mcp", README MCP tools list, mcp_server.py, plugin wiring) | Foundational for agent surfaces. |
| test_221_core_audit_engine.py (and related) | PerformInformationAuditTool (stub + catalog defaults + Goals signals), baseline catalog informational goals (platform vs extension), agent_guidance includes audit section | Feature-proof | Information Audit engine (Epic #218 / #221 / design #223 / model #220, Goals.md as primary signal, baseline_catalog, agent_guidance.py INFORMATION_AUDIT_GUIDANCE, SPEC) | Explicit "tests first skeleton"; proves the complementary "discover gaps" path. |
| test_native_github_pr_integration.py | Feature templates use Epic milestones, label-check requiresMilestone (incl. Release), PR issue link check (CONNECTED_EVENT, Development sidebar, warning rollout) | Feature-proof | Native GitHub PR integration + milestone/label enforcement (design doc, AGENTS PR title/body rules + label requirements, workflows, Epic #100 lineage) | Design doc + this test are good examples. |
| test_features.py / test_cli.py | Feature detection (Playwright, plugin, etc.), CLI entrypoints | Feature-proof (mostly) | "gh plate features", capability detection (README, SPEC, features.py, e2e harness) | Mix; core flag reporting is feature-proof. |
| test_contemplation.py / test_curiosity_answers.py | Answer parsing, contemplation, RecordAnswer, backfill | Feature-proof (partial) + supporting | Curiosity / Q&A / Contemplation Engine (Epic #139, SPEC beta "Contemplation Engine v2", design/curiosity-answer-model.md, AGENTS QANDA section) | Research notes gaps for full v2 contract (answer_signal strict closure, append-only, etc.). See docs/research/contemplation-engine-v2-contract-enumeration.md. |
| test_costs.py / test_delegation.py | Cost aggregation, delegation flows | Feature-proof | Observability / delegation (SPEC "Observability: ... cost", "single-agent-delegation-flow" design, AGENTS usage report mandate) | Good for beta roadmap items. |
| test_epic89_* (plate_config, markers, artifacts, inventory, extensions, cutover) + test_plate_config related | .plate config lifecycle, markers, template payload inventory/cutover | Feature-proof (for that slice) + supporting (cutover) | .plate Root Config (SPEC beta Epic, design/plate-root-config-schema-lifecycle.md which cites `tests/test_epic89_plate_config.py` in Acceptance Evidence), template sync | Legacy Epic 89 work now foundational; plate-root-config design is a model for good Evidence citation. |
| test_current_md_* (stale_reference_audit, reference_docs) + test_cut_release + test_template_payload* + test_spec_audit | Deprecation of CURRENT.md, release note translation, template cutover, SPEC audit | Supporting (mostly) | Migration hygiene, deprecation (AGENTS, .agentic/releases/ as replacement, CURRENT.md itself marked deprecated) | Valuable guards; not primary "feature" proofs. |
| test_github_client.py, test_cli (deeper), conftest patterns | Client error handling, CLI basics, shared fixtures | Infra + supporting | Resilience (github_client), basic surfaces | Important for robustness claims but secondary. |
| test_contemplation.py | ContemplationEngine: close_signal_met requires checklist citations in answer, prose does not close, revision invalidates prior, blocking resumption posts comments, USAGE REPORT on close | Feature-proof (partial for contract) | Contemplation Engine contract (SPEC beta roadmap "Contemplation Engine v2", docs/design/contemplation-engine-contract.md Acceptance Evidence, design/curiosity-answer-model.md, AGENTS QANDA/Contemplation sections, Epic #139 invariants) | Proves key parts of #143 contract (citation verification, closure logic, revision handling). Per its research doc, full v2 (all artifact types, strict non-destructive transcript, complete forward progress) has gaps in coverage. |
| test_curiosity_answers.py | Answer Model: parse_plate_answer_blocks, build_answer_from_block, update_answers_index, get_answers, backfill (committed + GitHub comments) | Feature-proof | Curiosity Answer Model / storage (SPEC beta "Curiosity Answer Model", docs/design/curiosity-answer-model.md Acceptance Evidence, docs/design/informational-goals-model.md, AGENTS Answer Model / QANDA, mcp/curiosity_tools) | Covers lossless history, revision_of, index, backfill. Good traceability example. |
| test_features.py | get_features (flags for copilot-plugin, baseline-agents, current-md, playwright-e2e, autonomous-mode), detect_playwright_e2e_local | Feature-proof | Feature detection / "gh plate features" (README, SPEC surfaces + "gh plate features", features.py, e2e harness + plugin-structure tests, AGENTS E2E guidance) | Proves capability reporting and flexible heuristics for optional features like Playwright. |
| test_baseline_catalog.py | load_baseline_catalog, agents/skills, informational_goals (platform vs extension), primary_skill_ids etc. | Feature-proof | Baseline catalog / agent & skill surfaces (SPEC, README MCP list, docs/design/baseline-agents-*.md and agent-skill-registry, mcp/curiosity + audit tools, plugin/agents/plate.agent.md) | Foundation for discovery (plate_agents, plate_skills) and defaults in audits. |

**Other notes**: test_baseline_catalog.py proves catalog loading (informational goals, extensions). Many tests use mocks/fakes for GH (good for isolation). test_mcp.py has extensive coverage of tool dispatch (including stubs for plan_epic, what_next, etc.) — largely feature-proof for the documented MCP surface contract.

### E2E / Harness (tests/e2e/)

| Test / Spec | Primary Focus | Classification | Linked Claims | Notes |
|-------------|---------------|----------------|---------------|-------|
| plugin-structure.spec.ts | Declarative manifests (plugin.json fields, repository), plate.agent.md (required tools like plate_health/epic_status/delegate, baseline catalog mentions, no vendor terms like "Copilot CLI"), .mcp.json wiring | Feature-proof | "CLI-agnostic claims" / multi-host plugin model (Epic #205 lineage, e2e/README.md "host-independent simulation/certification", design docs on plugin/MCP surfaces, SPEC surfaces, AGENTS upstream sync) | Explicit certification language. Structure tests are the primary host-agnostic proof. |
| catalog-discovery.spec.ts | `gh plate agents` / `skills` via wrapper, baseline catalog expectations | Feature-proof | Catalog discovery surfaces (README, MCP catalog tools, agent guidance) | Complements Python catalog tests. |
| copilot-plugin.spec.ts | Real Copilot CLI install/uninstall + plugin load (skippable if no binary) | Feature-proof (host-specific) | Host install flows (e2e/README) | Validates real integration for one host; harness supports adaptation for others. |
| e2e/README.md + playwright.config + recording scripts | Harness purpose, running, "what passing means", update guidance for new MCP/tools | Feature-proof (the harness itself) | E2E + visual evidence for UI-facing (though this harness is more structure than UI), Playwright capability in features | Documents the "certifies claims" model. GIFs for demos (some in fixtures). |
| (template_payload copy) | Mirrored harness in payload for new repos | Supporting (for adopters) | Template inheritance of E2E | Ensures downstream projects get the capability. |

**tests/README.md** (the meta one): Codifies the entire evidence model (Unit/Integration/E2E/Regression/Manual + "link to tests that prove it"). This is a core process claim that the test suite itself helps prove. Should be referenced from AGENTS or design docs.

## Key Documented Claims Sample (High-Signal Current-State)

**From docs/wiki/Goals.md** (primary for Information Audits + strategic intent):
- Mission: reliable high-velocity agentic SDLC on GitHub; "operating system for agent-driven development".
- Core Principles: GitHub SSoT, Agent Autonomy default, **Test-First is Non-Negotiable**, Lightweight/GitHub-native, Evolvable.
- How we succeed: <15min adoption, 70-90% agent-driven, durability of knowledge (answers/artifacts), ecosystem.
- Current State references Curiosity/Q&A (#139), baseline catalog, start of Information Audit (#218), Goals convention.
- Open Questions tracked as Question issues.

**From SPEC.md**:
- North Star + surfaces table (gh plate, plate-mcp, Copilot plugin) with exact commands.
- Goals: test-first mandatory + continuous verifiable progress (SPEC → CURRENT via fragments), observability (health/velocity/cost), high autonomy + safety gates.
- Beta Roadmap: explicit list of Epics/Features (interactive planning engine as stub to replace, Contemplation v2, .plate config, release tooling, health expansion, E2E polish, catalog, observability, etc.).
- Target workflows, constraints, architecture.

**From design/ (Acceptance Evidence sections — user directive focus)**:
- Most end with `## Acceptance Evidence`. Good examples: release-ceremony-refinement.md (lists 4+ specific tests + bootstrap + fragments + AGENTS updates); plate-root-config...md (cites `tests/test_epic89_plate_config.py`); others are lighter ("tests pass", "committed design", "PRs pass").
- Similar in qanda-*.md, informational-goals-model.md, native-github-pr-integration.md, curiosity-answer-model.md, task-issue-type..., etc.
- Opportunity: Standardize a subsection or bullets: "- Proving tests: `tests/test_xxx.py:Class.test_foo` (and e2e if applicable). Evidence in this PR + fragment."

**Other**:
- AGENTS.md: Detailed rules for every work type (Feature requires tests + fragments + PR to correct base, etc.), babysit loop, autonomous mode, label rules, stub definition (now in #351).
- e2e/README + README: Explicit certification and MCP tool lists.
- Research docs: Often call out specific test files needed for gaps (e.g. contemplation v2 research).

## Findings & Gaps (First Pass)

**Strengths**:
- Dogfooding + naming discipline makes many tests self-documenting as proofs.
- Dedicated tests for nearly every major ceremony/surface in the beta roadmap.
- Existing audit-like tests (stale ref, spec, current md) + 221 engine show audit culture.
- Some designs already do the right thing in Acceptance Evidence.
- tests/README states the philosophy we are operationalizing.

**Gaps (prioritized for children)**:
1. **Interactive planning engine** (SPEC beta roadmap explicitly calls out the `_plan_epic_stub` in src/plate_core/mcp_server.py:36 and test_mcp.py:167 as Phase-1 stub to replace with full guided flow + child stubs + PLATE_SESSION_STATE. Current test only exercises the stub payload. test_mcp.py also has plate_plan_epic in tool list.)
2. **Contemplation v2 full contract** (docs/design/contemplation-engine-contract.md and docs/research/contemplation-engine-v2-contract-enumeration.md note gaps; test_contemplation.py covers citation-based close + revision + blocking, but not full non-destructive transcript for all artifact types, complete forward-progress creation, or strict closure only on verified signal for complex cases).
3. **Bidirectional explicit links & Acceptance Evidence hygiene**: Most design docs have the section (see grep results), but only a minority cite exact proving tests (e.g. release-ceremony-refinement.md, plate-root-config..., markers, cutover, agent-skill-registry). Many are criteria lists or "tests pass". Tests rarely back-link to the SPEC/Goals/design claim.
4. **E2E / compound flow depth**: plugin-structure and catalog are strong for CLI-agnostic + discovery claims. Limited coverage of full babysit loop (with branch-update), release cut + finalize ceremony, or end-to-end Q&A → contemplate → artifacts in the harness.
5. **Template payload + adopter inheritance**: The mirrored tests/e2e and docs in src/plate_core/template_payload/ (and new-repo checklist) claim the capabilities but the audit of claims vs tests there is thin (supporting cutover tests exist but not full feature-proof matrix for adopters).
6. **No repeatable tooling yet**: Classification and audit are manual (this Epic's goal). The planning stub and what_next are v1 heuristics that could integrate future test-audit signals.
7. **Other partials**: test_costs / delegation, some cli deeper paths, migration guards are good but lower-signal for "core surfaces" claims.
3. **Acceptance Evidence convention** (inconsistent; expand to always list exact proving tests + update existing design docs as part of this work).
4. **Bidirectional explicit links** (docs → tests and tests → claims; e.g. test docstrings + design sections + perhaps a central index or health signal later).
5. **Depth for newer/compound flows** (full babysit with branch update + resolve, end-to-end release cut + tag, full Q&A → contemplate → artifact creation loop in e2e or integration).
6. **Tooling for repeatability** (no `plate test-audit` or extension of information_audit yet; classification is manual today).
7. **Template payload + adopter view**: The harness copy in template_payload should also be audited for claims it makes about what new PLATE repos get.

**Risks observed**: Surface is broad (core + e2e + docs across design/research/wiki + AGENTS/SPEC); first pass is necessarily sampled. Classification can be subjective for "supporting" vs "feature-proof" (e.g. a regression test for a Feature may still prove the feature's guardrails).

## Recommendations & Next Steps (for this Epic)

1. **Adopt/expand "Acceptance Evidence" convention** (per user input): In every design/*.md and relevant research that describes implemented behavior, add or refine:
   ```
   ## Acceptance Evidence
   - Design/research artifact committed.
   - Proving tests: `tests/test_release.py` (fragments/versions/status), `tests/test_cut_release.py`, `tests/test_bootstrap.py`, `tests/test_native_github_pr_integration.py` (and e2e where applicable).
   - PR + fragment(s) under `.agentic/releases/unreleased/`.
   - Updated AGENTS.md / SPEC / docs as required.
   ```
   Update the 8-10 design docs that currently have the section.

2. **Update tests/README.md** (and template copy) to reference this audit convention and classification guidance. Add "Feature-proof vs. supporting" note.

3. **AGENTS.md guidance**: Add brief section (in test or documentation rules) on writing feature-proof tests with clear docstrings and referencing the claim/Epic.

4. **Child work**:
   - Research (first): Deepen this inventory (read all remaining test files + more docs), produce full classification matrix + gap list, propose exact convention text + updates to existing Evidence sections. Commit expanded version of this report or a companion classification doc.
   - Design: Formalize the proof-reference model (lightweight, no heavy new machinery) + updates to design template / audit report template.
   - Audit/Feature children: Execute gap closures (e.g. add tests + doc links for planning engine stub, contemplation coverage); optionally expose classification via MCP/CLI or integrate with health / information_audit.
   - Update this report with evidence from children.

5. **Session artifacts**: This file + GH comments + child issues (with `need:refinement`) + eventual PR(s) with `Closes #350` (after children) serve as the traceable record.

6. **Alignment**: Keep this complementary to Information Audits (use Goals page + catalog as one signal source here too). No duplication of #218 engine.

## Follow-Up

- Corrective / gap issues created as children of #350.
- Re-run / expand this audit after major landings (e.g. planning engine, contemplation v2).
- Consider adding a lightweight `plate test-coverage-audit --dry-run` (or similar) in a Feature child for ongoing cheap execution.
- Human review of classification edge cases and priority of gaps.

**Status**: Initial skeleton complete. Broad inventory + classification pass done. Ready for Research child to deepen + first doc convention updates.

---

## Addendum (2026-07-27) — v1.0 autonomy surface proofs (#907 / #364 batch)

Post-#470 / #654 landings added substantial feature-proof coverage that this June skeleton did not list. Classification for agent routing:

| Test File | Primary claim proved | Classification | Notes |
|-----------|----------------------|----------------|-------|
| `tests/test_what_next.py` | Empty-pipeline ranking: budget → open PR → ready issue → PM active queue → epic closeout/refine when PM idle (#905/#907); CLI `what-next` | Feature-proof | Live `get_what_next` wiring mocked for PM idle vs active; pure `recommend_what_next` matrix |
| `tests/test_pm.py` | PM assign/tick/queue; `queue_size` active-only (`proposed\|delegated\|blocked`, not done/cancelled) (#903/#904); loop idle stop | Feature-proof | Core #660 surface |
| `tests/test_autonomy.py` | AutonomyEngine config, budget, procedures, risk gates (#470) | Feature-proof | Heart of autonomy runtime |
| `tests/test_ledger.py` | Provenance / decision ledger (#647) | Feature-proof | Safety stack |
| `tests/test_cost_control_thin_surfaces.py` | Cost/risk thin surfaces toward feed (#653) | Feature-proof (thin) | Complements costs tests |

**Gap closed in this batch (#907):** Bidirectional proof that idle PM + open epics does **not** force PM dry-run; active `open_assignments` / delegated rows still rank PM/tick. Tests declare `Proves:` claims in docstrings.

**Closed (partial) under #921:** Contemplation full transcript (`Answer full:` + question title/body excerpt) and typed Research/Design/Feature follow-ups with parent Question link.

**Closed (partial) under #923:** Contemplation git commit provenance + structured Provenance fields in transcript (Design #142 gap first slice).

**Closed (partial) under #925:** Contemplation artifact mutation intents + PR-only draft plan Feature issues (Design #143 §2 / research §3.3 first slice). Detects process paths, logs intents, high-risk need:human-review; does **not** auto-push or open PRs.

**Closed (partial) under #927:** Compound Playwright e2e offline chain — `tests/e2e/compound-flows.spec.ts` + `fixtures/compound_flow_driver.py` proves babysit gate block/unblock, release cut dry-run (no write) + `plan_gh_plate_sync` dry surface, and contemplate→mutation PR draft plan without network.

**Closed (partial) under #929:** Contemplation structured `mutation_pr_plan` + `apply_mutation_pr_plan` dry-run default (gh_argv/git_steps); high-risk requires `allow_high_risk`; live apply only via injectable runner (no default auto-push).

**Closed (first slice) under #917:** template_payload adopter harness parity — `TemplatePayloadAdopterClaimsTests` proves payload ships AGENTS/SPEC, e2e README+example specs, core workflows; `list_payload_files` + import dry-run plan those paths. Monorepo-only `plugin-structure.spec.ts` / `catalog-discovery.spec.ts` (hardcoded `.plugin` layout) intentionally **not** copied into payload; adopters get example harness + import-payload instead.

**Closed (unit compound) under #919:** `TestWhatNextCompoundPriorityLadder` proves budget → open PR → ready → PM tick/active → named closeout → empty-closeout stub refine in one compound suite (#905/#913/#915). Offline Playwright compound covered by #927.

---

## Addendum (2026-07-27) — #364 high-priority gap closeout

Feature #364 (child of Epic #350) is **closed for high-priority inventory gaps** after the v1.0 proof batches above. Success criteria mapping:

| #364 success criterion | Evidence |
|------------------------|----------|
| Top 4–6 inventory gaps have proving tests + doc refs | what_next/PM idle (#907/#919); template_payload adopter (#917); Contemplation transcript/typed follow-ups/provenance/mutation plan (#921/#923/#925/#929); compound offline ceremony e2e (#927) |
| Audit report shows those gaps closed with PR/test links | This addendum + closed (partial) rows above |
| Acceptance Evidence cites proving tests | `docs/design/contemplation-engine-contract.md`; e2e README compound-flows; research closeout `docs/research/364-test-coverage-gap-closeout.md` |
| PR(s) carry process + `Closes #N` | #908, #918, #920, #922, #924, #926, #928, #930 + this closeout PR |

### Intentionally deferred (not #364 blockers)

| Deferred item | Why deferred | Follow-on home |
|---------------|--------------|----------------|
| Contemplation live auto-push / `gh pr create` without injectable runner | Safety: default remains dry-run; high-risk needs human + `allow_high_risk` | Contemplation v2.2+ under Epic #257 / future Feature |
| Live-network babysit→merge and cut+tag+finalize apply in CI | Needs secrets, real remotes, non-idempotent tags | Optional nightly / human Task; offline harness is the cert for #364 |
| Full interactive epic planning engine replacement | Separate product Feature (SPEC Phase-1), not mere test gap | Own Feature under planning / MCP surface work |

### Proving-test index (bidirectional)

| Claim area | Primary proving tests |
|------------|----------------------|
| what_next priority ladder | `tests/test_what_next.py` (`TestWhatNextCompoundPriorityLadder`, idle/active PM) |
| template_payload adopter | `tests/test_template_payload*.py` / adopter claims suite (#917) |
| Contemplation contract (partial→v2.1) | `tests/test_contemplation.py` |
| Compound ceremony offline | `tests/e2e/compound-flows.spec.ts` + `fixtures/compound_flow_driver.py` |
| Answer model | `tests/test_curiosity_answers.py` |

Parent Epic #350 may remain open for broader classification tooling / remaining low-priority inventory; #364 high-priority gap closure is complete.

---
*This report follows the template in `docs/audits/audit-report-template.md`. Per PLATE Issue Artifact Rules for Audit/Epic work, findings live in `docs/audits/`.*
