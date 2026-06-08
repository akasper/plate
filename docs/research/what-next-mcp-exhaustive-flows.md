# What Next? MCP — Exhaustive Flows Enumeration

- **Issue:** #286
- **Related:** Epic #282, Research #283, Design #284, Feature #285
- **Researched by:** Grok (autonomous progress on #282)
- **Date:** 2026-06 (updated from initial seed)
- **Status:** In progress (initial survey + inventory committed; refinements via further reads)

## Research Goal

Exhaustively enumerate every flow, ceremony, decision point, required artifact, label/state transition, agent role, and MCP/tool sequencing that `plate_what_next` must recognize to deliver the full current PLATE process (per AGENTS.md, .agentic/ files, SPEC, code) without requiring full re-ingestion or drift. Primary artifact for v1 static encoding in the MCP (and handoff to siblings).

## Research Path / Sources Surveyed

- AGENTS.md (full: Authority, Autopilot doctrine, Required Work Loop tables for all types, Issue Artifact Rules, Stub rules, Autonomous Mode, Label Rules, Documentation Rules, CLI body patterns, upstream sync, Wiki Sync, Escalation, Prohibited).
- .agentic/releases/unreleased/README.md (fragment contract, when required for process/agent surfaces).
- .agentic/process.yml and skills (cross-ref in code/docs).
- SPEC.md Beta section (referenced in Epic).
- Existing research/designs: contemplation-engine-v2-contract-enumeration.md, curiosity-answer-model.md, informational-goals-model.md, release-ceremony-refinement.md, plate-plan-epic related, qanda-*, task-issue-type-and-linking-model.md, etc.
- MCP implementation: mcp_server.py (all tools: health, epics, features, release_*, plan_epic stub, what_next, contemplate, curiosity_tools, babysit, etc.), mcp/*.py (curiosity, audit, tools), pr_babysit.py, contemplation.py, health.py, epics.py, release.py, bootstrap.py, cli.py, agent_guidance.py, baseline_catalog.yml.
- GitHub client patterns, markers, .plate/config, docs/wiki/Goals.md convention.
- Prior fragments in v0.2.0/ (incl 285-what-next-mcp.json) and unreleased.
- Test files and audits for usage patterns (test_mcp.py, test-coverage-audit, etc.).

(Full greps/reads performed; see code comments and prior sessions for traces. Focused on primary sources to avoid drift.)

## Categorized Inventory of Flows, Ceremonies, States, Roles, Artifacts, Signals

### 1. Issue Type Work Loops (AGENTS Required Work Loop)
- **Feature** (8 steps): Confirm label+milestone; identify ACs/tests/docs/risk; add/update tests alongside; smallest coherent change; fragment in .agentic/releases/unreleased/ (for process); correct base via `gh plate release status` (release or release-*/major/minor/patch); PR labeled Feature, clean title, Closes #N in *body only*; leave wiki/audit for human.
- **Bug**: Reproduce (or note:reproduction); regression test; Closes in body; labels need:* if missing info.
- **Research** (6 steps): Confirm question/options/criteria/output clear; gather primary evidence + document path; commit to docs/research/<slug>.md (or SPEC update); if product intent change, update SPEC; Doc PR with Closes; post summary comment before close. (Usage report if Feature/Question closure.)
- **Design** (4 steps): Confirm scope/constraints; produce artifact (wireframes, contract, model, diagram, ADR); commit to docs/design/<slug>.md or docs/wiki/Features/; Doc PR.
- **Question** (4 steps): Confirm label + info goal/answer signal; batched review (/question-batch or script); commit answer artifact (docs/research) + process updates (AGENTS, skills.yml) if guidance changes; Doc PR.
- **Task** (6 steps): Confirm label + human-only (why agent can't, context, instructions, done signal, links); link artifacts + inherit Epic milestone; redact sensitive; completion comment with `<!-- PLATE-TASK-CLOSED -->` + close directly (no PR unless repo truth changes); if changes truth, follow-up PR/Doc.
- **Audit**: Commit to docs/audits/; if drift, open Bug/Feature; Doc PR.
- **Migration**: Commit to docs/migration/; update completion-report.md; Doc PR.
- **Epic**: Wiki summary in docs/wiki/ or epic comment summarizing child outcomes (post when all children resolved); Doc PR? Human review before next epic.
- **Release** (7+ steps): Confirm standing "Next Release" issue (titled default, Epics link via sidebar); work on track branches (major/minor/patch) per label; packaging (freeze, semver lock via cut+labels+issue, create versioned branch, rename issue, *immediately* spawn fresh Next); Release PR (Documentation label, heavy CI); human merge; finalize (tag, triggers from .plate/, ensure next Next, hard-reset); GitHub Release from tag+release.json; (plus pre: gh plate release status, init/repair for standing state per #320).
- **Cross for all**: Exactly one type label at create (enforced); milestone for Epic/Feature/Bug/Doc PRs (warning gate); fragments for *process/agent/template changes* (even in Release/Epic refinement); sub-issue linking for Epics; PLATE_SESSION_STATE in planning; usage report on agent-run Feature/Question closes (harvested to COSTS.md); no self-merge unless autonomous + risk:low + eligible (no AGENTS/SPEC/CODEOWNERS/workflow/credential changes).

### 2. Ceremonies
- **Epic-close**: All child Feature/Bug PRs merged to epic/<name>; post summary comment on Epic (outcomes, migration notes, usage?); PR from epic/<name> → release (label Feature/Doc, Closes #N); human squash-merge; Epic closes via body keyword.
- **Release** (detailed in AGENTS + design/release-ceremony-refinement.md): Standing Next Release (always one open Release titled "Next Release"); Major/Minor/Patch labels drive track branches (permissive next-* during dev); packaging phase (freeze non-bugs, infer/lock semver from fragments+labels+issue, create release-vX.Y.Z combining tracks, rename standing issue, *immediately spawn fresh Next*); Release PR from versioned → main (Doc label, heavy CI after fast-fail); human approve/merge; finalize (tag+push, .plate triggers + extensions/release_checks, hard-reset branch to tag); GitHub Release from tag (populated from release.json); (legacy single-release supported in transition).
- **PR babysit** (detailed in AGENTS, pr-babysit skill): Local `gh plate pr babysit <N> [--act] [--watch] [--branch-update-strategy]` (MCP plate_pr_babysit + resolveReviewThread); detects unresolved review threads from third-party agents (devin etc.) + base branch out-of-sync (BEHIND/CONFLICTING/DIRTY); for suggestions in comments: apply or reply+explain; for other actionable: code change or reply; resolve threads via GraphQL after address; push to *existing* PR branch (no new PR); add need:human-review for judgment cases; feedback-resolution check in branch protection; config via PLATE_PR_FEEDBACK_AGENTS var; legacy workflow deprecated.
- **Q&A / Contemplation / Curiosity** (Epic #139 + children): List/synthesize Questions; record_answer (PLATE-ANSWER block + committed to curiosity/answers/ per #258); contemplate (checklist vs cited evidence, log, close-ready); blocking Question as last-resort (create + pause status on original, bidirectional); resumption (merge answer, unblock report, resume); backfill for historical; answer_signal in body for strict closure; usage on closes.
- **Bootstrap / Health / Features / Doctor**: Bootstrap --apply for labels/branches/.plate/Questions/Goals/wiki; health (labels, protection, epics, binaries, Goals, Questions, plate_config, curiosity_answers, etc.); features; doctor for low-risk fixes.
- **Plan Epic** (stub #256 + related): Interactive (chat + ask_user_question or qanda); create Research→Design→Feature children as need:refinement stubs; link sub-issues; update PLATE_SESSION_STATE; handoff.
- **Info Audit** (#218+): plate_perform_information_audit (dry_run, scope); evidence hierarchy (tests > code/workflows > docs/wiki); generate Questions/Research/Design/Feature/Bug/Doc + draft SPEC patch; human for vision/SPEC/public claims.
- **Other**: Upstream template sync (PLATES-CORE markers, sectional); wiki-sync (opt-in, scoped, provenance); migration (docs/migration/ + completion-report).

### 3. Cross-Cutting Rules & Transitions
- Labels: Exactly one type (Bug/Feature/Epic/... for issues; Bug/Feature/Doc/Feedback for PRs); stable area:*, risk:*, need:* (need:refinement for planning stubs, need:human-review for escalations); Major/Minor/Patch for tracks; Epic: short-name (legacy); status:stub/blocked/ready-to-work (exceptions).
- Fragments: Required for Feature (or process-changing) PRs touching process/templates/agent surfaces (even Epic/Release refinements); unreleased/ or epic-*/ ; schema (slug, change_type, surface, summary, migration_impact, agent_notes, optional guidance/breaking/links/requires); cut aggregates to vX.Y.Z/.
- PR/Issue hygiene: Clean human titles (no [WIP] etc.; use Draft status); metadata in labels/body/Development sidebar/milestones; Closes #N in body only for intended closes; atomic (small, revertable, ≤10 files soft); no direct to main; base via gh plate release status.
- Session/Orchestrator: PLATE_SESSION_STATE (phase, last_step, turn, child_issues, extracted...); orchestrator feeds (agent_type, config={issue, task_type, prior_state}) to MCP for templatized prompt (base_role + PLATE_instructions); agent can callback "what next?"; supports ask_user_question for interactive.
- Autonomous: .github/AUTONOMOUS_MODE enables self-merge for risk:low eligible PRs (no AGENTS/SPEC/CODEOWNERS/workflows/cred changes, no need:human-review); use gh pr create --label risk:low,auto-merge + gh pr merge --auto --squash; feedback-resolution gate.
- Escalation/Human: need:* labels + comments; human checkpoints (Epic summary before next, merge approval, release, irreversible); prohibited (self-merge unless autonomous+eligible, bypass checks, fabricate, expose secrets, close without artifact).
- Other: GitHub as single source (artifacts over chat); resource consciousness (targeted tools, batch); easy revert norm (squash to main, no direct); upstream PLATES-CORE sectional sync.

### 4. Agent Roles / Orchestrator Contexts
- **Implementer**: Follows Feature/Bug loop (tests first, fragment, PR to release-*, babysit if feedback).
- **Researcher/Designer**: Research (evidence + artifact + Doc PR + summary+usage); Design (artifact + Doc PR).
- **Planner**: plate_plan_epic (or interactive chat/qanda) + what-next for turns; creates children in R→D→F, links, updates session state.
- **Reviewer/Babysitter**: PR babysit loop (detect threads/out-of-sync, apply suggestions or reply, resolve, push to same branch).
- **Orchestrator** (vision): Maintains task queue; calls MCP with (agent_type e.g. implementer|researcher, config={repo, issue/epic, task_type, prior}); receives structured next + prompt_snippet; spawns specialized (base from catalog + PLATE instructions); handles callbacks for "what next?"; uses for Epic planning, child work, ceremonies.
- **Direct agent**: Calls plate_what_next for self-guidance before/while tasks; reduces re-teaching full AGENTS/SPEC.
- **Q&A/Curiosity/Contemplation**: During any flow for info goals; record + contemplate + blocking/resume.

### 5. MCP / Tool Surfaces & Sequencing
- Core: plate_health (signals for state), plate_epic_status (children, milestones), plate_features, plate_release_status (fragments, Next Release, tracks), plate_get_answers / record / backfill / list / synthesize (curiosity during flows), plate_contemplate, plate_pr_babysit + resolve, plate_plan_epic (stub), plate_what_next (this), plate_*_migrate, delegate_to_agent, plate_create_blocking_question, plate_perform_*_audit, discussions tools, etc.
- Sequencing: health/features/bootstrap/Goals/curiosity before mutations; what_next for guidance at start/turns/callbacks; record+contemplate for answers; babysit for feedback; release for ceremonies; plan_epic for Epics (what_next as subroutine); graceful fallback on incomplete state.
- Registration: mcp_server.py dispatch + tool list (inputSchema); return .to_dict() payloads; read-only for guidance (no mutations except via explicit like record/babysit).
- Live vs config: Prefer live queries (small payload); accept hints/config for context (repo, issue, task_type, prior_state, extra).
- Output for what_next: per resolutions (structured steps + prompt_snippet for orchestrator/direct; references to AGENTS/SPEC/design; required artifacts; branches/questions for user; done flag; snapshot).

### 6. State Detection Signals (queryable live or cheap)
- GitHub: open/closed issues by labels (Epic/Feature/Question/need:*, Major/Minor/Patch, Release), milestones, sub-issues/closing refs (for linked), PR mergeStateStatus (for babysit), branch protection/existence (via /branches/*), contents (for .plate, docs/wiki/Goals.md, .agentic/...), search for fragments count? (via local or release status).
- Local (in clone): .agentic/releases/unreleased/ (count + slugs for pending), .agentic/releases/v*/ (history), .plate/ (config presence/valid via health), docs/wiki/Goals.md, markers (PLATE-*, .agentic/markers), git status/tags, PLATE_SESSION_STATE in issue bodies/comments.
- MCP/derived: plate_health (labels_ok, open_epics, goals_present, open_questions, plate_config_*, curiosity_answers, errors), plate_epic_status (per-Epic open/closed children), plate_release_status (active Next Release, linked/on-hold Epics, track summary, pending_fragments, extension checks), plate_features, get_epic_status, curiosity index presence, release fragment count.
- Other: PR feedback agents var, autonomous mode file presence, label-check enforcement.

### 7. Escalation, Autonomous, Prohibited, Human Checkpoints
- Escalation: need:human-review / need:security-review / need:decision / need:docs / need:tests / need:reproduction / need:refinement / need:wiki-sync; blocking comments; human for creds, arch decisions, public claims, merge/release approval, Epic summaries.
- Autonomous eligibility: .github/AUTONOMOUS_MODE present; PR risk:low; no touch AGENTS/SPEC/CODEOWNERS/workflows; no cred/payment/auth/security; no need:human-review; feedback-resolution green.
- Prohibited: self-merge (unless autonomous+eligible), bypass checks, weaken tests, fabricate results, rewrite intent silently, expose secrets, close without artifact (PR+Closes or Task comment `<!-- PLATE-TASK-CLOSED -->`), treat stubs as ready without refinement.
- Checkpoints: Epic summary comment before next epic; human merge for Release PRs; release cut ceremony (freeze, status, cut, PR); interactive planning (ask_user_question); approval for vision/SPEC/public.

## Decision Matrix / Flow Encoding Recommendations (v1 Static)

v1: Static Python decision tree / tables in mcp_server.py or dedicated what_next.py (inspectable, versioned with AGENTS.md, testable via unit + golden paths, no LLM invention of rules). Encode as if/elif or dict[role][phase/state] → {action, rationale_ref (AGENTS section), prompt_snippet (PLATE instructions to concat to base_role from catalog), required_artifacts, branches (e.g. ask_user), done: bool}.

Prioritize high-value for v1 (per planning: Epic planning, Feature/Bug loop, Research/Design closure, PR babysit, Release cut, Q&A/contemplation; deliver "entire PLATE as exists today" to max in static). Graceful for incomplete state (fallback to health/epic_status + "inspect manually").

Example skeleton (expand from current _what_next + survey):
- If no labels/Goals/wiki/starters: bootstrap (ref AGENTS bootstrap, health).
- Elif open Questions (esp with answer_signal or blocking): qanda / record / contemplate / synthesize (ref #139 flows).
- Elif open Epics with children (esp need:refinement or ready): plate_epic_status + advance child (Feature: tests+impl+fragment+PR; use what_next recursively for sub-steps); planner mode for new children.
- Elif pending fragments + release signals: release status / cut / finalize (ref Release loop + #306).
- Elif PR feedback or out-of-sync: babysit (ref babysit loop in AGENTS).
- Elif info drift suspected: info_audit (ref #218).
- Else: release status or next beta (or "use plate_plan_epic for new Epic").
- Orchestrator path: given agent_type + config (issue/task), return full templatized (base + snippet); support incremental "what next?" for running agent.
- Always: live queries preferred (health + epics + release + curiosity + local .agentic/.plate + GitHub labels/children); snapshot returned; citations to sources; support ask_user_question for branches.

Handoff to Design #284: Use this inventory for full decision tree encoding (tables or ruleset traceable to AGENTS sections); define exact schemas (see Epic Q&A resolutions for input/output); drift guards (tests asserting coverage of listed flows + links in code/comments to AGENTS; later linter/generated?); integration with plate_plan_epic (subroutine), agent_guidance (inject instructions), baseline skills/catalog (examples for orchestrator spin-up + direct).

For #283 contract recs: plate_what_next (name per planning); live state + hints; output {status, next: {instructions (prompt_snippet), steps, artifacts, refs, done}, snapshot, error?}; static code encoding; read-only; v1 high-fidelity on existing (phased for full).

## Current Status & Recommendations

- Initial seed + this survey committed as artifact.
- v1 static in current _what_next is basic (health labels/epics only); expand per this inventory + Design.
- Gaps for full: exhaustive in one doc (this + #283 artifact); full tree encoding will be large (prioritize, use refs not duplication); future data-driven (.plate or wiki) after v1 validates.
- Dogfood: Call plate_what_next during work on #282 children / beta items; capture in comments/PRs.
- No drift: Keep encoded logic + AGENTS in sync via tests/comments/reviews; update both on process changes (with fragment).

This fulfills the Research goal for #286 (and feeds #283). Open Documentation PR(s) with Closes #286 (and #283); post summary + usage on the Research issue(s) before close; update parent #282 session state / Epic body.

(Exhaustive but focused on primary; further iterations can add SPEC/code specifics or edge cases from fragments.)