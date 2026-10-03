# Refinement Q&A Pack: New-Repo Standard Workflows (Epic #1008)

**Question Issue:** #1009  
**Parent Epic:** #1008 — New-repo standard workflows  
**Milestone:** New-repo standard workflows  
**Prepared for:** Andrew (solopreneur, prefers slow-paced agent-delegated work)  
**Status:** Answered by Andrew on 2026-10-03. Recorded on PR #1026. Question #1009 stays open until that PR merges.

---

## Overview

Andrew answered every question in this pack. The decisions below are the launch scope for Epic #1008.

1. **CI/CD discovery** is strict test-first, GitHub-first, and Playwright-wherever-possible. Common stacks get opinionated defaults (pytest for Python; shell scripts per #1017). Uncommon stacks (Roblox is the example) get research-based discovery. HITL is optional opt-in, not a first-class layer.
2. **Philosophy encoding** assumes a solopreneur, always asks how many humans are on the project and what the methodology is, and encodes experience per repo. Q&A authority at launch is always the repo owner. Role encoding and team-size-adaptive gates are vision only.

Docs for this Epic live under `docs/plate/` (#1015). This pack does not change `.plate`.

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

**Answer (Andrew):** A. Strict test-first.

---

### Q2: Human-in-the-loop (HITL) test scope

**Context:** Some products require human verification (UI/UX feel, game balance, accessibility, Steam deployment). Should PLATE's CI/CD discovery explicitly name and scaffold HITL tests?

**Options:**
- **A. Yes, first-class (recommended)** — Discovery asks about HITL needs; creates Task issues for human verification steps; documents in test inventory.
- **B. No, out of scope** — Treat HITL as external; agents only scaffold automated CI.
- **C. Optional flag** — Only discover HITL if user opts in during bootstrap.

**Rationale:** Determines whether the test inventory is complete or assumes "automation only." Affects Task issue generation and Q&A interview questions.

**Recommended:** A (first-class) — Epic body explicitly calls out "computer-operator agents for Steam games" as a motivating example.

**Answer (Andrew):** C. Optional opt-in. HITL is not first-class at launch. Discovery scaffolds HITL Tasks only when the user opts in. The first-class HITL assumption moves to vision / later.

---

### Q3: CI/CD component naming depth

**Context:** After discovering test needs, how should agents select and name specific CI/CD tooling (runners, frameworks, environments)?

**Options:**
- **A. Opinionated defaults (recommended)** — Agent proposes a PLATE-blessed stack (e.g., GitHub Actions + Playwright + pytest + shell scripts per #1017) unless user overrides.
- **B. Full discovery** — Agent researches and offers 3-5 options per component; user chooses.
- **C. User-declared only** — Agent requires explicit tooling choices upfront; no recommendations.

**Rationale:** Balances time-to-value against flexibility. Full discovery adds Q&A toil; opinionated defaults align with "sane defaults" philosophy.

**Recommended:** A (opinionated) — Andrew prefers agent-delegated work; full discovery adds friction.

**Answer (Andrew):** Hybrid A+B. GitHub-first for everything, Playwright wherever possible; opinionated defaults for common stacks (e.g. pytest for Python); research-based discovery for uncommon stacks (e.g. Roblox game dev). Shell scripts stay the default per #1017.

---

### Q4: Non-obvious verification surfaces

**Context:** Beyond typical web CI (unit tests, Playwright), should the discovery workflow probe for non-obvious surfaces (desktop apps, game platforms, marketplace publish, hardware-adjacent flows)?

**Options:**
- **A. Yes, comprehensive probe (recommended)** — Discovery asks about deployment targets, platforms, operator touchpoints; names them in test inventory even if not yet automated.
- **B. No, assume web-first** — Only discover standard web/API CI; let user file custom issues for exotic cases.

**Rationale:** Epic body emphasizes "unnamed or non-obvious processes" as a key differentiator. Comprehensive probe unlocks full verification surface.

**Recommended:** A (comprehensive) — core value proposition of this Epic.

**Answer (Andrew):** A. Comprehensive probe.

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

**Answer (Andrew):** Assume solopreneur by default; add a default question asking how many humans are on the project and what the development methodology is (this also covers Q8 methodology: ask). The headcount answer is recorded. It does not adapt review gates, Q&A authority, or Epic planning scope. That team-size adaptive assumption moves to vision / later.

---

### Q6: Experience level calibration

**Context:** PLATE's agent prompts and Q&A surfaces can vary based on developer experience (junior, mid, senior, founding engineer).

**Options:**
- **A. Yes, encode and adapt (recommended)** — Discovery asks experience level(s); adjusts Q&A verbosity, auto-stub generation risk, and review expectations in agent guidance.
- **B. No, assume expert** — PLATE always assumes senior+ developers; juniors ask for help manually.
- **C. Global user preference** — User sets experience once in Cursor settings; not per-repo.

**Rationale:** Per-repo encoding lets Andrew delegate differently across projects (e.g., experimental repo = high autonomy; client project = cautious).

**Recommended:** A (per-repo encoding) — aligns with Epic's "real ecosystem" goal.

**Answer (Andrew):** A. Per-repo experience encoding.

---

### Q7: Q&A authority model

**Context:** PLATE Q&A (Contemplation, planning, Epic refinement) currently assumes the GitHub repo owner is the human decision-maker. Should the encoding workflow discover a broader authority model?

**Options:**
- **A. Yes, encode explicit roles (recommended)** — Discovery asks: "Who can answer product Q&A? Who approves Epics? Who reviews code?" Encodes into `AGENTS.md` + `CODEOWNERS`.
- **B. No, always repo owner** — Simplest; matches current practice.
- **C. Defer to GitHub roles** — Use GitHub org/team permissions; no PLATE-specific encoding.

**Rationale:** Solo projects: simple. Team projects: explicit roles prevent agent confusion ("Who should I ask?"). Supports Andrew's future delegation to contractors.

**Recommended:** A (encode roles) — future-proof without breaking solo case.

**Answer (Andrew):** Launch: always repo owner. Vision (post-launch): allow encoding of specific roles. Q8 is covered by Q5 (methodology asked as a default question). Role encoding is not launch scope.

---

### Q8: Methodology preference

**Context:** PLATE enforces process (issues, labels, ceremonies) but doesn't mandate a development methodology (Scrum, Kanban, Shape Up, unstructured).

**Options:**
- **A. Yes, discover and document (recommended)** — Ask: "Do you follow a specific methodology?" Document answer in `AGENTS.md` / process docs; let agents adapt language (e.g., "sprint" vs "iteration" vs "cycle").
- **B. No, methodology-agnostic** — PLATE terms are universal; don't ask.

**Rationale:** Helps agents speak the team's language. Low-cost question; high clarity payoff.

**Recommended:** A (discover) — improves agent communication, especially for teams.

**Answer (Andrew):** Covered by Q5. Methodology is asked as a default question together with the number of humans. There is no separate methodology decision.

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

**Answer (Andrew):** A. Compose.

---

### Q10: Artifact outputs

**Context:** After discovery completes, what durable artifacts should land in the repo?

**Check all that apply:**
- ☑ Test inventory document (`docs/plate/ci-cd/test-inventory.md` per #1015)
- ☑ CI/CD component manifest (`.plate` extension or separate)
- ☑ Team/philosophy summary (`AGENTS.md` updates or `docs/plate/team.md`)
- ☑ Human Tasks for external setup (Steam keys, CI secrets, marketplace publish)
- ☑ Stub issues for unautomated tests (Playwright, E2E)
- ☐ Full CI workflow files (or defer to Feature implementation)
- ☐ Other: _____________

**Rationale:** Determines whether the discovery is "planning only" or produces immediate actionable outputs.

**Recommended:** First 5 checked — concrete but defers heavy CI implementation to child Features.

**Answer (Andrew):** The first five: test inventory doc, CI/CD component manifest, team/philosophy summary, human Tasks for external setup, stub issues for unautomated tests. Not full CI workflow files.

---

## Proposed Scope

Launch scope for Epic #1008, from Andrew's answers.

### In scope
1. **CI/CD discovery workflow** (interactive, second phase after bootstrap)
   - Strict test-first. The agent creates test stubs before implementation. CI fails when tests are missing.
   - Layers in the inventory: unit, integration, and acceptance.
   - Comprehensive probe of deployment targets, platforms, and operator touchpoints, including non-obvious surfaces (desktop, game platforms, marketplace publish, hardware-adjacent flows). Name them in the test inventory even when they are not automated yet.
   - Component naming is GitHub-first for everything, and Playwright wherever a browser or UI surface exists.
   - Common stacks get opinionated defaults. Python uses pytest. Scripts are shell scripts unless the repo declares Windows support (#1017).
   - Uncommon stacks use research-based discovery. Roblox game development is the motivating example: the agent investigates and proposes, rather than forcing a blessed default.
   - HITL is optional opt-in. The interview scaffolds human verification Tasks only when the user opts in.
   - Outputs: test inventory (`docs/plate/ci-cd/test-inventory.md`), CI/CD component manifest, stub issues for unautomated tests, and human Tasks for external setup (accounts, secrets, marketplace publish).
   - Discovery does not write full CI workflow files.

2. **Development philosophy encoding** (launch slice)
   - Assume a solopreneur by default.
   - Always ask how many humans are on the project, and what the development methodology is (or that there is none). Q8 is this question, not a separate decision. Record both answers in the team/philosophy summary.
   - Do not adapt review gates, Q&A authority, or Epic planning scope from the headcount answer.
   - Encode experience per repository. That encoding may adjust Q&A verbosity, auto-stub generation risk, and review expectations.
   - Q&A authority at launch is always the repo owner.
   - Output: team/philosophy summary under `docs/plate/team.md` and/or an `AGENTS.md` section.

3. **Compose with bootstrap** (#633)
   - Bootstrap creates standing structure. This Epic adds CI/CD and philosophy discovery as phase 2 (`gh plate setup-ci`, `gh plate encode-team`), nudged by health when the inventory or the summary is missing.

### Success criteria
- [ ] Discovery enforces strict test-first and writes unit, integration, and acceptance coverage into the inventory
- [ ] Naming is GitHub-first, uses Playwright wherever possible, defaults pytest and shell scripts for common stacks, and researches uncommon stacks
- [ ] The comprehensive probe names non-obvious verification surfaces even when they are not automated
- [ ] HITL Tasks are created only on opt-in
- [ ] Artifacts are the test inventory, component manifest, team/philosophy summary, human Tasks, and stub issues for unautomated tests
- [ ] Full CI workflow files are not a discovery output
- [ ] Philosophy encoding asks human count and methodology, encodes experience per repo, and leaves authority with the repo owner
- [ ] Workflows compose with bootstrap as phase 2, with health nudges

### Explicitly out of scope (non-goals)
- Full CI workflow file implementation (later Features scaffold those)
- Replacing bootstrap (#633) or folding discovery into a single mega-bootstrap session
- Non-test-first or test-optional workflows
- Silent team or philosophy assumptions that skip the default questions
- Changing `.plate` as part of this refinement (implementation Features may propose schema later, in their own PRs)
- The three items in Vision / later

### Vision / later (not launch scope)
- **HITL as a first-class layer.** Launch is optional opt-in only. Always-on HITL discovery, inventory sections, and Task scaffolding wait.
- **Team-size adaptive defaults.** Launch records how many humans there are and still behaves as a solopreneur tool. Changing review gates, Q&A authority, or planning scope from team size waits.
- **Role encoding.** Launch Q&A authority is always the repo owner. Encoding who may answer product Q&A, approve Epics, or review code (`AGENTS.md` roles, `CODEOWNERS`) waits until after launch.

---

## Candidate Child Issues (Ordered)

Eight stubs, created and linked as sub-issues of #1008. Each should carry `status:stub` and `need:refinement` until its own refinement. Milestone for every child: **New-repo standard workflows**.

The integration token created these issues and linked them, and could not add labels or the milestone. Apply the labels below if they are missing.

1. **#1031 — Research: CI/CD test layer taxonomy and verification surface model**
   - Unit, integration, and acceptance under strict test-first. HITL documented as optional opt-in, not a required layer. Comprehensive probe of non-obvious surfaces.
   - Output: `docs/plate/research/ci-cd-test-taxonomy.md`
   - Labels: `Research`, `area:tests`, `risk:low`, `status:stub`, `need:refinement`

2. **#1032 — Design: CI/CD discovery interview flow**
   - GitHub-first, Playwright wherever possible, pytest and shell defaults, research path for uncommon stacks (Roblox), HITL only on opt-in, artifacts from Q10, no CI workflow files.
   - Output: `docs/plate/design/ci-cd-discovery-flow.md`
   - Labels: `Design`, `area:tests`, `area:infra`, `risk:low`, `status:stub`, `need:refinement`

3. **#1033 — Feature: CI/CD discovery workflow for new repositories**
   - `gh plate setup-ci` and MCP `plate_discover_ci_cd`. Writes `docs/plate/ci-cd/test-inventory.md` and the component manifest. Opens stub issues for unautomated tests and human Tasks for external setup.
   - Labels: `Feature`, `area:tests`, `area:infra`, `area:agent`, `risk:medium`, `status:stub`, `need:refinement`

4. **#1034 — Research: Development ecosystem questionnaire**
   - Solopreneur default. Default questions: human count and methodology (Q8 covered here). Per-repo experience. Authority is the repo owner. Headcount is recorded, not used to retune gates. No role matrix.
   - Output: `docs/plate/research/dev-philosophy-questionnaire.md`
   - Labels: `Research`, `area:product`, `area:agent`, `risk:low`, `status:stub`, `need:refinement`

5. **#1035 — Design: Philosophy encoding targets and experience adaptation**
   - Where human count, methodology, and experience are stored. Experience may change verbosity, auto-stub risk, and review expectations. No `CODEOWNERS` role encoding and no team-size gate adaptation.
   - Output: `docs/plate/design/philosophy-encoding-model.md`
   - Labels: `Design`, `area:agent`, `area:product`, `risk:low`, `status:stub`, `need:refinement`

6. **#1036 — Feature: Development philosophy encoding workflow**
   - `gh plate encode-team` and MCP `plate_encode_team_philosophy`. Asks the default questions, writes the team/philosophy summary under `docs/plate/`, applies experience adaptations, does not encode roles.
   - Labels: `Feature`, `area:agent`, `area:product`, `risk:medium`, `status:stub`, `need:refinement`

7. **#1037 — Feature: Health nudges for CI and philosophy discovery**
   - `gh plate health` warns when the test inventory or philosophy summary is missing and points at `setup-ci` / `encode-team`.
   - Labels: `Feature`, `area:product`, `risk:low`, `status:stub`, `need:refinement`

8. **#1038 — Design: Bootstrap and discovery composition**
   - Phase 1 is `gh plate bootstrap` (#633). Phase 2 is health-nudged discovery. Discovery is not folded into the bootstrap session.
   - Output: `docs/plate/design/bootstrap-discovery-composition.md`
   - Labels: `Design`, `area:product`, `area:infra`, `risk:low`, `status:stub`, `need:refinement`

No child issue is opened for role encoding, team-size adaptation, or first-class HITL. Those stay in Vision / later.

---

## Recording status

- Answers above are Andrew's, from the 2026-10-03 reply (pack-QN format).
- Child issues #1031–#1038 exist and are sub-issues of #1008.
- Epic #1008 keeps `status:stub` and `need:refinement`. The scope is now concrete, and the children are still stubs. Process docs clear those labels at `mark_ready`, not when the parent Q&A is answered.
- Question #1009 stays open until PR #1026 merges. The token that opened the children cannot comment on #1009 or edit #1008; the comment and the replacement Epic body are in the PR description.

---

**References:**
- Epic #1008: https://github.com/akasper/plate/issues/1008
- Question #1009: https://github.com/akasper/plate/issues/1009
- Related: #633 (bootstrap), #1017 (shell-first scripts), #1015 (docs namespacing under `docs/plate/`)
- AGENTS.md §Required Work Loop (Research, Design, Feature)
- SPEC.md §Goals (test-first mandatory, 70-90% agent-driven SDLC)
