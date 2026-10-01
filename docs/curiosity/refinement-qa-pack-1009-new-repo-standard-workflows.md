# Refinement Q&A Pack: New-Repo Standard Workflows (Epic #1008)

**Question Issue:** #1009  
**Parent Epic:** #1008 — New-repo standard workflows  
**Milestone:** New-repo standard workflows  
**Prepared for:** Andrew (solopreneur, prefers slow-paced agent-delegated work)  
**Estimated time:** 15-20 minutes total  

---

## Overview

This pack helps refine Epic #1008 (New-repo standard workflows) by clarifying two high-leverage areas:
1. **CI/CD discovery workflow** — how agents should discover test needs and name components
2. **Development philosophy encoding** — how to capture the real human ecosystem and adapt PLATE's defaults

The answers will shape concrete child issues, scope boundaries, and the agent-guided workflows that bootstrap these capabilities into new PLATE repositories.

---

## Theme A: CI/CD Discovery & Test Inventory

### Q1: Test layer philosophy

**Context:** PLATE can guide agents to build a comprehensive test inventory (unit / integration / acceptance / HITL). Should the discovery workflow enforce test-first discipline strictly, or allow progressive adoption?

**Options:**
- **A. Strict test-first (recommended)** — Agent must create test stubs before implementation for every Feature; CI fails without tests. Aligns with PLATE's core TDD/BDD discipline.
- **B. Progressive** — Allow test-optional for MVP/prototype phases; agent warns but doesn't block. Risk: undermines test-first culture.
- **C. Configurable per-repo** — Let `.plate` config declare `test_discipline: strict|progressive|optional`. Adds complexity.

**Rationale:** This unlocks whether the CI/CD workflow can assume tests exist, or must scaffold test creation as a separate agent task.

**Recommended:** A (strict test-first) — PLATE's north star requires verifiable progress.

---

### Q2: Human-in-the-loop (HITL) test scope

**Context:** Some products require human verification (UI/UX feel, game balance, accessibility, Steam deployment). Should PLATE's CI/CD discovery explicitly name and scaffold HITL tests?

**Options:**
- **A. Yes, first-class (recommended)** — Discovery asks about HITL needs; creates Task issues for human verification steps; documents in test inventory.
- **B. No, out of scope** — Treat HITL as external; agents only scaffold automated CI.
- **C. Optional flag** — Only discover HITL if user opts in during bootstrap.

**Rationale:** Determines whether the test inventory is complete or assumes "automation only." Affects Task issue generation and Q&A interview questions.

**Recommended:** A (first-class) — Epic body explicitly calls out "computer-operator agents for Steam games" as a motivating example.

---

### Q3: CI/CD component naming depth

**Context:** After discovering test needs, how should agents select and name specific CI/CD tooling (runners, frameworks, environments)?

