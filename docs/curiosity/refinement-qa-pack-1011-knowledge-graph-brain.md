# Refinement Q&A Pack: Knowledge Graph Brain (Epic #1010)

**Question Issue:** #1011  
**Parent Epic:** #1010 — Knowledge graph brain  
**Milestone:** Knowledge graph brain  
**Prepared for:** Andrew (solopreneur, prefers slow-paced agent-delegated work)  
**Estimated time:** 15-20 minutes total  

---

## Overview

This pack helps refine Epic #1010 (Knowledge graph brain) by clarifying:
1. **Ontology & from-scratch build** — which artifacts become nodes/edges, PLATE-aware vs generic
2. **Query UX** — how agents search the brain (CLI/MCP surfaces)
3. **Token savings** — measurement baseline, targets, verification
4. **Refresh model** — keeping the graph aligned with GitHub truth
5. **SaaS vs local-first** — productization path and boundary

The answers will shape concrete child issues, define success metrics, and determine whether this Epic ships as core PLATE capability or explores SaaS optionality.

---

## Theme A: Ontology & Graph Construction

### Q1: Node granularity

**Context:** A knowledge graph can represent coarse entities (Epics, files) or fine-grained (functions, fragments, review comments). What granularity serves agent memory best?

**Options:**
- **A. Coarse PLATE process entities (recommended)** — Nodes: Epic, Feature, Question, Task, Release, fragment file, wiki page, docs page. Edges: "Feature belongs to Epic", "fragment addresses Feature". No code-level nodes (functions, classes).
- **B. Hybrid PLATE + code structure** — PLATE process nodes + file/directory nodes + function/class nodes from code analysis.
- **C. Fine-grained everything** — Every issue comment, fragment field, code symbol is a node.

**Rationale:** Coarse is fast to build, cheap to query, aligns with "GitHub preserves truth." Hybrid adds code navigation value but more complexity. Fine-grained risks drowning signal in noise.

**Recommended:** A (coarse) — PLATE-aware brain, not a generic code index. Target is process memory, not IDE autocomplete.

---

### Q2: PLATE-specific ontology depth

**Context:** Should the KG encode PLATE-specific semantics (Epic success criteria, risk labels, autonomy eligibility, ceremony state) or stay generic?

**Options:**
- **A. Deep PLATE ontology (recommended)** — Nodes carry PLATE semantics: Epic.success_criteria, Feature.risk_label, PR.merge_eligibility, Release.track, fragment.semver_impact. Queries: "Which Features block this Epic?", "What's the current release base?", "Human Tasks for Epic X?".
- **B. Shallow generic** — Nodes are just "Issue", "PR", "File" with labels/metadata as string properties. Agents parse meaning themselves.

**Rationale:** Deep ontology unlocks intelligent queries (what-next, PM, autonomy) without re-parsing process rules. Shallow is simpler but duplicates logic in every query.

**Recommended:** A (deep) — the "killer feature" is PLATE-aware intelligence, not another generic repo graph.

---

### Q3: From-scratch build sources

**Context:** Which repo artifacts should feed the initial graph build?

