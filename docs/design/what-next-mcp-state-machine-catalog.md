# PLATE State Machine Catalog (what_next / Orchestrator)

**Source:** Interactive TUI Q&A on #284 (25 small steps, all <100 words, using the exact requested format "Given an agent of type X who entered state Y on a project/issue with Status Z, the MCP server should enter state Y2 with prompt W. Is that correct?" with one answer reserved for feedback; very brief; one feedback option always available).

**Locked Model (refined per user feedback during TUI):**
- Project state lives in GitHub (labels, issues, PRs, .agentic/ fragments, health signals, curiosity/answers.yml, AUTONOMOUS_MODE, etc.).
- State transitions are reported by the orchestration agent (or, in future versions, directly by the MCP server listening for GitHub webhooks).
- MCP is stateless: given a reported transition + project snapshot, it returns next steps as ABC (list of tuples: (agent_type, suggested prompt W, planned tool calls / ctx)).
- The orchestration agent manages actual agent/work state, delegates to specialists (using base_role from catalog + the returned prompt segment), executes, babysits, etc.
- All examples use generic "a PLATE repo" (portable to any repository following PLATE per AGENTS.md and #286).

**Exhaustive List of Confirmed Transitions** (aggregated from all TUI steps; Event -> [agent_type, 'W (short action/prompt segment)', {ctx}])

### Epic Autonomous Implementation Story (for an Epic like #282)
1. New Epic detected/open (Epic label + milestone, per AGENTS Epic loop + human checkpoint)  
   -> [planner, 'plan epic children / create stubs (need:refinement)', {epic:#N}]

2. The user has finished interactively planning a new epic.  
   -> [planner, 'create child tickets for epic', {epic:#N}]

3. A child Feature is ready (Feature label + milestone + ACs per AGENTS Feature loop; no tests yet).  
   -> [implementer, 'implement Feature (tests first, fragment if process, PR to release-* base via gh plate release status, Closes in body)', {issue:#N}]

4. PR opened for child or review feedback received (unresolved threads, per babysit rules).  
   -> [babysitter, 'babysit PR (address threads, apply suggestions or reply, resolve via GraphQL, push to existing branch, escalate only w/ need:human-review, feedback-resolution gate)', {pr:#M, issue:#N}]

5. Child PR merged or child resolved with evidence (tests green, feedback clean, per Feature/Bug loop).  
   -> [orchestrator, 'child complete (record evidence/artifact, check siblings or epic all-resolved, snapshot, may parallel audit/curiosity)', {issue:#child, epic:#N}]

6. All children resolved (PRs merged to epic/, evidence, health/epic_status clean per AGENTS Epic-close).  
   -> [orchestrator, 'epic-close prep (post summary comment w/ outcomes + usage + migration notes; open Epic-close PR from epic/ to release, clean title, label Feature/Doc, Closes #N in body only; human checkpoint)', {epic:#N}]

7. Human merges the Epic-close PR (squash to release per branch model, per AGENTS Epic-close ceremony).  
   -> [orchestrator, 'finalize Epic close (post any final notes, hard-reset branch per release model, ensure next "Next Release" if applicable, Epic closes via keyword in PR body)', {epic:#N, pr:#M}]

### Cross-Cuts (apply across the process)
- Agent of any type begins assigned work (fresh session or after what_next delegation; per doctor + guidance).  
  -> [orchestrator, 'bootstrap (health + doctor --apply if issues, then proceed with assigned action or what_next per PLATE)', {agent_type, issue?, repo}]

- Assigned work blocked (open Question, need:human-review, curiosity block, or per Task rules human-only per AGENTS).  
  -> [orchestrator, 'escalate to human (create Task exact 6-field: human action required, why agent cannot safely proceed, context/artifacts, best-effort instructions, done signal <!-- PLATE-TASK-CLOSED -->, related links; or record Q&A/contemplate; link bidirectionally; no bypass)', {issue:#N, reason}]

- Specialist agent reports action complete (artifact e.g. PR/tests/fragment/comment per work loop, no block).  
  -> [orchestrator, 'record completion (update snapshot/prior_state, signals health/curiosity/fragments, check next sibling/ceremony, may parallel audit)', {agent_type, issue?, artifact}]

- Curiosity or open Question detected, or contemplation triggered during work (per Q&A rules, curiosity/answers model).  
  -> [researcher, 'contemplate or record_answer (PLATE-ANSWER block to answers.yml + per-Q .md, bidirectional links, resume after)', {question:#Q or gap}]

- A new standalone Feature issue is added (labeled Feature + milestone + ACs per AGENTS Feature loop, no tests yet; not an Epic child).  
  -> [implementer, 'implement Feature (tests first, fragment if process, PR to release-* base via gh plate release status, Closes in body)', {issue:#N}]

- Any PR is merged (babysit clean, feedback-resolution green, per PR babysit + AGENTS rules; not Epic-close specific).  
  -> [orchestrator, 'PR complete (update snapshot/signals, check linked issues/Epics/fragments/curiosity, may parallel release status or audit)', {pr:#M}]

- Information or test coverage audit triggered (e.g. via plate_perform_information_audit / plate_perform_test_coverage_audit, or periodic per doctor/guidance #363; per #218/#361 taxonomy).  
  -> [auditor, 'perform audit (classify per #361 feature_proof/supporting/infra, surface gaps per #362 "Proving tests:" convention, return prioritized gaps + evidence links + classifications)', {audit_type, repo}]

- PR is clean after babysit (feedback-resolution green, risk:low label, no AGENTS/SPEC/CODEOWNERS/workflows/credential/need:human-review changes, AUTONOMOUS_MODE present per AGENTS autonomous mode rules).  
  -> [orchestrator, 'self-merge eligible (call gh pr merge --auto --squash if all guards pass; do not self-merge otherwise or if need:human-review; per .github/AUTONOMOUS_MODE + auto-merge.yml)', {pr:#M}]

- Key signals change (e.g. health becomes PASS after doctor/bootstrap, fragments appear/disappear, curiosity index built/updated, AUTONOMOUS_MODE added/removed, open Questions resolved/added, per health/release/epic/curiosity signals in what_next inputs).  
  -> [orchestrator, 're-eval next (call what_next or directly emit next action based on new signals; may trigger bootstrap/audit/curiosity if relevant)', {changed_signal, project_state}]

### Release Ceremony
- gh plate release status shows pending fragments + Next Release issue + Epics with semver labels (Major/Minor/Patch); packaging decision point per AGENTS Release loop.  
  -> [orchestrator, 'release packaging (freeze non-bug merges, lock final semver, create release-vX.Y.Z branch, rename Next Release issue to vX.Y.Z, spawn fresh Next Release, commit .agentic/releases/vX.Y.Z/ notes)', {release_status}]

- Human approves and merges the Release PR from release-vX.Y.Z to main (heavy CI passed, per AGENTS Release loop + packaging vs finalization distinction).  
  -> [orchestrator, 'release finalization (git tag vX.Y.Z && git push --tags, kick downstream triggers per .plate/ + extensions, ensure next "Next Release" issue, hard-reset the versioned/originating branch to the tag, create GitHub Release from tag populated from .agentic/releases/vX.Y.Z/release.json)', {release_pr}]

**References:**
- AGENTS.md (full doctrine, required work loops per issue type, Issue Artifact Rules, Epic-close ceremony, Release ceremony (packaging vs finalization), Autonomous Mode eligibility, Task 6-field contract, fragment authoring, PR babysit + feedback-resolution, Q&A/Contemplation, Information Audit, bootstrap/health/doctor, atomic PR discipline, human checkpoints, etc.).
- #286 (exhaustive flows inventory as source of truth for tree nodes/guards).
- #284 (this Q&A), #282 (Epic), #368 (human checkpoint Task for direction on #282/#284).
- Recent dogfood: doctor (#262), test coverage audit MCP surface (#363), Task type support (#358), etc.

This catalog encodes the entire PLATE process as a state machine for the orchestrator + specialized agents via plate_what_next (and related MCP surfaces like health, doctor, audit, release, babysit, etc.). It is directly traceable to AGENTS.md and supports faithful autonomous (or semi-autonomous) progress while preserving all human checkpoints, atomicity, and GitHub as the source of truth.

**Usage Report for this Q&A (per AGENTS for Feature/Question closures and ceremonies; harvested to .agentic/COSTS.md):**
tokens: N/A (interactive TUI session)
cost: $0.00
duration: [full session]

**Next (per AGENTS):**
- Design artifact committed (this file).
- Summary comment posted to #284 (with reference to #284, pointers to #282/#368, full list excerpt or link, usage report; human can then open Doc PR if desired).
- Respect #368 as the durable human checkpoint for #282/#284 Epic-close (no autonomous close or new Epics).
- Future: handoff to Feature #285 for implementation of plate_what_next MCP surface + orchestrator.

The TUI Q&A delivered the state machine formalization interactively in the exact format requested. All steps grounded in AGENTS.md, #286, prior analysis, v1 _what_next, agent_guidance, health/release signals, and dogfood from the repo's own process.