**Options:**
- **A. Opinionated defaults (recommended)** — Agent proposes a PLATE-blessed stack (e.g., GitHub Actions + Playwright + pytest + shell scripts per #1017) unless user overrides.
- **B. Full discovery** — Agent researches and offers 3-5 options per component; user chooses.
- **C. User-declared only** — Agent requires explicit tooling choices upfront; no recommendations.

**Rationale:** Balances time-to-value against flexibility. Full discovery adds Q&A toil; opinionated defaults align with "sane defaults" philosophy.

**Recommended:** A (opinionated) — Andrew prefers agent-delegated work; full discovery adds friction.

---

### Q4: Non-obvious verification surfaces

**Context:** Beyond typical web CI (unit tests, Playwright), should the discovery workflow probe for non-obvious surfaces (desktop apps, game platforms, marketplace publish, hardware-adjacent flows)?

**Options:**
- **A. Yes, comprehensive probe (recommended)** — Discovery asks about deployment targets, platforms, operator touchpoints; names them in test inventory even if not yet automated.
- **B. No, assume web-first** — Only discover standard web/API CI; let user file custom issues for exotic cases.

**Rationale:** Epic body emphasizes "unnamed or non-obvious processes" as a key differentiator. Comprehensive probe unlocks full verification surface.

**Recommended:** A (comprehensive) — core value proposition of this Epic.

---

## Theme B: Development Philosophy Encoding

### Q5: Team size assumption

**Context:** PLATE ships solopreneur-oriented defaults. Should the philosophy encoding workflow adapt those defaults based on discovered team size?

**Options:**
- **A. Yes, adaptive (recommended)** — Discovery asks "How many humans on this project?" and encodes answer into `.plate` / `AGENTS.md` / persona; adjusts review gates, Q&A authority, and Epic planning scope.
- **B. No, always solopreneur** — Assume single human developer; power users edit manually.
- **C. Prompt once during bootstrap; don't re-encode** — One-time question during `gh plate bootstrap`; no dedicated Epic workflow.

**Rationale:** Andrew runs many projects; some may need contractors or future growth. Adaptive encoding makes PLATE's defaults match reality.

**Recommended:** A (adaptive) — Epic explicitly calls out "How many humans?" as a discovery question.

---

### Q6: Experience level calibration

**Context:** PLATE's agent prompts and Q&A surfaces can vary based on developer experience (junior, mid, senior, founding engineer).

**Options:**
- **A. Yes, encode and adapt (recommended)** — Discovery asks experience level(s); adjusts Q&A verbosity, auto-stub generation risk, and review expectations in agent guidance.
- **B. No, assume expert** — PLATE always assumes senior+ developers; juniors ask for help manually.
- **C. Global user preference** — User sets experience once in Cursor settings; not per-repo.

**Rationale:** Per-repo encoding lets Andrew delegate differently across projects (e.g., experimental repo = high autonomy; client project = cautious).

**Recommended:** A (per-repo encoding) — aligns with Epic's "real ecosystem" goal.

---

### Q7: Q&A authority model

**Context:** PLATE Q&A (Contemplation, planning, Epic refinement) currently assumes the GitHub repo owner is the human decision-maker. Should the encoding workflow discover a broader authority model?

**Options:**
- **A. Yes, encode explicit roles (recommended)** — Discovery asks: "Who can answer product Q&A? Who approves Epics? Who reviews code?" Encodes into `AGENTS.md` + `CODEOWNERS`.
- **B. No, always repo owner** — Simplest; matches current practice.
- **C. Defer to GitHub roles** — Use GitHub org/team permissions; no PLATE-specific encoding.

**Rationale:** Solo projects: simple. Team projects: explicit roles prevent agent confusion ("Who should I ask?"). Supports Andrew's future delegation to contractors.

**Recommended:** A (encode roles) — future-proof without breaking solo case.

---

### Q8: Methodology preference

**Context:** PLATE enforces process (issues, labels, ceremonies) but doesn't mandate a development methodology (Scrum, Kanban, Shape Up, unstructured).

**Options:**
- **A. Yes, discover and document (recommended)** — Ask: "Do you follow a specific methodology?" Document answer in `AGENTS.md` / process docs; let agents adapt language (e.g., "sprint" vs "iteration" vs "cycle").
- **B. No, methodology-agnostic** — PLATE terms are universal; don't ask.

**Rationale:** Helps agents speak the team's language. Low-cost question; high clarity payoff.

**Recommended:** A (discover) — improves agent communication, especially for teams.

---

## Theme C: Scope & Integration

### Q9: Relationship to bootstrap (#633)

**Context:** Epic #633 (frictionless integration + new-project bootstrap) overlaps with this Epic. Should these workflows merge, compose, or remain separate?

**Options:**
- **A. Compose (recommended)** — Bootstrap creates standing structure (branches, Next Release, labels); **this Epic** adds CI/CD + philosophy discovery as a second-phase interactive workflow (e.g., `gh plate setup-ci`, `gh plate encode-team`).
- **B. Merge** — Fold all discovery into a single mega-bootstrap session.
- **C. Separate** — Treat as independent; user runs manually when ready.

**Rationale:** Composition respects "progressive enhancement" and keeps bootstrap fast. Mega-bootstrap adds toil. Separation risks users forgetting to run.

**Recommended:** A (compose) — bootstrap first, then discovery workflows on demand or nudged by health.

---

### Q10: Artifact outputs

**Context:** After discovery completes, what durable artifacts should land in the repo?

**Check all that apply:**
- ☑ Test inventory document (`docs/plate/ci-cd/test-inventory.md` per #1015)
- ☑ CI/CD component manifest (`.plate` extension or separate)
- ☑ Team/philosophy summary (`AGENTS.md` updates or `docs/plate/team.md`)
- ☑ Human Tasks for external setup (Steam keys, CI secrets, marketplace publish)
- ☑ Stub issues for unauthenticated tests (Playwright, E2E)
- ☐ Full CI workflow files (or defer to Feature implementation)
- ☐ Other: _____________

**Rationale:** Determines whether the discovery is "planning only" or produces immediate actionable outputs.

**Recommended:** First 5 checked — concrete but defers heavy CI implementation to child Features.

---

## Proposed Scope (Draft)

Based on the above Q&A, the refined Epic #1008 would include:

### In scope
1. **CI/CD discovery workflow** (interactive agent-guided interview)
   - Probe product surface, platforms, test layers (unit/integration/acceptance/HITL)
   - Name specific components (opinionated PLATE-blessed defaults with override)
   - Discover non-obvious verification surfaces (desktop, game platforms, marketplace, hardware)
   - Output: test inventory doc + component manifest + stub issues + human Tasks
   
2. **Development philosophy encoding workflow** (interactive Q&A)
   - Team size, experience levels, Q&A authority roles, methodology preference
   - Encode into `.plate`, `AGENTS.md`, `CODEOWNERS`, process docs
   - Adapt agent verbosity, autonomy defaults, review expectations
   - Output: updated process artifacts + team summary doc

3. **Integration with bootstrap** (#633)
   - Compose: bootstrap first (structure), then discovery (CI + team)
   - Health surfaces nudge when test inventory or team encoding is missing

4. **Default stack per #1017**
   - Shell scripts unless Windows support declared
   - Playwright for web acceptance tests
   - pytest for Python, GitHub Actions for CI
   - Opinionated but overridable

### Explicitly out of scope (non-goals)
- Full CI workflow implementation (Feature children will scaffold)
- Replacing bootstrap or adoption workflow wholesale
- Choosing CI stack without discovery (opinionated defaults **are** the discovery output)
- Supporting non-test-first workflows (PLATE enforces TDD/BDD)
- Encoding team/philosophy without human input (no silent assumptions)

---

## Candidate Child Issues (Ordered)

Based on answers, the Epic would decompose into ~6-8 child issues:

1. **Research: CI/CD Test Layer Taxonomy & Verification Surface Model** (#1008.1)
   - Define unit/integration/acceptance/HITL categories for PLATE
   - Research non-obvious verification surfaces (desktop, game, marketplace)
   - Output: `docs/plate/research/ci-cd-test-taxonomy.md`
   - Labels: `Research`, `area:tests`, `risk:low`

2. **Design: CI/CD Discovery Interview Flow** (#1008.2)
   - Design Q&A flow: product surface → platforms → test layers → components → HITL
   - Specify artifact outputs (test inventory doc, component manifest, Tasks)
   - Output: `docs/plate/design/ci-cd-discovery-flow.md`
   - Labels: `Design`, `area:tests`, `area:infra`, `risk:low`

3. **Feature: CI/CD Discovery Workflow (MCP + CLI)** (#1008.3)
   - Implement `plate_discover_ci_cd` (MCP) / `gh plate setup-ci` (CLI)
   - Interactive Q&A per design; opinionated defaults (Playwright, pytest, shell scripts per #1017)
   - Generate test inventory doc under `docs/plate/ci-cd/`
   - Create stub Feature issues for unauthenticated test scaffolding
   - Create human Tasks for external CI secrets/accounts
   - Labels: `Feature`, `area:tests`, `area:infra`, `area:agent`, `risk:medium`
   - Fragment: describe new agent workflow + MCP surface

4. **Research: Development Ecosystem Questionnaire** (#1008.4)
   - Define Q&A for team size, experience, roles, methodology
   - Research how to encode into `.plate` / `AGENTS.md` / `CODEOWNERS`
   - Output: `docs/plate/research/dev-philosophy-questionnaire.md`
   - Labels: `Research`, `area:product`, `area:agent`, `risk:low`

5. **Design: Philosophy Encoding Targets & Agent Adaptation Model** (#1008.5)
   - Specify where each answer lands (`.plate` schema extensions, `AGENTS.md` sections)
   - Design how agents adapt behavior (verbosity, auto-stub risk, review expectations)
   - Output: `docs/plate/design/philosophy-encoding-model.md`
   - Labels: `Design`, `area:agent`, `area:product`, `risk:low`

6. **Feature: Development Philosophy Encoding Workflow (MCP + CLI)** (#1008.6)
   - Implement `plate_encode_team_philosophy` (MCP) / `gh plate encode-team` (CLI)
   - Interactive Q&A per questionnaire; update `.plate` + `AGENTS.md` + docs
   - Generate team summary doc under `docs/plate/team.md` (or similar)
   - Labels: `Feature`, `area:agent`, `area:product`, `risk:medium`
   - Fragment: describe new config sections + agent adaptation

7. **Feature: Health Integration for Discovery Nudges** (#1008.7)
   - Extend `plate_health` / `gh plate health` to check for test inventory + team encoding
   - Report warnings when missing; suggest `gh plate setup-ci` / `gh plate encode-team`
   - Labels: `Feature`, `area:product`, `risk:low`

8. **Design: Bootstrap + Discovery Composition Model** (#1008.8)
   - Specify how bootstrap (#633) and these workflows compose
   - Define user journey: `gh plate bootstrap` → health nudge → `setup-ci` → `encode-team`
   - Update bootstrap documentation to reference discovery as phase 2
   - Output: `docs/plate/design/bootstrap-discovery-composition.md`
   - Labels: `Design`, `area:product`, `area:infra`, `risk:low`

---

## Next Steps (for Andrew)

1. **Answer these 10 questions** (15-20 minutes) — recommended defaults are marked.
2. **Review proposed scope** — adjust in-scope / out-of-scope boundaries.
3. **Review candidate child issues** — reorder, merge, split, or add as needed.
4. **Approve or refine** — agent will then:
   - Update Epic #1008 body with concrete scope, non-goals, success criteria
   - Create the 6-8 child issues as stubs (labeled, linked to milestone, `need:refinement` removed)
   - Close Question #1009 via Documentation PR with this pack + Epic updates
   - Mark #1008 as `status:ready-to-work` (no longer a stub)

**Estimated total effort to ship:** 4-6 weeks of agent time (Research + Design + 2 Features), assuming other Epics don't block. No calendar time estimate per PLATE doctrine.

---

**References:**
- Epic #1008: https://github.com/akasper/plate/issues/1008
- Question #1009: https://github.com/akasper/plate/issues/1009
- Related: #633 (bootstrap), #1017 (shell-first scripts), #1015 (docs namespacing under `docs/plate/`)
- AGENTS.md §Required Work Loop (Research, Design, Feature)
- SPEC.md §Goals (test-first mandatory, 70-90% agent-driven SDLC)
