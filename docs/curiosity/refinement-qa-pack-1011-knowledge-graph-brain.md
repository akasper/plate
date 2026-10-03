# Refinement Q&A Pack: Knowledge Graph Brain (Epic #1010)

**Question Issue:** #1011  
**Parent Epic:** #1010 — Knowledge graph brain  
**Milestone:** Knowledge graph brain  
**Prepared for:** Andrew (solopreneur, prefers slow-paced agent-delegated work)  
**Status:** Answered by Andrew on 2026-10-03. Recorded on PR #1026. Question #1011 stays open until that PR merges.

---

## Overview

Andrew answered all 16 questions. Epic #1010 ships a local-first knowledge graph for PLATE process memory.

- Coarse nodes, deep PLATE ontology. Sources are Issues, PRs (including review threads), Milestones, release fragments, AGENTS/SPEC/CURRENT/`.plate`, `docs/plate/` design and research, and wiki pages. Not code, commits, or CI.
- Edges include Issue→Issue depends-on/blocks. No file or function edges.
- CLI and MCP return a narrow cited subgraph. Existing surfaces augment the graph and fall back to the GitHub API.
- v1 answers seven process queries. Token target is 30–50% on process-heavy queries, measured synthetic-first, then a controlled experiment, then ongoing monitoring.
- Refresh is on-demand plus periodic, full rebuild, local-first. SaaS is out of scope, including the later browser UI.

