# What Next? MCP — Orchestrator Vision, Contract, Live State, and Static Flow Strategy

- **Issue:** #283
- **Related:** Epic #282 (parent), Research #286 (exhaustive flows), Design #284, Feature #285 (v1 impl)
- **Researched by:** Grok (autonomous progress on #282)
- **Date:** 2026-06
- **Status:** Draft recommendations (survey + inventory + recs committed; handoff to Design/Feature/Epic)

## Research Goal

Resolve key decisions and produce recommendation record for plate_what_next MCP (incorporating orchestrator vision from #282 kickoff Q&A). Survey process surface + state signals; recommend contract (name, inputs/outputs, encoding); explicit feed to Design #284 (schemas/tree/integration) and Feature #285 (v1 scope, tests, dogfood); commit artifact per Research rules.

## Research Path / Sources

- Epic #282 body (problem, desired, draft ACs, Q&A resolutions, PLATE_SESSION_STATE, vision quote).
- AGENTS.md (Required Work Loops, Issue Artifact Rules, ceremonies, labels, fragments, autonomous, stubs, escalation, prohibited, autopilot, PR title rules, documentation rules, upstream sync).
- Related research/design: #286 exhaustive (this session's companion artifact), contemplation-engine-v2-contract-enumeration.md, curiosity-answer-model.md (#258), informational-goals-model.md, release-ceremony-refinement.md, qanda-*, plate-plan-epic stubs, task-issue-type model.
- MCP/code: mcp_server.py (_what_next stub + registration + all other tools for composition), mcp/*.py (curiosity, audit, tools), health.py (signals), epics.py (status), release.py/bootstrap (status/init), pr_babysit.py, contemplation.py, curiosity_tools.py, cli.py, agent_guidance.py, baseline_catalog.yml (existing what-next skill), github_client.
- .agentic/ (unreleased fragments incl prior 285-what-next-mcp, process rules, skills), SPEC.md Beta, docs/wiki/Goals.md convention, template_payload.
- Prior comments/audits/test inventories referencing #282 (e.g. test_mcp coverage of what_next, audits noting stubs).

(Primary sources prioritized; batch reads/greps for efficiency; no invention of new process rules.)

## Survey Summary (PLATE Process Surface Area + Current Assets)

**Core Process (from AGENTS Required Work Loop + rules):**
- Every issue has exactly one type label at creation (enforced by workflows/label-check).
- Milestones for Epics/Features/Bugs/Docs PRs (warning gate); exactly one per relevant PR.
- Fragments in .agentic/releases/unreleased/ (or epic-*) for *any* Feature or process/agent/template change PR (required even for Epic/Release refinements); schema-driven (slug, change_type e.g. feature/process, surface, summary, migration_impact, agent_notes, optional breaking/links/guidance); aggregated at cut.
- Sub-issues for Epics (R→D→F order for planning); linked via GitHub sidebar.
- PRs: clean human titles (no prefixes; use native Draft); metadata in labels/body/sidebar/milestones; Closes #N *in body only*; atomic (small, ≤~10 files soft, revertable via squash to main from release-* or epic/*); base determined by gh plate release status (legacy release or release-major/etc per track labels); babysit for feedback (third-party agents like devin); no self-merge unless autonomous+eligible (risk:low, no AGENTS/SPEC/etc changes, feedback-resolution green).
- Ceremonies detailed: Epic-close (children merged, summary comment, epic/* → release PR); Release (standing Next Release issue, track labels/branches, packaging with immediate fresh Next, versioned branch + heavy CI Release PR, finalize with tag/triggers/hard-reset); Q&A/Contemplation (record + contemplate for closure, blocking as last resort with dump + pause, resumption merge); babysit full loop; bootstrap for init; info audit for drift.
- Stubs: intentional (with need:refinement); not ready for impl until refined; agents must not treat as ready.
- Autonomous: .github/AUTONOMOUS_MODE enables limited self-merge for eligible low-risk; pacing (≤5 open PRs unless auto-merge eligible); human checkpoints (Epic summaries, merges, releases).
- Cross: usage reports on agent Feature/Question closes (harvested); PLATE_SESSION_STATE for planning; GitHub as source of truth (artifacts > chat); resource consciousness (targeted/batch tools); escalation via need:* + comments (human for judgment/creds/arch/public claims); prohibited actions listed.
- Documentation: update AGENTS + fragments for process changes; sectional upstream sync with PLATES-CORE markers.

**Current Agent Prompt Assets:**
- agent_guidance.py (sections: QANDA_CURIOSITY_GUIDANCE with record/contemplate/blocking/resume + what_next mentions in audits; INFORMATION_AUDIT; PLAYWRIGHT; etc.; get_agent_guidance_sections()).
- baseline_catalog.yml (skills incl "what-next-plate-process" with inputs state via health/epic/release/labels, outputs next_action+prompt_segment+rationale; examples for bootstrap/Epic child/release/babysit; also github-discussions for orchestration comms; owning agents like research-agent).
- plate.agent.md / plugin agents (referenced; focus on health/epic/features/delegation + native Q&A/curiosity; babysit deprecated to local gh plate pr babysit).
- mcp tools exposed for composition (health, epics/status, features, release_*, curiosity full suite, contemplate, babysit/resolve, plan_epic stub, what_next, audits, discussions, delegate, migrate, etc.).

**Live State Signals (queryable, cheap to add):**
- From health.py/get_health: label_coverage_ok + missing, branch_protection, open_epic_count (search label:Epic), goals_page_present (docs/wiki/Goals.md), open_question_count, plate_config_* (present/valid/version/upgrade/extensions), curiosity_answers_present (answers.yml/json), binary_artifacts_tracked, errors (resilience).
- From epics.py/get_epic_status: per-Epic open/closed children, summaries (can enrich with Project v2).
- From release.py / cli / bootstrap: release status (release_branch_exists, open_release_issues, active_next_release, linked_epics, on_hold_epics, release_track_summary, pending_fragments count+slugs, extension_release_checks, versions); init/repair for standing state; cut logic (fragments, semver).
- GitHub direct (via client/search/GraphQL): issue labels/milestones/state/children/closing refs/timeline (CONNECTED_EVENT for linked), PR mergeStateStatus (for babysit), branches existence/protection, contents (for .plate, wiki/Goals, .agentic files, markers), search for specific (e.g. need:refinement + Epic).
- Local/clone: .agentic/releases/unreleased/ (count, parse for pending process changes), .agentic/releases/* (history), .plate/ (config), docs/wiki/Goals.md, markers (PLATE-* comments), git (tags, status, ls-files for binaries), PLATE_SESSION_STATE (in issue bodies/comments for planning phase/children/turn).
- Curiosity/Contemplation: answers index presence + count (via answers.yml or get_answers), open Questions with/without answer_signal.
- MCP derived: plate_features, plate_epic_status, release reports, curiosity list/synthesize/get, etc. (can compose inside what_next for freshness).
- Other: .github/AUTONOMOUS_MODE presence, PLATE_PR_FEEDBACK_AGENTS var, session hints in config.

(Prefer live queries inside MCP for freshness + small caller payloads; accept config/context hints (repo, issue/epic ref, task_type, prior_state, extra).)

## Recommendations (for Design #284 + Feature #285 + Epic #282)

**Tool name/family:** plate_what_next (per Q&A resolutions + catalog consistency with plate_* pattern; supporting internals like plate_get_role_prompt or _what_next if needed; not plate_next_step_for unless justified).

**State query strategy:** Live queries inside impl (health for labels/epics/goals/questions/curiosity/plate_config; epic_status for children/milestones; release_status for fragments/Next Release/tracks; direct GitHub for labels/children/linked/PR state; local FS for .agentic/unreleased/.plate/markers/Goals/wiki if cloned; compose curiosity for Questions). Accept minimal config from caller (repo/issue/task_type/prior_state/hints). Small payloads. Snapshot returned for transparency. Graceful on incomplete (fallback + note).

**Output shape (per Epic desired + Q&A):** dict with:
- status (e.g. "ok", "incomplete_state", "error")
- next: { instructions: str (templated PLATE-augmented prompt segment or action list — concat to base_role_prompt from catalog/agent), steps: array (concrete actions), artifacts: array (required e.g. "tests + fragment + PR"), refs: array (AGENTS.md sections, SPEC, designs, issues), done: bool (or branches for user decisions) }
- snapshot: {...} (the state used, e.g. health/epics/fragments summary)
- error?: str (if any)
- rationale: str (brief + citations)
Caller (orchestrator/plate agent/plate_plan_epic) renders/presents; supports native ask_user_question for surfaced interactive decisions. Incremental "what next?" for running agents (structured MCP call with current task state).

**Encoding of the "chart" for v1:** Static code (Python decision tree / tables / ruleset in mcp_server.py or dedicated mcp/what_next.py; clear, inspectable, versioned with AGENTS.md in git; testable with unit + golden-path examples per ACs). High-fidelity on *existing* documented process (surface AGENTS/SPEC exactly; do not invent). Use references + citations rather than duplicating full text (to ease drift maintenance). Structure by role x phase/state (e.g. implementer + open Feature child with no tests → "add/update tests first per AGENTS Feature step 3", with prompt_snippet, required artifacts, refs). Cover primary flows per Epic (Epic planning, Feature/Bug loop, Research/Design closure, PR babysit, Release cut, Q&A/contemplation) + cross (labels/fragments at right times, ceremonies). Full "entire PLATE" ambitious — phase v1 (high-value first per this + #286 inventory); note gaps. Future: data-driven (e.g. .plate/process-flow.yml or wiki-sourced with validator/linter) after v1 proves value + drift guards.

**Orchestrator vs direct use (per vision + Q&A):** Primary mental model = orchestrator (queue of tasks; feed (agent_type e.g. "implementer"|"planner"|"researcher", config={repo, issue/epic ref?, task_type, prior_state, extra}) to MCP; receives full templatized prompt = base from catalog + PLATE snippet; spawns specialized agent; handles "OK, what now?" callbacks as structured MCP). Supports direct agent use (self-guidance before/while tasks to reduce re-teaching). Both benefit from same primitive. Examples in catalog/guidance (orchestrator: "spawn implementer for Feature on #N"; direct: "call what_next for my next step").

**Integration points:** 
- plate_plan_epic (#256): complementary; what_next as subroutine for dialogue turns or to emit instructions during planning.
- agent_guidance.py + plate.agent.md + baseline_catalog (inject/reduce repeated full-process; add/extend sections + skill examples for orchestrator spin-up + direct).
- Curiosity/contemplation (#139/#258): surface open Questions/answers pending in next if relevant.
- Health/epics/features/release/bootstrap (live state).
- Contemplation engine, github_client (mutations only via explicit tools).
- Existing Q&A surfaces.

**Drift guards:** Comments in code linking sections of AGENTS.md/SPEC/designs; tests that enumerate/assert coverage of key flows from #286 inventory (golden paths); on process change (fragments required), update both encoded logic + sources (with review). Later: generated-from or linter. No drift between what_next and docs.

**v1 scope / prioritization (for Feature #285):** High-fidelity static on primary (Epic/Feature/Bug work loops + labels/fragments/PR rules; Research/Design closure; PR babysit; Release status/cut/fundamentals; Q&A/contemplation hooks; bootstrap/health entry; graceful for others). Deliver "entire PLATE as exists today" to max achievable in static without bloat. Defer full edges/CLI (per planning: v1 MCP-only; thin gh plate if data warrants later). Dogfood on #282 + at least one other (e.g. during beta work). Tests in test_mcp.py (or new) + manual.

**Other recs from Q&A (recorded in parent #282):**
- Tool queries live + accepts hints (small payloads).
- Output supports ask_user_question for branches.
- v1 static (hardcoded tree/tables; inspectable/reviewable/versioned); future data-driven.
- CLI deferred (document MCP prominently in guidance).
- Children labeled with need:refinement + Epic: what-next-mcp + beta-roadmap + areas + milestone.

**Handoff:**
- To Design #284: Use this + #286 inventory for exact schemas (input: agent_type/role + config object; output as above), decision tree spec (role x phase/state → ... traceable to AGENTS), integration diagrams/sequences (orchestrator vs direct; with plan_epic), drift guards details, build instructions for Feature (files, tests, fragment). Define any helpers.
- To Feature #285: v1 coverage scope (primary flows first); dogfood plan (use on #282 children or sibling beta); tests (logic + golden + MCP integration); guidance/catalog updates; fragment (agent surface/process); note future evolution.
- To Epic #282: Update ACs (make testable per this), session state (progress on children), body if needed. After Research/Design close + Feature (already closed), Epic summary comment + close ceremony.

**Risks / Open (align with Epic):**
- Process drift (mitigated by guards + primary-source fidelity + tests).
- Over-constraining (graceful fallbacks; "prompt to continue" vs pure structured; support user ask_user_question).
- Scope/cost of static (phase; prioritize high-value; refs not full paste).
- Input state (live preferred; minimal vs rich — this recs balanced).
- Exact encoding (to Design).
- No GitHub mutations in core what_next (guidance only; delegate to explicit tools).

This Research artifact + companion #286 exhaustive provide the foundation. Commit, coordinate with siblings, update parent #282, prepare Doc PR(s) with Closes #283 (ref #282), post summary comment + usage report on #283 before close. (See #286 for full enumerated flows to encode.)

(Produced autonomously from primary sources + Epic Q&A; ready for refinement via user input / Design child.)