**Check all that apply:**
- ☑ GitHub Issues (title, body, labels, milestone, state, linked PRs)
- ☑ Pull Requests (title, body, labels, linked issues, merge state, review threads)
- ☑ Release fragments (`.agentic/releases/unreleased/*.json`, versioned dirs)
- ☑ `AGENTS.md`, `SPEC.md`, `CURRENT.md`, `.plate` config
- ☑ `docs/plate/design/*.md`, `docs/plate/research/*.md` (per #1015 namespacing)
- ☑ Wiki pages (if `docs/wiki/Goals.md` and sync enabled)
- ☑ Milestones (Epic containers)
- ☐ Code structure (file tree, imports, function signatures)
- ☐ Commit history / git log
- ☐ CI workflow definitions
- ☐ GitHub Actions run history
- ☐ Other: _____________

**Rationale:** Determines build complexity, refresh frequency, and query surface. More sources = richer graph but longer build time.

**Recommended:** First 7 checked (GitHub + PLATE artifacts) — core process memory. Defer code/commit/CI to future if token savings justify complexity.

---

### Q4: Edge semantics

**Context:** What relationships should the graph capture?

**Check all that apply:**
- ☑ Feature → Epic (milestone/parent)
- ☑ PR → Issue (closes, addresses)
- ☑ Fragment → Feature (documents change)
- ☑ Epic → Release (linked via Development sidebar to Next Release)
- ☑ Task → Epic (human blocker)
- ☑ Question → Epic (refinement)
- ☑ Design doc → Epic/Feature (informs)
- ☑ Wiki page → Feature (describes)
- ☐ File → PR (changed in)
- ☐ Function → File (defined in)
- ☐ Issue → Issue (depends on, blocks)
- ☐ Other: _____________

**Rationale:** Edges enable graph traversal ("show me all Features blocking Epic X", "which docs explain this Question"). More edges = more query power but more maintenance.

**Recommended:** First 8 checked — PLATE process relationships only. Defer code-level edges unless use case emerges.

---

## Theme B: Query UX & Agent Integration

### Q5: Primary query interface

**Context:** Agents need to search the brain. What surface should PLATE ship?

**Options:**
- **A. MCP tools only (recommended)** — `plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse`. Agents call from any MCP-enabled host.
- **B. CLI + MCP** — `gh plate kg query "..."` for humans; MCP for agents.
- **C. Hybrid: natural language → structured query** — Agent writes English question; brain translates to graph traversal.

**Rationale:** MCP-only keeps implementation focused; CLI adds human debugging value. Natural language translation is ambitious but may miss.

**Recommended:** B (CLI + MCP) — humans debug, agents use MCP. Natural language can be a future enhancement.

---

### Q6: Query result format

**Context:** When an agent queries the brain, what should it receive?

**Options:**
- **A. Narrow cited subgraph (recommended)** — JSON with entity nodes + edges + GitHub URLs + snippet text. Example: `{"epic": {"number": 1008, "title": "...", "url": "...", "children": [...]}}`. Fits in prompt as compact cited context.
- **B. Full entity dumps** — Return complete issue bodies, PR descriptions, fragment JSON. Agent filters.
- **C. Markdown summaries** — Brain generates prose summary of query result. Example: "Epic #1008 has 3 open Features (links). Success criteria: ..."

**Rationale:** Narrow subgraph optimizes token cost (the goal). Full dumps waste tokens. Markdown summaries risk hiding provenance links.

**Recommended:** A (narrow cited) — agents get compact JSON; can fetch full entities via GitHub API if needed.

---

### Q7: Integration with existing surfaces

**Context:** Should the brain replace or augment existing PLATE surfaces?

**Options:**
- **A. Augment with fallback (recommended)** — `plate_what_next`, `plate_epic_status`, PM orchestrator **optionally** query the brain if available; fall back to live GitHub API if brain is stale/missing. Brain is a cache, not a replacement.
- **B. Replace** — Surfaces always query brain; error if brain unavailable.
- **C. Separate** — Brain is a new standalone tool; existing surfaces unchanged.

**Rationale:** Augment preserves reliability (GitHub is truth). Replace creates hard dependency. Separate misses the opportunity to accelerate existing workflows.

**Recommended:** A (augment) — brain is a smart cache, not a new SOR.

---

### Q8: Query examples (scope check)

**Context:** Which queries should the brain answer well in v1?

**Check all that apply:**
- ☑ "What Features block Epic #1008?"
- ☑ "Which open Issues need refinement?" (label queries)
- ☑ "What is the current release base branch?" (ceremony state)
- ☑ "Human Tasks linked to this Epic?" (Task discovery)
- ☑ "Show me all fragments addressing Feature #123"
- ☑ "What does the Goals page say about X?" (wiki content)
- ☑ "Which PRs are waiting for human review?" (merge state)
- ☐ "What functions call X()?" (code graph, deferred)
- ☐ "Why did this test fail?" (CI log analysis, deferred)
- ☐ "Who authored this Epic?" (provenance, can use GitHub API)

**Rationale:** Determines query API surface and ontology depth. Checked queries = must-have in v1.

**Recommended:** First 7 checked — PLATE process queries only. Defer code/CI/provenance.

---

## Theme C: Token Savings & Verification

### Q9: Baseline for token savings

**Context:** To claim token savings, we need a "before brain" baseline. How should we measure?

**Options:**
- **A. Controlled experiment (recommended)** — Run same task (e.g., "plan Epic #1008") with/without brain; compare prompt token counts. Repeat 10+ times for statistical confidence.
- **B. Production monitoring** — Deploy brain; track average prompt size over time; compare to historical average.
- **C. Synthetic benchmark** — Define 20 standard queries ("what blocks Epic X", "show open Questions"); measure token cost with brain vs naive full-context.

**Rationale:** Controlled experiment is rigorous but slow. Production monitoring is realistic but noisy. Synthetic benchmark is fast but may not reflect real use.

**Recommended:** C first (synthetic benchmark for v1 proof), then A (controlled experiment for production claim). B for ongoing monitoring.

---

### Q10: Token savings target

**Context:** What token reduction would make this Epic "worth it"?

**Options:**
- **A. 30-50% for process-heavy queries (recommended)** — Queries like "what-next", "epic status", "plan epic" save 30-50% vs full AGENTS.md + issue dumps. Ambitious but achievable.
- **B. 10-20% overall** — Modest but reliable; brain is nice-to-have, not transformative.
- **C. 70%+ for all queries** — Moonshot; may not be realistic without perfect caching.

**Rationale:** Sets success bar and prioritization. 30-50% justifies Epic investment. 10-20% is incremental. 70%+ risks under-delivery.

**Recommended:** A (30-50% for process queries) — proves value without overpromising.

---

### Q11: Failure mode handling

**Context:** If the brain is stale (graph not refreshed after recent Issue creation), what should agents do?

**Options:**
- **A. Fallback to GitHub API (recommended)** — Brain returns "stale" flag; agent queries GitHub directly; logs staleness event.
- **B. Return stale data with warning** — Brain says "last updated 2 hours ago"; agent decides.
- **C. Refuse to answer** — Brain errors; agent must refresh before querying.

**Rationale:** Fallback preserves reliability. Warning trades accuracy for speed. Refusal blocks progress.

**Recommended:** A (fallback) — GitHub is truth; brain is a best-effort optimization.

---

## Theme D: Refresh Model & GitHub as SOR

### Q12: Refresh trigger

**Context:** When should the graph rebuild?

**Options:**
- **A. On-demand + periodic (recommended)** — User runs `gh plate kg refresh` manually or on a schedule (e.g., nightly via cron/autonomy procedure). Cheap and predictable.
- **B. Webhook-driven** — GitHub webhook fires on issue/PR events; brain updates incrementally in real-time. Fast but requires server.
- **C. On every query** — Brain checks GitHub API for changes before answering. Always fresh but slow/expensive.

**Rationale:** On-demand + periodic fits local-first, no server. Webhooks enable real-time but require hosting. On-query is naive and defeats caching purpose.

**Recommended:** A (on-demand + periodic) — ship local-first; defer webhooks to SaaS exploration.

---

### Q13: Incremental vs full rebuild

**Context:** After initial from-scratch build, should updates be incremental (patch changed entities) or full rebuild?

**Options:**
- **A. Full rebuild (recommended for v1)** — Simpler; no complex diff logic. Run nightly or on-demand. Fast enough for medium repos (<1000 issues).
- **B. Incremental update** — Track changed entities; update subgraph only. Complex but scalable.

**Rationale:** Full rebuild is easier to reason about and test. Incremental is premature optimization until we prove repos are too large.

**Recommended:** A (full rebuild for v1) — optimize later if needed.

---

## Theme E: SaaS vs Local-First

### Q14: Hosting model for v1

**Context:** Should the brain run locally (repo-local graph file + CLI/MCP) or require a hosted service?

**Options:**
- **A. Local-first only (recommended for v1)** — Graph stored in `.agentic/kg/` (or similar); `gh plate kg refresh` builds locally; MCP queries local graph. No server, no SaaS dependency. Works offline.
- **B. Local + optional hosted** — Local works; hosted service (SaaS) offers faster search, multi-repo, team sharing. Opt-in.
- **C. Hosted-only** — Brain requires PLATE SaaS account. Local-first not supported.

**Rationale:** Local-first aligns with PLATE's "GitHub preserves truth" + no external state. Hosted adds value but delays MVP. Hosted-only risks adoption barrier.

**Recommended:** A (local-first for v1) — prove value without SaaS dependency. Explore SaaS as separate Epic after adoption proof.

---

### Q15: SaaS value proposition (if pursued later)

**Context:** If we build SaaS hosting later, what would justify the complexity?

**Check all that apply:**
- ☑ Multi-repo search (query across all my PLATE projects)
- ☑ Team sharing (shared brain for org, not per-developer rebuild)
- ☑ Real-time refresh (webhooks → instant updates)
- ☑ Advanced analytics (velocity, cost trends, Epic health across repos)
- ☐ Public marketplace (search other orgs' PLATE best practices)
- ☐ Embeddings / semantic search (natural language → graph query)
- ☐ Browser UI (visual graph explorer)
- ☐ Other: _____________

**Rationale:** Determines SaaS scope and whether it's a distinct product or just "hosted version of local KG."

**Recommended:** First 4 checked — team/enterprise value. Defer marketplace/embeddings/UI until demand proven.

---

### Q16: SaaS scope for this Epic

**Context:** Should SaaS exploration be in-scope for Epic #1010, or deferred to a future Epic?

**Options:**
- **A. Out of scope (recommended)** — Ship local-first brain in #1010. Open separate Epic for SaaS if demand emerges.
- **B. Optional spike** — Include one Research child in #1010 to sketch SaaS architecture; no implementation.
- **C. Full SaaS track** — Ship local + hosted in parallel within #1010.

**Rationale:** Out-of-scope keeps Epic focused; SaaS can piggyback on proven local implementation. Spike documents intent. Full track dilutes focus.

**Recommended:** A (out of scope) — mention SaaS in Epic body as future path; prioritize local-first proof.

---

## Proposed Scope (Draft)

Based on the above Q&A, the refined Epic #1010 would include:

### In scope
1. **From-scratch KG build** (coarse PLATE process ontology)
   - Nodes: Epic, Feature, Question, Task, Release, PR, fragment, docs, wiki
   - Edges: belongs-to, closes, documents, links, blocks (PLATE relationships only)
   - Sources: GitHub Issues/PRs + fragments + AGENTS/SPEC/CURRENT + docs/plate/ + wiki + milestones
   - Build: full rebuild (local, on-demand + periodic via autonomy procedure)
   - Storage: `.agentic/kg/graph.json` (or similar repo-local file)

2. **Query surface** (CLI + MCP)
   - CLI: `gh plate kg refresh`, `gh plate kg query "..."`, `gh plate kg get <entity>`
   - MCP: `plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse`
   - Result format: narrow cited JSON subgraphs (optimized for prompt insertion)
   - Query examples: "Features blocking Epic X", "open refinement Questions", "current release base", "Tasks for Epic Y", "fragments for Feature Z"

3. **Integration with existing surfaces** (augment with fallback)
   - `plate_what_next`, `plate_epic_status`, PM orchestrator optionally query brain if available
   - Fallback to GitHub API if brain stale/missing
   - Staleness detection and logging

4. **Token savings verification**
   - Synthetic benchmark: 20 standard process queries (what-next, epic status, plan epic, etc.)
   - Measure token cost with brain vs naive full-context
   - Target: 30-50% reduction for process-heavy queries
   - Controlled experiment (optional): run same task with/without brain; compare prompt tokens

5. **Refresh model**
   - On-demand: `gh plate kg refresh` (manual)
   - Periodic: autonomy procedure (nightly or configurable)
   - Full rebuild (no incremental update in v1)
   - GitHub remains source of record; brain is derived cache

### Explicitly out of scope (non-goals)
- Code-level graph (functions, classes, imports) — defer unless use case emerges
- Real-time webhook-driven refresh — requires server; local-first first
- Incremental graph updates — premature optimization
- SaaS hosting / multi-repo search / team sharing — separate Epic after local proof
- Natural language query translation — future enhancement
- Browser UI / visual graph explorer — defer
- Replacing GitHub as source of record — brain is always a derived cache

---

## Candidate Child Issues (Ordered)

Based on answers, the Epic would decompose into ~7-9 child issues:

1. **Research: PLATE Process Ontology for KG** (#1010.1)
   - Define node types (Epic, Feature, PR, fragment, etc.) + properties
   - Define edge types (belongs-to, closes, documents, etc.)
   - Survey existing property graph / RDF ontologies for inspiration
   - Output: `docs/plate/research/kg-ontology.md`
   - Labels: `Research`, `area:backend`, `area:agent`, `risk:low`

2. **Research: Token Savings Baseline & Measurement Strategy** (#1010.2)
   - Design synthetic benchmark (20 standard queries)
   - Measure naive full-context prompt token cost per query
   - Design controlled experiment protocol (same task, with/without brain)
   - Define success bar (30-50% savings for process queries)
   - Output: `docs/plate/research/kg-token-savings-baseline.md`
   - Labels: `Research`, `area:product`, `area:agent`, `risk:low`

3. **Design: KG Build Pipeline & Storage Model** (#1010.3)
   - Specify build sources (GitHub Issues/PRs + fragments + process docs + wiki)
   - Design full-rebuild algorithm (fetch → parse → graph construction)
   - Design storage format (`.agentic/kg/graph.json` schema)
   - Specify refresh triggers (on-demand CLI + periodic procedure)
   - Output: `docs/plate/design/kg-build-pipeline.md`
   - Labels: `Design`, `area:backend`, `risk:low`

4. **Design: Query API & Result Format** (#1010.4)
   - Specify MCP tools (`plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse`)
   - Specify CLI commands (`gh plate kg refresh`, `gh plate kg query`, etc.)
   - Design narrow cited JSON result format (optimize for prompt insertion)
   - Define staleness detection and fallback logic
   - Output: `docs/plate/design/kg-query-api.md`
   - Labels: `Design`, `area:backend`, `area:agent`, `risk:low`

5. **Feature: KG Build Implementation** (#1010.5)
   - Implement from-scratch build: fetch GitHub data + parse + construct graph per ontology
   - Implement storage to `.agentic/kg/graph.json` (or DB backend)
   - Implement `gh plate kg refresh` CLI
   - Add staleness metadata (last_refresh timestamp)
   - Labels: `Feature`, `area:backend`, `risk:medium`
   - Fragment: describe new KG capability + build command

6. **Feature: KG Query Implementation (MCP + CLI)** (#1010.6)
   - Implement `plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse` MCP tools
   - Implement `gh plate kg query`, `gh plate kg get` CLI
   - Return narrow cited JSON per design
   - Handle staleness: fallback to GitHub API with logging
   - Labels: `Feature`, `area:backend`, `area:agent`, `risk:medium`
   - Fragment: describe MCP query surface

7. **Feature: Integration with plate_what_next & plate_epic_status** (#1010.7)
   - Augment `plate_what_next` to optionally query brain for open PRs, ready issues, Epic state
   - Augment `plate_epic_status` to query brain for child Features, blockers
   - Fallback to GitHub API if brain unavailable/stale
   - Labels: `Feature`, `area:agent`, `area:product`, `risk:medium`

8. **Feature: Periodic Refresh Autonomy Procedure** (#1010.8)
   - Create `.agentic/procedures/kg-refresh-nightly.json` (or similar)
   - Schedule: nightly (or configurable)
   - Risk level: low (read-only refresh)
   - Action: run `gh plate kg refresh`
   - Labels: `Feature`, `area:infra`, `risk:low`

9. **Research: Token Savings Verification & Benchmark Report** (#1010.9)
   - Run synthetic benchmark: 20 queries with brain vs naive context
   - Measure token savings per query
   - Run controlled experiment (optional): same task with/without brain
   - Output: `docs/plate/research/kg-token-savings-report.md` with results
   - Success bar: 30-50% savings for process-heavy queries
   - Labels: `Research`, `area:product`, `risk:low`

**Optional (if SaaS spike is in-scope):**
10. **Research: SaaS KG Hosting Architecture (Optional Spike)** (#1010.10)
    - Sketch multi-repo search, team sharing, webhooks, analytics
    - Estimate complexity, hosting cost, auth requirements
    - Propose SaaS value proposition and pricing model
    - Output: `docs/plate/research/kg-saas-architecture.md`
    - Labels: `Research`, `area:product`, `area:backend`, `risk:low`
    - Note: Implementation deferred to separate Epic

---

## Next Steps (for Andrew)

1. **Answer these 16 questions** (15-20 minutes) — recommended defaults are marked.
2. **Review proposed scope** — adjust in-scope / out-of-scope boundaries, especially SaaS deferral.
3. **Review candidate child issues** — reorder, merge, split, or add as needed.
4. **Approve or refine** — agent will then:
   - Update Epic #1010 body with concrete scope, non-goals, success criteria
   - Create the 7-10 child issues as stubs (labeled, linked to milestone, `need:refinement` removed)
   - Close Question #1011 via Documentation PR with this pack + Epic updates
   - Mark #1010 as `status:ready-to-work` (no longer a stub)

**Estimated total effort to ship:** 6-8 weeks of agent time (3 Research + 2 Design + 4 Features), assuming no blocking dependencies. No calendar time estimate per PLATE doctrine.

---

**References:**
- Epic #1010: https://github.com/akasper/plate/issues/1010
- Question #1011: https://github.com/akasper/plate/issues/1011
- Related: #218 (Information Audit), #224 (Goals page), #660 (PM orchestrator), #470 (AutonomyEngine)
- AGENTS.md §Required Work Loop (Research, Design, Feature)
- SPEC.md §Goals (token savings, observability, high agent autonomy)
- #1015 (docs namespacing under `docs/plate/`)