Docs for this Epic live under `docs/plate/` (#1015). This pack does not change `.plate`.

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

**Answer (Andrew):** A. Coarse PLATE entities.

---

### Q2: PLATE-specific ontology depth

**Context:** Should the KG encode PLATE-specific semantics (Epic success criteria, risk labels, autonomy eligibility, ceremony state) or stay generic?

**Options:**
- **A. Deep PLATE ontology (recommended)** — Nodes carry PLATE semantics: Epic.success_criteria, Feature.risk_label, PR.merge_eligibility, Release.track, fragment.semver_impact. Queries: "Which Features block this Epic?", "What's the current release base?", "Human Tasks for Epic X?".
- **B. Shallow generic** — Nodes are just "Issue", "PR", "File" with labels/metadata as string properties. Agents parse meaning themselves.

**Rationale:** Deep ontology unlocks intelligent queries (what-next, PM, autonomy) without re-parsing process rules. Shallow is simpler but duplicates logic in every query.

**Recommended:** A (deep) — the "killer feature" is PLATE-aware intelligence, not another generic repo graph.

**Answer (Andrew):** A. Deep PLATE ontology.

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

**Answer (Andrew):** Issues, PRs (including review threads), Milestones, release fragments, AGENTS/SPEC/CURRENT/`.plate`, `docs/plate/` design and research, wiki pages. Not code, commits, or CI.

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
- ☑ Issue → Issue (depends on, blocks)
- ☐ Other: _____________

**Rationale:** Edges enable graph traversal ("show me all Features blocking Epic X", "which docs explain this Question"). More edges = more query power but more maintenance.

**Recommended:** First 8 checked — PLATE process relationships only. Defer code-level edges unless use case emerges.

**Answer (Andrew):** Feature/Task/Question→Epic; PR→Issue; Fragment→Feature; Epic→Release; Design doc→Epic/Feature; Wiki→Feature; plus Issue→Issue (depends on / blocks). Not file or function code edges. The depends-on/blocks edge is in v1 scope.

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

**Answer (Andrew):** B. CLI + MCP.

---

### Q6: Query result format

**Context:** When an agent queries the brain, what should it receive?

**Options:**
- **A. Narrow cited subgraph (recommended)** — JSON with entity nodes + edges + GitHub URLs + snippet text. Example: `{"epic": {"number": 1008, "title": "...", "url": "...", "children": [...]}}`. Fits in prompt as compact cited context.
- **B. Full entity dumps** — Return complete issue bodies, PR descriptions, fragment JSON. Agent filters.
- **C. Markdown summaries** — Brain generates prose summary of query result. Example: "Epic #1008 has 3 open Features (links). Success criteria: ..."

**Rationale:** Narrow subgraph optimizes token cost (the goal). Full dumps waste tokens. Markdown summaries risk hiding provenance links.

**Recommended:** A (narrow cited) — agents get compact JSON; can fetch full entities via GitHub API if needed.

**Answer (Andrew):** A. Narrow cited subgraph.

---

### Q7: Integration with existing surfaces

**Context:** Should the brain replace or augment existing PLATE surfaces?

**Options:**
- **A. Augment with fallback (recommended)** — `plate_what_next`, `plate_epic_status`, PM orchestrator **optionally** query the brain if available; fall back to live GitHub API if brain is stale/missing. Brain is a cache, not a replacement.
- **B. Replace** — Surfaces always query brain; error if brain unavailable.
- **C. Separate** — Brain is a new standalone tool; existing surfaces unchanged.

**Rationale:** Augment preserves reliability (GitHub is truth). Replace creates hard dependency. Separate misses the opportunity to accelerate existing workflows.

**Recommended:** A (augment) — brain is a smart cache, not a new SOR.

**Answer (Andrew):** A. Augment with fallback.

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

**Answer (Andrew):** All 7 process queries: blocking Features, refinement Issues, release base branch, human Tasks per Epic, fragments per Feature, wiki/Goals lookup, PRs awaiting human review. Code, CI, and provenance queries stay deferred.

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

**Answer (Andrew):** C. Synthetic benchmark first, then A. Controlled experiment. B. Monitoring is ongoing.

---

### Q10: Token savings target

**Context:** What token reduction would make this Epic "worth it"?

**Options:**
- **A. 30-50% for process-heavy queries (recommended)** — Queries like "what-next", "epic status", "plan epic" save 30-50% vs full AGENTS.md + issue dumps. Ambitious but achievable.
- **B. 10-20% overall** — Modest but reliable; brain is nice-to-have, not transformative.
- **C. 70%+ for all queries** — Moonshot; may not be realistic without perfect caching.

**Rationale:** Sets success bar and prioritization. 30-50% justifies Epic investment. 10-20% is incremental. 70%+ risks under-delivery.

**Recommended:** A (30-50% for process queries) — proves value without overpromising.

**Answer (Andrew):** A. 30–50% for process-heavy queries.

---

### Q11: Failure mode handling

**Context:** If the brain is stale (graph not refreshed after recent Issue creation), what should agents do?

**Options:**
- **A. Fallback to GitHub API (recommended)** — Brain returns "stale" flag; agent queries GitHub directly; logs staleness event.
- **B. Return stale data with warning** — Brain says "last updated 2 hours ago"; agent decides.
- **C. Refuse to answer** — Brain errors; agent must refresh before querying.

**Rationale:** Fallback preserves reliability. Warning trades accuracy for speed. Refusal blocks progress.

**Recommended:** A (fallback) — GitHub is truth; brain is a best-effort optimization.

**Answer (Andrew):** A. Fallback to the GitHub API.

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

**Answer (Andrew):** A. On-demand + periodic.

---

### Q13: Incremental vs full rebuild

**Context:** After initial from-scratch build, should updates be incremental (patch changed entities) or full rebuild?

**Options:**
- **A. Full rebuild (recommended for v1)** — Simpler; no complex diff logic. Run nightly or on-demand. Fast enough for medium repos (<1000 issues).
- **B. Incremental update** — Track changed entities; update subgraph only. Complex but scalable.

**Rationale:** Full rebuild is easier to reason about and test. Incremental is premature optimization until we prove repos are too large.

**Recommended:** A (full rebuild for v1) — optimize later if needed.

**Answer (Andrew):** A. Full rebuild for v1.

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

**Answer (Andrew):** A. Local-first only for v1.

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
- ☑ Browser UI (visual graph explorer)
- ☐ Other: _____________

**Rationale:** Determines SaaS scope and whether it's a distinct product or just "hosted version of local KG."

**Recommended:** First 4 checked — team/enterprise value. Defer marketplace/embeddings/UI until demand proven.

**Answer (Andrew):** Multi-repo search, team sharing, webhooks for real-time refresh, advanced analytics, plus a browser UI / visual graph explorer. Not embeddings. These are the later value proposition only. Q16 keeps them out of this Epic.

---

### Q16: SaaS scope for this Epic

**Context:** Should SaaS exploration be in-scope for Epic #1010, or deferred to a future Epic?

**Options:**
- **A. Out of scope (recommended)** — Ship local-first brain in #1010. Open separate Epic for SaaS if demand emerges.
- **B. Optional spike** — Include one Research child in #1010 to sketch SaaS architecture; no implementation.
- **C. Full SaaS track** — Ship local + hosted in parallel within #1010.

**Rationale:** Out-of-scope keeps Epic focused; SaaS can piggyback on proven local implementation. Spike documents intent. Full track dilutes focus.

**Recommended:** A (out of scope) — mention SaaS in Epic body as future path; prioritize local-first proof.

**Answer (Andrew):** A. Out of scope. No SaaS spike in this Epic.

---

## Proposed Scope

Launch scope for Epic #1010, from Andrew's answers. SaaS is not part of this Epic.

### In scope
1. **From-scratch knowledge graph** (coarse nodes, deep PLATE ontology)
   - Nodes: Epic, Feature, Question, Task, Release, PR (including review threads), fragment, design/research doc, wiki page, milestone.
   - Deep PLATE properties (success criteria, risk, release track, fragment semver impact, and similar process fields).
   - Edges: Feature, Task, and Question → Epic; PR → Issue; fragment → Feature; Epic → Release; design doc → Epic or Feature; wiki page → Feature; **Issue → Issue (depends-on / blocks)**.
   - No file or function edges.
   - Sources: GitHub Issues; Pull Requests including review threads; Milestones; release fragments; `AGENTS.md`, `SPEC.md`, `CURRENT.md`, `.plate`; `docs/plate/` design and research; wiki pages.
   - Not sources: code structure, commits, CI workflow files, Actions run history.
   - Build: local-first full rebuild. Storage under `.agentic/kg/` (working file `graph.json`).
   - Refresh: on-demand (`gh plate kg refresh`) plus a periodic autonomy procedure. Not webhooks, and not refresh-on-every-query.

2. **Query surface** (CLI + MCP)
   - CLI: `gh plate kg refresh`, `gh plate kg query`, `gh plate kg get`.
   - MCP: `plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse`.
   - Result format: narrow cited JSON subgraph (nodes, edges, GitHub URLs, short snippets).
   - v1 query set:
     1. Which Features block an Epic?
     2. Which open Issues need refinement?
     3. What is the current release base branch?
     4. Which human Tasks belong to an Epic?
     5. Which fragments address a Feature?
     6. What does the wiki/Goals page say about a topic?
     7. Which PRs are awaiting human review?

3. **Augment existing surfaces, with fallback**
   - `plate_what_next`, `plate_epic_status`, and the PM orchestrator may read the graph when it is fresh.
   - If the graph is missing or stale, they fall back to the GitHub API and log the fallback.
   - GitHub stays the source of record. The graph is a derived cache.

4. **Token savings**
   - Target: **30–50%** fewer tokens on process-heavy queries versus naive full context.
   - Measurement order: synthetic benchmark first, then a controlled experiment (same task with and without the graph), then ongoing monitoring.

### Success criteria
- [ ] A local full rebuild produces the coarse, deep PLATE graph from the sources above, including Issue→Issue depends-on/blocks, and excludes code, commits, and CI
- [ ] CLI and MCP return a narrow cited subgraph for all seven v1 queries
- [ ] `plate_what_next` and `plate_epic_status` use a fresh graph and fall back to the GitHub API when the graph is missing or stale
- [ ] Refresh is on-demand and periodic, and each refresh is a full rebuild
- [ ] A synthetic benchmark, then a controlled experiment, then a monitoring note, are published against the 30–50% process-query bar
- [ ] No SaaS, webhook, browser UI, or embedding work lands in this Epic

### Explicitly out of scope (non-goals)
- Code, commit, and CI nodes, and file/function edges
- Code-call, CI-log, and provenance queries
- Incremental updates and refresh-on-every-query
- Real-time webhook refresh
- Natural-language query translation
- Embeddings / semantic search
- Replacing GitHub as the source of record
- SaaS, including every item in Vision / later

### Vision / later (not this Epic)
Q16 keeps a hosted product out of #1010. If a later Epic pursues it, the value proposition Andrew named is:

- Multi-repo search
- Team sharing
- Webhooks for real-time refresh
- Advanced analytics
- Browser UI / visual graph explorer

Embeddings are not part of that later list.

---

## Candidate Child Issues (Ordered)

Nine stubs, created and linked as sub-issues of #1010. The optional SaaS research spike is dropped (Q16). Each child should carry `status:stub` and `need:refinement` until its own refinement. Milestone for every child: **Knowledge graph brain**.

The integration token created these issues and linked them, and could not add labels or the milestone. Apply the labels below if they are missing.

1. **#1039 — Research: PLATE process ontology for the knowledge graph**
   - Coarse node types, deep PLATE properties, and the edge set including Issue→Issue depends-on/blocks. Excludes code edges.
   - Output: `docs/plate/research/kg-ontology.md`
   - Labels: `Research`, `area:backend`, `area:agent`, `risk:low`, `status:stub`, `need:refinement`

2. **#1040 — Research: Token savings baseline and measurement strategy**
   - Synthetic benchmark first, then controlled-experiment protocol, then the ongoing monitoring signal. Success bar 30–50% on process-heavy queries. The seven v1 queries are the benchmark core.
   - Output: `docs/plate/research/kg-token-savings-baseline.md`
   - Labels: `Research`, `area:product`, `area:agent`, `risk:low`, `status:stub`, `need:refinement`

3. **#1041 — Design: Knowledge graph build pipeline and storage model**
   - Local full rebuild from the agreed sources, `.agentic/kg/` schema, staleness timestamp, on-demand plus periodic triggers. No webhooks.
   - Output: `docs/plate/design/kg-build-pipeline.md`
   - Labels: `Design`, `area:backend`, `risk:low`, `status:stub`, `need:refinement`

4. **#1042 — Design: Knowledge graph query API and result format**
   - CLI and MCP operations, narrow cited JSON, a traversal for each of the seven queries, GitHub API fallback when stale.
   - Output: `docs/plate/design/kg-query-api.md`
   - Labels: `Design`, `area:backend`, `area:agent`, `risk:low`, `status:stub`, `need:refinement`

5. **#1043 — Feature: Knowledge graph build and refresh**
   - `gh plate kg refresh` writes the local graph, including depends-on/blocks, and does not ingest code, commits, or CI.
   - Labels: `Feature`, `area:backend`, `risk:medium`, `status:stub`, `need:refinement`

6. **#1044 — Feature: Knowledge graph query CLI and MCP**
   - `gh plate kg query` / `gh plate kg get` and `plate_kg_query`, `plate_kg_get_entity`, `plate_kg_traverse`. Narrow cited results. Fallback to the GitHub API.
   - Labels: `Feature`, `area:backend`, `area:agent`, `risk:medium`, `status:stub`, `need:refinement`

7. **#1045 — Feature: Augment what-next and epic status with the knowledge graph**
   - Optional graph reads on `plate_what_next` and `plate_epic_status`, with the same GitHub API fallback.
   - Labels: `Feature`, `area:agent`, `area:product`, `risk:medium`, `status:stub`, `need:refinement`

8. **#1046 — Feature: Periodic knowledge graph refresh procedure**
   - `.agentic/procedures/` entry that runs the same full rebuild. Not a webhook listener.
   - Labels: `Feature`, `area:infra`, `risk:low`, `status:stub`, `need:refinement`

9. **#1047 — Research: Token savings verification and benchmark report**
   - Run synthetic first, then the controlled experiment, and describe monitoring. Report against the 30–50% bar.
   - Output: `docs/plate/research/kg-token-savings-report.md`
   - Labels: `Research`, `area:product`, `risk:low`, `status:stub`, `need:refinement`

---

## Recording status

- Answers above are Andrew's, from the 2026-10-03 reply (pack-QN format). This pack has 16 questions; Q8 in the #1009 pack is unrelated.
- Child issues #1039–#1047 exist and are sub-issues of #1010. No SaaS spike issue was opened.
- Epic #1010 keeps `status:stub` and `need:refinement`. The scope is now concrete, and the children are still stubs. Process docs clear those labels at `mark_ready`, not when the parent Q&A is answered.
- Question #1011 stays open until PR #1026 merges. The token that opened the children cannot comment on #1011 or edit #1010; the comment and the replacement Epic body are in the PR description.

---

**References:**
- Epic #1010: https://github.com/akasper/plate/issues/1010
- Question #1011: https://github.com/akasper/plate/issues/1011
- Related: #218 (Information Audit), #224 (Goals page), #660 (PM orchestrator), #470 (AutonomyEngine)
- AGENTS.md §Required Work Loop (Research, Design, Feature)
- SPEC.md §Goals (token savings, observability, high agent autonomy)
- #1015 (docs namespacing under `docs/plate/`)
