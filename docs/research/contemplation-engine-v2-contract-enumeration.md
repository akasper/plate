# Research: Contemplation Engine v2 Contract Enumeration + Gaps vs v1 + answer_signal Options + Phased Core Implementation Recommendations

- **Issue:** #342 (Research child of Epic #257 "Contemplation Engine v2 + Full Contract + Reliable Close Logic")
- **Resolves:** #326 "[Question]: What answer_signal representation should Contemplation Engine v2 evaluate for strict closure?"
- **Researched by:** Claude (Anthropic agent)
- **Date:** 2026-06-05
- **Status:** Complete

## Research Question

For Epic #257 (Contemplation Engine v2) and resolving Question #326: Enumerate the full contract from Design #143 (and `docs/design/contemplation-engine-contract.md`) versus the current v1 minimal implementation in `src/plate_core/contemplation.py` (and integration in `mcp_server.py`, `curiosity_tools.py`, `agent_guidance.py`, `plate.agent.md`). Resolve the open question in #326 on machine-readable `answer_signal` representation. Produce recommendations for the phased v2.1 scope (core engine + close + basic creation first, per interactive planning resolutions on #257). Identify gaps in transcript/provenance, signal eval, child creation, artifact mutation (PR-only), strict close (with citations + USAGE REPORT), revisions, blocking/resumption (#147/#148), tests, and encoding in guidance/catalog.

## Sources

Primary sources reviewed for this research:
- `docs/design/contemplation-engine-contract.md` — Design #143 formal contract (5-step sequence)
- `src/plate_core/contemplation.py` — Current v1 minimal implementation (lines 1-173)
- `src/plate_core/mcp/curiosity_tools.py` — RecordAnswerTool, CreateBlockingQuestionTool integration (lines 1-456)
- `src/plate_core/agent_guidance.py` — QANDA_CURIOSITY_GUIDANCE reusable constant (lines 1-131)
- `plugin/agents/plate.agent.md` — Core agent persona Q&A mode section (lines 1-36)
- `.github/ISSUE_TEMPLATE/question.yml` — Question template with answer_signal field (lines 1-52)
- `AGENTS.md` — Question work loop + USAGE REPORT requirement (lines 91-99, 141-149)
- `docs/design/curiosity-answer-model.md` — Design #142 provenance strategy
- `docs/research/curiosity-qanda-inventory.md` — Research #140 inventory + invariants
- Issue #326 body + answers (closed with recommendation: checklist-style in question.yml + evaluate per #143 contract + enforce in guidance)
- Issue #257 body + Q&A Resolution section + PLATE_SESSION_STATE (planning decisions: phased v2.1 scope)
- SPEC.md § Beta Roadmap (Epic: Contemplation Engine v2 entry, lines 138-139)

## Findings

### 1. Design #143 Contract vs. v1 Implementation — Side-by-Side Mapping

The formal contract from Design #143 (`docs/design/contemplation-engine-contract.md`) specifies a 5-step sequence. Below is the mapping to current v1 code behavior:

| Contract Step (Design #143) | Required Behavior | v1 Implementation Status (`contemplation.py`) | Gap Analysis |
|------------------------------|-------------------|-----------------------------------------------|--------------|
| **1. Full transcript append (non-destructive)** | Post structured comment on Question with: original question verbatim, verbatim user answer, timestamp + session/provenance (agent login, MCP/CLI context, git commit), link to prior revision comment. Use provenance schema from Design #142. | **Partial.** Lines 62-101: Creates `PLATE-CONTEMPLATION` block with timestamp, source, session, answered_by, answer excerpt (180 chars), actions list, close_signal_met flag. Does NOT capture: original question verbatim, full answer (only 180-char excerpt), revision_of links, git commit hash, Design #142 provenance schema fields (question_id, session_id UUID, author with @ prefix, revision_of databaseId). | **Missing:** Full answer text (truncated at 180 chars), original question verbatim, revision_of linking, full Design #142 provenance JSON schema, git commit provenance. |
| **2. Create forward-progress artifacts** | Parse answer against Question's documented `answer_signal`. If gaps/requirements identified: create appropriately labeled child issues (Feature/Research/Design/Question) with `Closes` or reference back. For process-impacting answers: directly prepare updates to AGENTS.md, .agentic/skills.yml, SPEC.md, CURRENT.md, wiki sources, docs/ via atomic PRs (never direct push). Update Epic #139 PLATE_SESSION_STATE. For research/design: commit to docs/research/ or docs/design/. | **Heuristic only.** Lines 73-91: Simple keyword heuristics (`"risk"`, `"unknown"`, `"create"`, `"implement"`, `"add"` in answer text OR len > 80) create a generic `[Feature]: Follow-up from answer to Question #N` issue with 300-char excerpt. No signal parsing from Question body. No typed child creation (always Feature). No artifact mutations (AGENTS.md, fragments, SPEC, wiki, docs). No PLATE_SESSION_STATE updates. No research/design commit logic. | **Missing:** `answer_signal` parsing from Question body. Deterministic child type selection (Feature/Research/Design/Question). Artifact mutation preparation (AGENTS.md, fragments, SPEC, wiki, docs) via PR creation. PLATE_SESSION_STATE updates. Research/design artifact commits. Evidence-based (not keyword-based) forward progress. |
| **3. Revision/re-answer handling** | Always append (never mutate prior comments). Re-evaluate full history + new input; may close stale follow-on issues and/or spawn corrected ones. Preserve full chain for audit. | **Not implemented.** No revision detection. No `revision_of` linking. No re-evaluation of prior answers. No stale issue closure. | **Missing:** Entire revision/correction workflow. Detection of revised answers, `revision_of` links, history replay, stale issue management. |
| **4. Closure decision** | Close Question if and only if `answer_signal` criteria verifiably met by accumulated transcript evidence (agent can cite specific answer excerpts; human confirmation for high-risk). On closure, include required `=== USAGE REPORT ===` block per AGENTS.md. | **Heuristic only.** Lines 93-97: Simple keyword detection (`"done"`, `"complete"`, `"resolved"`, `"shipped"`). Comment says "In real #149 this would fetch Question body and check against its answer_signal". No signal parsing. No citation of excerpts. No USAGE REPORT block emission. | **Missing:** Real signal evaluation from Question body. Criteria verification with citations. USAGE REPORT block (required per AGENTS.md lines 141-149). Human confirmation path for high-risk. Evidence-based (not keyword-based) closure. |
| **5. Persona and guidance updates** | Contract encoded in: AGENTS.md Question handling loop and babysit sections; plugin/agents/plate.agent.md; baseline agent catalog entries for Curiosity/Q&A; plate_plan_epic extensions for Q&A session state. | **Partial.** QANDA_CURIOSITY_GUIDANCE in `agent_guidance.py` (lines 58-122) documents blocking pattern and resumption. `plate.agent.md` (lines 20-26) references MCP tools and native TUI preference. AGENTS.md (lines 91-99) has Question work loop stub. Baseline catalog not yet updated with Contemplation skills. plate_plan_epic (#257 note) defers to "host agent's chat or gh plate qanda". | **Missing:** Explicit contract steps in AGENTS.md Question loop. Baseline catalog entries for run-qanda-session, contemplate-answer, create-blocking-question, resume-from-answered-question skills. Full contract encoding in plate_plan_epic integration. |

**Summary:** v1 is a ~20% implementation of the Design #143 contract. Major gaps: signal parsing, artifact mutations, revision handling, strict evidence-based close with USAGE REPORT, contract encoding in guidance/catalog.

### 2. Full Inventory of `answer_signal` Options (Resolution of #326)

Question #326 asked: "What machine-readable `answer_signal` representation should Contemplation Engine v2 evaluate for strict closure?"

**Prior answers on #326** (referenced in #257 Q&A Resolution + #326 body):
- Recommendation cites `.github/ISSUE_TEMPLATE/question.yml` as checklist-style storage format for `Answer signal`.
- Recommendation cites `docs/design/contemplation-engine-contract.md` and #257 as closure-contract references.
- Recommendation cites `src/plate_core/agent_guidance.py` or `plugin/agents/plate.agent.md` as enforcement surface.
- **Resolution accepted per #257 planning:** checklist-style in question.yml + evaluate per #143 contract + enforce in guidance.

**Current question.yml format** (`.github/ISSUE_TEMPLATE/question.yml` lines 26-32):
```yaml
- type: textarea
  id: answer_signal
  attributes:
    label: Answer signal
    description: How will we know this question is answered?
    placeholder: "A documented recommendation in docs/research/question-agent-packaging.md and follow-up implementation issue(s)."
  validations:
    required: true
```

This is **free-text** in the template, but the placeholder and prior usage suggest structured criteria.

**Options evaluated:**

| Format | Example | Pros | Cons | Parseability | Human Editability | Agent Eval Complexity |
|--------|---------|------|------|--------------|-------------------|----------------------|
| **Checklist (Markdown)** | `- [ ] Recommendation cites X\n- [ ] Artifact committed to Y\n- [ ] Follow-up issues created` | Native GitHub rendering, familiar UX, explicit item-by-item tracking | Requires Markdown parsing, checkbox state not machine-readable from issue body (need comment scan for checked state), ambiguous completion (partial checks?) | Medium (regex for `- [x]` patterns) | High (standard Markdown) | Medium (pattern match + count checked vs total) |
| **YAML block in issue body** | `\`\`\`yaml\nanswer_signal:\n  - condition: "artifact_committed"\n    target: "docs/research/X.md"\n  - condition: "follow_up_created"\n\`\`\`` | Structured, easy to parse, extensible | Requires code block in issue body, less human-friendly for quick edits, not idiomatic GitHub | High (YAML parser) | Medium (code block editing) | Low (direct field access) |
| **JSON in hidden comment** | `<!-- plate-answer-signal {"criteria": [...]} -->` | Machine-first, clean separation from human text | Hidden from humans, poor discoverability/editability, violates "GitHub as UI" principle | High (JSON parser) | Low (hidden HTML comment) | Low (direct field access) |
| **Structured natural language with keywords** | "Answered when: (1) recommendation in docs/research/X.md AND (2) follow-up Feature created" | Human-readable, no special syntax | Requires NLP/LLM for parsing, ambiguous, brittle to phrasing changes, high token cost for eval | Low (needs LLM) | High (natural text) | High (LLM-based inference per answer) |
| **Checklist in question.yml + explicit eval contract** | Markdown checklist in `answer_signal` field + Design #143 contract defines eval: parse body for `- [ ]` items, contemplate checks each item against answer + created artifacts, close only when all checked or verifiable | Balances GitHub-native UX + parseability; explicit contract for eval logic; extensible (can add typed criteria later) | Still requires regex parsing + heuristic/LLM per item; partial ambiguity on what "verifiable" means per item | Medium-High (regex + heuristic or light LLM per item) | High (standard Markdown + familiar checkbox UX) | Medium (structured parse + per-item verification; explicit contract reduces ambiguity) |

**Recommendation (resolves #326):**

Use **Markdown checklist in question.yml `answer_signal` field** + **explicit evaluation contract in Design #143 and Contemplation Engine**.

Rationale:
- **GitHub-native UX:** Markdown checklists are idiomatic, render well, and are familiar to users creating Questions.
- **Balances parseability and human editability:** Agent can regex parse `- [ ]` and `- [x]` patterns; humans can edit inline without special tooling.
- **Explicit contract reduces ambiguity:** The Contemplation Engine's eval logic (defined in Design #143 and implemented in v2) interprets each checkbox item as a verifiable criterion. The engine checks:
  - Artifact existence (e.g., "Artifact committed to `docs/research/X.md`" → check git tree).
  - Issue creation (e.g., "Follow-up Feature created" → scan created_issues in contemplation log or GitHub search).
  - Content presence (e.g., "Recommendation cites Y" → scan answer text for Y reference).
- **Extensible:** Can evolve to typed criteria (e.g., `<!-- plate-signal-type: artifact_committed -->` annotations) in future without breaking existing Questions.
- **Enforcement surface:** Encode the eval logic in `agent_guidance.py` QANDA_CURIOSITY_GUIDANCE, `plate.agent.md`, and baseline catalog entries (e.g., "contemplate-answer" skill).

**Examples of well-formed answer_signal checklists:**

```markdown
## Answer signal

- [ ] Recommendation documented in `docs/research/contemplation-engine-v2-contract-enumeration.md` with side-by-side mapping and gap analysis.
- [ ] Machine-readable `answer_signal` format recommendation provided (resolves #326).
- [ ] Phased v2.1 scope recommendations with file-level handoff to Feature child.
- [ ] Test strategy outline included.
```

```markdown
## Answer signal

- [ ] Analysis of stack options (TypeScript, Go, Python) committed to `docs/research/stack-selection.md`.
- [ ] Decision recorded with rationale and tradeoffs.
- [ ] Follow-up Feature issue created for migration (if stack changes).
```

**Evaluation contract for Contemplation Engine v2:**

On `plate_record_answer` + `plate_contemplate` (or trigger_contemplation):
1. Fetch Question body via GitHub API.
2. Extract `answer_signal` section (Markdown heading `## Answer signal` or similar).
3. Parse Markdown checklist items (regex: `^- \[ \] (.+)$` for unchecked, `^- \[x\] (.+)$` for checked).
4. For each item, evaluate against:
   - Answer text (keyword/pattern match for explicit references).
   - Created artifacts (git tree lookup for file paths mentioned).
   - Created issues (contemplation log `created_issues` or GitHub search for linked issues).
   - Agent actions (contemplation log `actions` list).
5. **Strict close decision:** Close Question if and only if:
   - All checklist items are verifiable as met (either explicitly checked in a revision comment or agent can cite evidence), OR
   - Human explicitly checks all items in a revision comment (append-only).
6. **On close:** Emit `=== USAGE REPORT ===` block per AGENTS.md (lines 141-149).
7. **Citation requirement:** Contemplation log or close comment must cite specific answer excerpts or artifact links proving each criterion met.

**This resolves #326.** The recommendation (checklist-style + #143 contract + guidance enforcement) matches the accepted answer in #326 and #257 planning.

### 3. Gap Analysis: v1 → v2 Contract

Detailed gaps identified from side-by-side mapping (§1) and contract requirements:

#### 3.1 Full Non-Destructive Transcript + Provenance

**Gap:** v1 truncates answer at 180 chars (contemplation.py:70), omits original question verbatim, lacks `revision_of` links, missing git commit hash, doesn't follow Design #142 provenance JSON schema.

**Required for v2:**
- Full answer text (no truncation) in PLATE-CONTEMPLATION block.
- Original question text verbatim (fetch from Question body).
- Design #142 provenance fields: `question_id` (int), `session_id` (UUID or gh run id), `author` (with @ prefix), `source` (qanda-tui|cli|copilot-cli|direct-comment), `revision_of` (prior comment databaseId or null).
- Git commit hash (if answer recorded from local context with git info).
- Timestamp already present (v1: line 49); session already present (v1: line 69).

**Files to touch:** `contemplation.py` (ContemplationEngine.contemplate method, lines 38-162), `curiosity_tools.py` (RecordAnswerTool, lines 174-232).

#### 3.2 Typed Child Creation with Back-References

**Gap:** v1 always creates Feature issues (contemplation.py:76-91), no typed selection (Research/Design/Question), no back-references beyond title mention.

**Required for v2:**
- Parse answer + answer_signal to determine appropriate child type (Feature for implementation, Research for investigation, Design for planning, Question for follow-up info needs).
- Include `Closes #<Question>` or bidirectional reference (`Relates to #<Question>`) in child issue body.
- Link back to parent Epic if Question is Epic-scoped (Epic #139 PLATE_SESSION_STATE updates).
- Contemplation log records child type + number + link.

**Files to touch:** `contemplation.py` (issue creation logic, lines 73-91).

#### 3.3 PR-Based Mutations to Process Artifacts (AGENTS.md / fragments / SPEC / wiki / docs)

**Gap:** v1 has no artifact mutation logic (contemplation.py:118 comment: "Future: direct resource updates").

**Required for v2:**
- Detect process-impacting answers (keywords: "update AGENTS.md", "add skill", "change process", "SPEC update").
- Prepare atomic Documentation PRs (never direct push to main) with proposed changes.
- For `.agentic/releases/unreleased/` fragments: detect new behavior and draft fragment content.
- For AGENTS.md / SPEC.md / wiki sources: draft patch or new section.
- Respect `need:human-review` for high-risk changes (security, auth, public claims).
- Contemplation log records "PR draft prepared for X; human review required" or "Direct artifact commit prepared (low-risk doc update)".

**Phased v2.1 scope (per #257 planning):** Defer full mutation PR creation to v2.2+. In v2.1: log mutation *intent* (e.g., "Answer suggests updating AGENTS.md §Question loop; create follow-up Feature for process update"). Optionally: basic doc commits (research findings to docs/research/) as proof-of-concept.

**Files to touch (v2.2+):** `contemplation.py` (new mutation detection + PR creation via github_client), `github_client.py` (PR creation helpers).

#### 3.4 Strict Evidence-Based Close Only on Verified Signal (Citations Required)

**Gap:** v1 uses keyword heuristics (contemplation.py:93-97), no signal parsing, no citations, no USAGE REPORT block.

**Required for v2:**
- Fetch Question body and parse `answer_signal` section (Markdown checklist per §2).
- Evaluate each criterion against answer text, created artifacts, created issues, agent actions.
- Close only if all criteria verifiable.
- Contemplation log (or close comment) cites specific evidence per criterion (e.g., "Criterion 1: met per answer excerpt 'X' + artifact at docs/research/Y.md").
- Emit `=== USAGE REPORT ===` block with tokens, cost, duration on closure (AGENTS.md lines 141-149).

**Files to touch:** `contemplation.py` (signal parsing + eval logic, lines 93-101; close comment emission), `curiosity_tools.py` (RecordAnswerTool may trigger close via contemplation).

#### 3.5 Append-Only Revisions (`revision_of`)

**Gap:** v1 has no revision handling.

**Required for v2:**
- When user provides a revised/corrected answer, RecordAnswerTool (or manual comment) includes `revision_of` field pointing to prior PLATE-ANSWER comment databaseId.
- Contemplation re-evaluates full history (all PLATE-ANSWER comments on Question, chronological order, with revision links).
- May close stale follow-up issues (e.g., Feature created from original answer but now obsolete due to revision).
- Contemplation log notes "Revision detected; re-evaluated criteria; closed stale issue #X".

**Files to touch:** `curiosity_tools.py` (RecordAnswerTool: add `revision_of` param + field, lines 174-232), `contemplation.py` (history fetch + replay logic).

#### 3.6 Full Blocking Paths + Unblock Reports + Merge Context

**Gap:** v1 has partial blocking support (contemplation.py:120-150), detects `PLATE-BLOCKING-DUMP` marker, posts unblock report, but no structured merge or child creation from blocking answer.

**Required for v2 (harden #147/#148):**
- CreateBlockingQuestionTool already present (curiosity_tools.py:330-444); ensure it follows Design #142 provenance.
- On answer to blocking Question: contemplation detects blocking marker, fetches original issue number, posts unblock report (already in v1), **additionally**: merges key information into original issue body (append new "Unblocked Info" section), updates original issue labels (remove `status:blocked` if present), creates any follow-on issues warranted by unblocking info, records full bidirectional traceability.
- Contemplation log includes "Blocking resumption: merged info into #X, created follow-on #Y, posted unblock report".

**Files to touch:** `contemplation.py` (blocking detection + merge logic, lines 120-150), `curiosity_tools.py` (CreateBlockingQuestionTool: ensure provenance compliance).

#### 3.7 Tests

**Gap:** No dedicated contemplation tests. `tests/test_curiosity_answers.py` exists (imports Answer model from #150/#258) but doesn't cover contemplation contract.

**Required for v2:**
- Unit tests: `tests/test_contemplation.py` covering:
  - Signal parsing (Markdown checklist extraction from Question body).
  - Criterion evaluation (mock answer + artifacts + issues → verdict per criterion).
  - Close decision (all met → close; partial met → stay open).
  - Revision handling (revision_of links, history replay).
  - Blocking detection + unblock report.
  - USAGE REPORT emission.
- Integration tests: Simulate `RecordAnswerTool.execute()` → `trigger_contemplation()` → assert on created issues, contemplation log, close state.
- Dogfood: Answer a real Question in this repo using v2 engine, verify correct artifacts + closure.

**Files to touch:** `tests/test_contemplation.py` (new), `tests/test_curiosity_answers.py` (integration tests), `tests/` fixtures (mock Question bodies with answer_signal checklists).

#### 3.8 Encoding in Guidance and Catalog

**Gap:** Partial (QANDA_CURIOSITY_GUIDANCE exists but lacks v2 contract details; baseline catalog not updated).

**Required for v2:**
- Update `agent_guidance.py` QANDA_CURIOSITY_GUIDANCE (lines 58-122) with:
  - Signal evaluation procedure (checklist parsing + criterion verification).
  - Strict close contract (all criteria met + citations + USAGE REPORT).
  - Revision workflow (append-only, revision_of).
  - Artifact mutation intent (log for v2.1; PR creation for v2.2+).
- Update `plugin/agents/plate.agent.md` (lines 20-26) with v2 contract steps.
- Update `src/plate_core/data/baseline_catalog.yml` with skills:
  - `contemplate-answer`: "Trigger Contemplation Engine v2 on recorded answer; parse signal, evaluate criteria, create issues, log actions, close if verified."
  - `create-blocking-question-on-obstacle`: "Last-resort blocking Question creation per #147."
  - `resume-from-answered-question`: "Merge answered blocking Question info + post unblock report per #148."
- Update AGENTS.md §Required Work Loop / Question (lines 91-99) with v2 contract summary (or reference to agent_guidance.py).

**Files to touch:** `agent_guidance.py`, `plugin/agents/plate.agent.md`, `src/plate_core/data/baseline_catalog.yml`, `AGENTS.md`.

### 4. Recommendations for Phased v2.1 Scope (Core Engine + Close + Basic Creation First)

Per #257 planning resolutions, v2.1 should prioritize **core reliability** over full artifact mutations. Below is the recommended phased scope:

#### Phase v2.1 (this Feature #343): Core Engine + Strict Close + Basic Creation + Tests + Dogfood

**In scope:**
1. **Signal parsing and evaluation:**
   - Parse `answer_signal` section from Question body (Markdown checklist).
   - Evaluate each criterion against answer text, created artifacts (git tree lookups), created issues (contemplation log + GitHub search), agent actions.
   - Strict close decision: close only if all criteria verifiable (with citations).
   - Emit USAGE REPORT block on close (per AGENTS.md).

2. **Improved transcript and provenance:**
   - Full answer text (no truncation).
   - Original question text verbatim.
   - Design #142 provenance fields (question_id, session_id, author, source, revision_of).
   - Git commit hash if available.

3. **Basic typed child creation:**
   - Heuristic or light LLM-based type selection (Feature/Research/Design/Question) from answer content.
   - Back-references in child issue body (`Relates to #<Question>` or `Closes #<Question>`).
   - Contemplation log records type + number.

4. **Revision handling (append-only):**
   - RecordAnswerTool accepts `revision_of` param.
   - Contemplation fetches full history, re-evaluates.
   - Logs revision detection.

5. **Harden blocking/resumption (#147/#148):**
   - Verify CreateBlockingQuestionTool follows Design #142 provenance.
   - On answer to blocking Q: structured merge into original issue body (append "Unblocked Info" section), post unblock report, create follow-on issues if warranted.
   - Full bidirectional traceability.

6. **Tests:**
   - Unit tests: `tests/test_contemplation.py` (signal parse, eval, close, revision, blocking).
   - Integration tests: `tests/test_curiosity_answers.py` (RecordAnswer → contemplate → assert).
   - Dogfood: Answer 1+ real Question in this repo using v2 engine.

7. **Core guidance and catalog updates:**
   - Update `agent_guidance.py` QANDA_CURIOSITY_GUIDANCE with v2 contract (signal eval, strict close, revision, blocking).
   - Update `plugin/agents/plate.agent.md` with v2 steps.
   - Update `baseline_catalog.yml` with contemplate-answer, create-blocking-question, resume-from-answered-question skills.
   - Light AGENTS.md §Question update (or reference to guidance).

8. **Fragment:**
   - `.agentic/releases/unreleased/contemplation-engine-v2-core.json` describing implemented behavior, verification (tests + dogfood), references to #257/#342/#326/#143/#139, guidance updates.

**Out of scope (defer to v2.2+ or separate Features):**
- Full artifact mutation PR creation (AGENTS.md, fragments, SPEC, wiki, docs). In v2.1: log mutation *intent* only (e.g., "Answer suggests process update; create follow-up Feature").
- Complex LLM-based criterion interpretation (keep heuristic + pattern matching for v2.1).
- Deep plate_plan_epic integration for Q&A session state (v1 stub remains; full planning is separate Epic per SPEC).
- Migration/backfill of historical Questions to v2 format (separate Feature).
- GitHub Projects v2 field integration for denormalized answer_status (future scalability).

**Rationale for phasing:**
- **Core first:** Reliable signal-driven close + forward progress (child creation) deliver immediate value and satisfy #139 invariants.
- **Defer complexity:** PR-based mutations are high-risk (need robust review gates); defer until core is solid and dogfooded.
- **Fast feedback loop:** Smaller v2.1 scope → faster landing → dogfood → learn → iterate in v2.2+.
- **Aligns with #257 planning:** User explicitly requested "core (signal, transcript, close reliability, basic creation) for v2.1".

#### Phase v2.2+ (future Features): Full Artifact Mutations + Advanced Capabilities

**Out-of-scope for v2.1, recommend for v2.2+:**
- PR-based mutations to AGENTS.md, `.agentic/releases/unreleased/`, SPEC.md, wiki sources, docs/.
- Advanced LLM-based criterion interpretation (e.g., "recommendation is well-reasoned" → LLM eval).
- Full plate_plan_epic Q&A session state integration.
- Migration/backfill command for historical Questions.
- Projects v2 field integration (answer_status, priority).
- Baseline catalog expansion (more Curiosity skills, delegation patterns).

### 5. Test Strategy Outline

#### 5.1 Unit Tests (`tests/test_contemplation.py`)

**Coverage:**
- **Signal parsing:**
  - Input: Mock Question body with `## Answer signal` checklist (2-5 items).
  - Output: Parsed list of criteria (text, checked state).
  - Edge cases: No answer_signal section, empty checklist, mixed checked/unchecked, malformed Markdown.

- **Criterion evaluation:**
  - Input: Criterion text + mock answer text + mock created artifacts (git tree mock) + mock created issues.
  - Output: Boolean (met/unmet) + citation excerpt.
  - Cases: Artifact mentioned in answer → met; artifact exists in git → met; issue number in log → met; keyword match → met; no evidence → unmet.

- **Close decision:**
  - Input: List of criteria with verdicts (all met, partial met, all unmet).
  - Output: Boolean (should close).
  - Assert: Close only if all met.

- **Revision handling:**
  - Input: Multiple PLATE-ANSWER comments with `revision_of` links.
  - Output: Chronological history, latest effective answer.
  - Assert: Re-evaluation uses latest; stale issue closure logged.

- **Blocking detection:**
  - Input: Question body with `PLATE-BLOCKING-DUMP`, original issue number.
  - Output: Unblock report posted, original issue updated, follow-on issues created.
  - Assert: Bidirectional links, full traceability.

- **USAGE REPORT emission:**
  - Input: Contemplation result with close=True.
  - Output: Contemplation log or close comment includes `=== USAGE REPORT ===` block.
  - Assert: Block format matches AGENTS.md (tokens, cost, duration).

**Mocking strategy:**
- Mock `GhClient` for API calls (issue fetch, comment post, issue creation).
- Mock git tree lookups (file existence checks).
- Fixture: Sample Question bodies (various answer_signal formats, blocking markers, etc.).

#### 5.2 Integration Tests (`tests/test_curiosity_answers.py` or new `tests/integration/test_qanda_flow.py`)

**Coverage:**
- **Full Q&A cycle:**
  - Setup: Create mock Question issue (number, body with answer_signal).
  - Execute: `RecordAnswerTool.execute()` → `trigger_contemplation()`.
  - Assert: PLATE-ANSWER comment posted, PLATE-CONTEMPLATION comment posted, created_issues list non-empty (if criteria warrant), close_signal_met=True if all criteria met.

- **Revision cycle:**
  - Setup: Question with 1 prior PLATE-ANSWER comment.
  - Execute: Record revised answer (with `revision_of`).
  - Assert: New PLATE-ANSWER comment, contemplation re-evaluates, stale issue closed (if mocked).

- **Blocking resumption:**
  - Setup: Blocking Question (with PLATE-BLOCKING-DUMP), original issue.
  - Execute: Record answer to blocking Q → contemplate.
  - Assert: Unblock report on original issue, original issue body updated (mock check), follow-on issues created (if warranted).

**Integration with real GitHub API (optional, slow tests):**
- Use test repo (e.g., `akasper/plate-test-sandbox`).
- Create real Question issue, record real answer, trigger real contemplation.
- Assert on live GitHub state (comments, issues).
- Cleanup after test (close/delete test issues).
- Mark as slow tests (`@pytest.mark.slow`), skip in CI fast path.

#### 5.3 Dogfood Scenarios (Manual Verification + Automated Smoke Tests)

**Scenario 1: Simple Question with checklist answer_signal**
- Create Question: "What is the recommended log level for plate CLI?"
- Answer signal: `- [ ] Recommendation documented in answer.\n- [ ] No follow-up issues needed.`
- Answer: "INFO for production, DEBUG for dev. No changes required."
- Expected: Contemplation evaluates both criteria (keyword match in answer), close_signal_met=True, Question closed with USAGE REPORT.

**Scenario 2: Research Question with artifact criterion**
- Create Question: "Should we use pydantic v1 or v2?"
- Answer signal: `- [ ] Analysis in docs/research/pydantic-version.md\n- [ ] Follow-up migration Feature created if v2 chosen.`
- Answer: "Use v2 for better performance. See research doc. Create migration Feature."
- Expected: Contemplation creates Research child (for doc), creates Feature child (for migration), criteria met after children created, Question closed.

**Scenario 3: Blocking Question answered**
- Original issue: Feature #999 (mock, blocked).
- Blocking Question created via CreateBlockingQuestionTool, references #999.
- Answer to blocking Q: "Use JWT tokens, not sessions."
- Expected: Contemplation posts unblock report on #999, updates #999 body with "Unblocked Info: JWT decision", blocking Question closed.

**Scenario 4: Revised answer**
- Question with prior answer: "Use Python."
- Revised answer (with `revision_of`): "Actually, use TypeScript per SPEC."
- Expected: Contemplation detects revision, re-evaluates, may close stale Python-related Feature, logs revision.

**Automated smoke tests:**
- `tests/e2e/test_contemplation_dogfood.py`: Runs Scenario 1-2 against local mock or test repo, asserts on outcomes.
- CI integration: Run smoke tests in PR CI (fast mocks) and nightly (real GitHub API against test repo).

#### 5.4 Test Maintenance and Coverage Goals

- **Coverage target:** ≥80% line coverage for `contemplation.py`, ≥60% for integration paths.
- **Regression prevention:** All prior v1 tests pass (no regressions in RecordAnswer, ListQuestions, etc.).
- **Test data management:** Fixtures in `tests/fixtures/questions/` (YAML files with sample Question bodies, answers, expected outcomes).
- **CI gates:** Unit tests required for PR merge; integration tests advisory (may be slow).

### 6. Risks, Dependencies, and Integration Notes

#### 6.1 Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Over-mutation of files without human review** | High (accidental corruption of AGENTS.md, SPEC, workflows) | Phase v2.1: log mutation *intent* only, defer PR creation to v2.2+. Always respect `need:human-review` for high-risk changes. |
| **Token cost of full history replay on large Questions** | Medium (cost spike for Questions with 10+ answers) | Cache parsed history per session; only re-parse on new answer. Future: local docs/curiosity/ index for fast lookup. |
| **Ambiguous criterion interpretation** | Medium (false positives/negatives on close decisions) | Use explicit heuristics + pattern matching in v2.1. Defer complex LLM-based interpretation to v2.2+. Always cite evidence; human can override. |
| **Breaking existing v1 callers (RecordAnswerTool, plate_contemplate)** | Medium (regression in Q&A flows) | Maintain backward compat: v1 behavior if no answer_signal in Question body. Add feature flag or version param if needed. |
| **Incomplete Design #142 provenance in existing Questions** | Low (historical data may lack provenance) | Accept graceful degradation: v2 adds full provenance to new answers; old answers parse best-effort. Migration/backfill is separate Feature. |

#### 6.2 Dependencies

| Dependency | Status | Impact on v2.1 |
|------------|--------|----------------|
| **Answer Model (#142/#150/#258)** | Partial (Design #142 exists; Feature #150/#258 in progress per SPEC) | Medium: v2.1 can proceed with GitHub comment parsing; committed index (docs/curiosity/answers-index.json) is optional enhancement. If #258 lands during v2.1 dev, integrate for fast lookups. |
| **Q&A surfaces (#145/#154)** | Complete (RecordAnswerTool, ListQuestionsTool, plate_contemplate MCP exist per curiosity_tools.py) | Low: v2.1 builds on existing tools. No blockers. |
| **Epic #139 invariants** | Complete (defined in docs/research/curiosity-qanda-inventory.md) | Low: v2.1 satisfies invariants (no info loss, findability, revisability, forward progress). |
| **Design #143 contract** | Complete (docs/design/contemplation-engine-contract.md) | None: v2.1 implements this contract. |
| **Baseline catalog format** | Complete (baseline_catalog.yml exists, used by cli.py/mcp_server.py) | None: v2.1 adds skills to existing catalog. |

#### 6.3 Integration Notes

**Integration with #139 invariants:**
- **Never lose info:** Full transcript + provenance (§3.1) + append-only revisions (§3.5) satisfy this.
- **Findability:** GitHub comments + optional committed index (from #258) satisfy this.
- **Revisability:** `revision_of` links + history replay (§3.5) satisfy this.
- **Forward progress:** Typed child creation (§3.2) + artifact mutations (deferred to v2.2+ but intent logged in v2.1) + strict close (§3.4) satisfy this.

**Integration with #282 What Next?:**
- `plate_what_next` (mcp_server.py:63-100) could surface "open Questions with answers pending contemplation" as a recommended action.
- v2.1: No explicit integration required. Future: add "contemplate unevaluated answers" to What Next recommendations.

**Integration with plate_plan_epic (#257 note):**
- Epic planning may seed initial Questions (bootstrap flow).
- v2.1: plate_plan_epic remains stub (mcp_server.py:45-60). Full integration is separate Epic per SPEC.
- Future: plate_plan_epic could invoke `plate_list_questions` + `plate_synthesize_priorities` for Q&A-driven planning.

**Integration with existing guidance (agent_guidance.py, plate.agent.md):**
- v2.1 updates QANDA_CURIOSITY_GUIDANCE (agent_guidance.py:58-122) with v2 contract.
- plate.agent.md (lines 20-26) updated with v2 steps (signal eval, strict close, revision, blocking).
- AGENTS.md §Question (lines 91-99) updated with contract summary or reference to guidance.

**Integration with baseline catalog (baseline_catalog.yml):**
- Add skills: contemplate-answer, create-blocking-question, resume-from-answered-question.
- Agents can delegate to these skills via `plate_delegate_to_agent` (mcp_server.py, baseline_catalog.py).

### 7. Explicit Handoff to Feature Child (#343)

This Research closes with committed artifact (`docs/research/contemplation-engine-v2-contract-enumeration.md`) and explicit handoff to Feature #343 for implementation.

**Build instructions for Feature #343:**

1. **Files to touch (primary implementation):**
   - `src/plate_core/contemplation.py` (ContemplationEngine class, lines 32-162):
     - Update `contemplate()` method: parse answer_signal from Question body, evaluate criteria, emit full transcript + provenance, typed child creation, revision handling, strict close with citations + USAGE REPORT.
   - `src/plate_core/mcp/curiosity_tools.py` (RecordAnswerTool, lines 174-232):
     - Add `revision_of` parameter (optional int, default None).
     - Update PLATE-ANSWER block to include Design #142 provenance fields.
   - `src/plate_core/agent_guidance.py` (QANDA_CURIOSITY_GUIDANCE, lines 58-122):
     - Add v2 contract details (signal eval, strict close, revision, blocking).
   - `plugin/agents/plate.agent.md` (lines 20-26):
     - Update with v2 contract steps.
   - `src/plate_core/data/baseline_catalog.yml`:
     - Add contemplate-answer, create-blocking-question, resume-from-answered-question skills.
   - `AGENTS.md` (§Question, lines 91-99):
     - Add v2 contract summary or reference to agent_guidance.py.

2. **Files to touch (tests):**
   - `tests/test_contemplation.py` (new file):
     - Unit tests per §5.1 (signal parse, eval, close, revision, blocking, USAGE REPORT).
   - `tests/test_curiosity_answers.py` (existing):
     - Add integration tests per §5.2 (RecordAnswer → contemplate → assert).
   - `tests/fixtures/questions/` (new directory):
     - Add sample Question bodies (YAML or Markdown) for test data.

3. **Files to touch (fragment):**
   - `.agentic/releases/unreleased/contemplation-engine-v2-core.json` (new):
     - Schema: `{feature_id, title, summary, behavior_changes, verification_evidence, breaking_changes, migration_notes, related_issues, files_changed}`.
     - Content: Describe v2 signal eval, strict close, revisions, blocking, tests, dogfood. References: #257, #342, #326, #143, #139.

4. **Implementation order (suggested):**
   - Phase 1: Signal parsing (fetch Question body, extract answer_signal, parse Markdown checklist). Unit tests for parsing.
   - Phase 2: Criterion evaluation (keyword/pattern match, artifact lookup, issue lookup). Unit tests for eval.
   - Phase 3: Strict close decision (all criteria met → close; emit USAGE REPORT). Unit tests for close logic.
   - Phase 4: Improved transcript + provenance (full answer, original question, revision_of). Update RecordAnswerTool.
   - Phase 5: Typed child creation (heuristic type selection). Unit tests for child creation.
   - Phase 6: Revision handling (history fetch, re-eval). Unit tests for revision.
   - Phase 7: Harden blocking/resumption (structured merge, follow-on issues). Unit tests for blocking.
   - Phase 8: Integration tests (RecordAnswer → contemplate end-to-end).
   - Phase 9: Dogfood (answer real Question in this repo, verify correct behavior).
   - Phase 10: Guidance + catalog updates (agent_guidance.py, plate.agent.md, baseline_catalog.yml, AGENTS.md).
   - Phase 11: Fragment (`.agentic/releases/unreleased/contemplation-engine-v2-core.json`).
   - Phase 12: PR (Documentation or Feature label, clean title, `Closes #257`, `Closes #326`, `Closes #342`, `Closes #343` in body).

5. **Baseline expectations:**
   - All prior tests pass (no regressions).
   - New tests achieve ≥80% coverage for contemplation.py.
   - At least 1 real Question dogfooded end-to-end with v2 engine.
   - Fragment committed, guidance updated, PR passes CI.

6. **Out of scope for #343 (defer to follow-ups):**
   - Full PR-based artifact mutations (log intent only in v2.1).
   - Advanced LLM-based criterion interpretation.
   - Migration/backfill of historical Questions.
   - Projects v2 field integration.

**This completes the Research handoff.** Feature #343 has explicit build instructions, file-level targets, phased scope, and test expectations.

## Recommendation

This research successfully enumerates the full Contemplation Engine v2 contract from Design #143, maps it against current v1 implementation (with detailed gap analysis), resolves Question #326 on `answer_signal` representation (recommendation: Markdown checklist in question.yml + explicit eval contract in #143 + guidance enforcement), and provides phased v2.1 scope recommendations prioritizing core engine reliability (signal eval, strict close, basic creation, revisions, blocking, tests, dogfood) over full artifact mutations (deferred to v2.2+).

**Next steps per PLATE:**
1. This Research closes with Documentation PR including `Closes #342`, `Closes #326` in body (also updates #257 references as needed).
2. Feature #343 proceeds with implementation per handoff instructions above.
3. Dogfood v2 engine on at least 1 real Question in this repo.
4. Post summary comment on Epic #257 after Feature #343 closes (per human checkpoints).
5. Update PLATE_SESSION_STATE on #257 with child status (Research complete, Feature in progress).

**Resolution of #326:** Accepted recommendation is **Markdown checklist in `.github/ISSUE_TEMPLATE/question.yml` `answer_signal` field**, evaluated per **Design #143 contract** (parse checklist, verify each criterion against answer + artifacts + issues + actions, close only if all met with citations), enforced in **agent_guidance.py QANDA_CURIOSITY_GUIDANCE**, **plugin/agents/plate.agent.md**, and **baseline catalog skills**. This balances GitHub-native UX, parseability, human editability, and explicit eval contract. Examples and detailed evaluation procedure provided in §2.

All findings, gaps, recommendations, test strategy, risks, dependencies, and handoff are documented above per PLATE Research artifact format (docs/research/README.md). This research satisfies Epic #257 and Question #326 requirements.
