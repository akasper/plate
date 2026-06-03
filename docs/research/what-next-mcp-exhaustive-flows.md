# Research: Exhaustive enumeration of all PLATE process flows for plate_what_next MCP coverage

- **Issue:** #286
- **Parent Epic:** #282
- **Researched by:** Grok agent (interactive session)
- **Date:** 2026-06-03
- **Status:** In progress (initial inventory seeded at issue creation; full survey + table to be expanded in this Research)

## Research Question

What are *every single flow*, sub-flow, ceremony, decision point, required artifact, label/state transition, role context, and MCP/tool sequencing rule from the current PLATE methodology (AGENTS.md, .agentic/*.yml, SPEC, implemented surfaces, etc.) that the `plate_what_next` MCP must be able to detect (via live state + caller config) and respond to with precise, citable next-step guidance (structured + templatized prompt segment = base role prompt + PLATE instructions) so that an orchestrator or direct agent can implement the full PLATE process without re-ingesting the entire methodology or risking drift/omission?

This supports the orchestrator vision: feed (agent_type, config={issues, task_types, prev_state, ...}) → get the exact PLATE-augmented instructions for a specialized agent instance, and allow agents to call back "what next?" via structured MCP.

## Sources (search path documented)

- Primary: AGENTS.md (full reads of Required Work Loop, Issue Artifact Rules, ceremonies sections, babysit loop, label rules, documentation rules, upstream sync, escalation, prohibited, autopilot doctrine, atomic PR, branch model, CLI patterns, wiki sync, authority model table).
- .agentic/process.yml (codified release/epic/fragment rules, labels, artifacts).
- .agentic/releases/unreleased/README.md (full fragment contract, when to author, fields, migration_guidance vs impact, aggregation via cut_release).
- Code surfaces: src/plate_core/mcp_server.py (all registered plate_* tools: health, epic_status, features, bootstrap, plan_epic, pr_babysit, resolve_review_thread, contemplate, curiosity suite, release_*, migrate_*, agents/skills/delegate, e2e tools), mcp/curiosity_tools.py, pr_babysit.py, etc.
- docs/research/README.md (required artifact format for Research).
- Existing related research (e.g. plate-plan-epic-host-agent-tui-and-scope-policy.md) and designs.
- Grep for "flow|loop|ceremony|step|Required Behavior|babysit|fragment|Epic-close|Release" across AGENTS.md.
- List of .agentic/ and docs/research/ for process artifacts and prior inventories.
- Epic #282 body (vision + Q&A resolutions) and sibling Research #283 stub.

Search path is reproducible via the tool calls and file reads in the session that created #286.

## Findings (Initial Enumeration / Decision Inventory)

The following is seeded from the sources above at the time #286 was opened. This Research will expand it into categorized tables with (role/context, observable_state_signals) → (exact next required behavior + AGENTS.md § ref + suggested `prompt_snippet` or action + artifacts_required + done?).

### 1. Issue Type Work Loops (AGENTS.md §Required Work Loop + Issue Artifact Rules)

**Feature (8 steps - core happy path for most agent toil):**
1. Confirm labeled `Feature` + assigned to Epic's GitHub milestone (label-check enforces).
2. Identify acceptance criteria, expected tests, documentation impact, and risk.
3. Add or update tests before or alongside implementation.
4. Implement the *smallest coherent change* that satisfies the issue.
5. Update per-feature change files in `.agentic/releases/unreleased/<slug>.json` (describe behavior + verification; use specific schema).
6. Add or update fragment when the change affects PLATE process or templates.
7. Open PR labeled `Feature` with `Closes #N` in body. Complete PR template. For gh: `gh pr create --label "Feature" ...` (apply type label at creation; use --body-file for multiline).
8. Leave wiki-sync, release-note, and audit evidence for human reviewer/post-merge workflows.

**Also:** Atomic PR discipline (≤~10 files soft limit preferred, many small PRs), squash to main, branch `type/short-description`, no direct to main. PR titles clean (no [Feature] etc. prefixes; metadata in labels/body/Development sidebar).

**Bug:**
- Reproduce failure or document why not possible yet.
- Add regression test.
- `Closes #N` in PR body.
- Label gaps with `need:reproduction`, `need:tests`, `need:human-review`.

**Research (6 steps):**
1. Confirm research question, options, decision criteria, required output clear.
2. Gather evidence (prefer primary/authoritative; document search path).
3. Commit findings to `docs/research/<issue-slug>.md` (see docs/research/README.md format: Issue, Researched by, Date, Status, Research Question, Sources, Findings, Recommendation) *or* SPEC.md update.
4. If findings change product intent, also update relevant SPEC.md section.
5. Open Documentation PR with `Closes #N` in body.
6. Post summary comment on the issue *before closing it* (include === USAGE REPORT === tokens/cost/duration block).

**Design:**
1. Confirm scope, constraints, the feature/system being designed.
2. Produce design artifact (wireframes, API contract, data model, architecture diagram, decision record).
3. Commit to `docs/design/<feature-slug>.md` or update `docs/wiki/Features/<feature>.md`.
4. Open Documentation PR with `Closes #N`.

**Question:**
1. Confirm labeled `Question` (or legacy) + clearly states information goal and answer_signal.
2. Use batched review (`/question-batch` or `scripts/question_batch.sh`).
3. Commit the answer artifact (e.g. `docs/research/<slug>.md`) + any resulting process updates.
4. When answer changes operating guidance, update `AGENTS.md` and `.agentic/skills.yml` in *the same PR*.
5. Open Documentation PR with `Closes #N`.

**Audit:**
- Commit findings to `docs/audits/`.
- If drift found, open follow-up Bug or Feature per finding.
- Open Documentation PR with `Closes #N`.

**Migration:**
- Commit progress to `docs/migration/`.
- Update completion status in `docs/migration/completion-report.md`.
- Open Documentation PR with `Closes #N`.

**Release (8 steps - see also ceremonies):**
1. Confirm Release issue exists with target version, linked epics, completed pre-release checklist.
2. Ensure all epic branches for release merged into `release` branch (Epic close ceremony).
3. Run `gh plate release status` (or equivalent) to confirm no unexpected pending fragments.
4. Run `python scripts/cut_release.py vX.Y.Z` (or `gh plate release cut vX.Y.Z`) to aggregate unreleased fragments into `.agentic/releases/vX.Y.Z/`.
5. Commit the versioned directory, then open PR from `release` → `main` with Release issue in body (`Closes #N`).
6. After human approval and merge, apply tag: `git tag vX.Y.Z && git push --tags`.
7. Create the GitHub Release from the tag (populated from `.agentic/releases/vX.Y.Z/release.json`).
8. Hard-reset the `release` branch to the tag: `git checkout release && git reset --hard vX.Y.Z && git push --force-with-lease`.

**Epic:**
- Create stub with proper labels (Epic + Epic: short-name + areas) + milestone assignment (enforced).
- Children created in Research→Design→Feature order (with need:refinement).
- Sub-issue links.
- PLATE_SESSION_STATE updates in body/comments during planning.
- Summary comment on Epic when all children resolved.
- Epic-close ceremony PR (epic/<name> → release).

**Before *any* issue close (manual or via linked PR):** Post final comment with structured usage block (tokens, cost, duration). `Feature` and `Question` closures harvested to `.agentic/COSTS.md`.

### 2. Ceremonies & Branch Model (AGENTS §Branch Model and Ceremonies + process.yml)

**Three-tier branch model:**
- `epic/<short-name>`: Owned by one Epic. All Feature/Bug PRs for that Epic target this (squash).
- `release`: Persistent integration. Epic-close PRs (squash) merge in. Always points to (future) tag.
- `main`: Stable tagged history. Every commit is a semver release. *Only* Release PRs (squash).

**Epic-close ceremony (when all child issues resolved):**
1. Confirm all Feature/Bug PRs for the Epic merged into `epic/<name>`.
2. Post summary comment on the Epic issue (outcomes + migration notes).
3. Open PR from `epic/<name>` → `release`. Label `Feature` or `Documentation`.
4. Human reviews + squash-merges. Epic closes via `Closes #N` in PR body.

**Release ceremony (see 8 steps above):** Requires Release issue, `gh plate release status`, cut script, PR release→main (Documentation label + Closes), human + tag + GitHub Release + hard reset release to tag.

**Release branch protection:** PRs required; only epic/* or release-prep; status checks same as main.

**Fragment authoring (mandatory for Feature PRs touching process/templates/agent surfaces):**
- Author under `.agentic/releases/unreleased/<slug>.json` (kebab unique).
- Required: slug, change_type (feature/fix/docs/process/breaking), surface, summary, migration_impact, agent_notes.
- Optional: migration_guidance (array of ordered steps preferred for unambiguous), breaking, links, requires.
- Use `migration_guidance` array when discrete numbered actions needed (for agent execution); prose for quick human scan.
- Fragments accumulate; swept by `cut_release.py` / `gh plate release cut` into versioned dir + release.json.
- Example structure in the README.

**PR babysitting (preferred local flow, replaces legacy):**
Use `gh plate pr babysit <number> [--act] [--watch] [--branch-update-strategy <copilot-request|local-rebase|none>]` + MCP `plate_pr_babysit` + `plate_resolve_review_thread`.
1. Start/join babysitting locally.
2. Auto-detects: unresolved review threads from third-party agents (actionable feedback); base branch out-of-sync (BEHIND/CONFLICTING/DIRTY).
3. Review all open inline comments + overall review body from named reviewer.
4. For suggestions (` ```suggestion `): apply directly as commit unless bug/false-assumption (if skip, reply with brief explanation).
5. For other actionable: push code change or reply explaining why no change needed.
6. After addressing (code/suggestion/reply), resolve via GraphQL resolveReviewThread (find THREAD_NODE_ID via repository.pullRequest.reviewThreads matching comments.nodes.databaseId).
7. **Push all changes to the *existing* PR branch** — do not open new issue/PR for feedback response.
8. For human judgment items (credentials, arch, security): add `need:human-review` + blocking comment.
- Base sync: default copilot-request posts @copilot trigger (deduped); local-rebase not yet; none = detect/report only. --act triggers the merge comment when out-of-sync.
- Lifecycle artifacts defined.
- Config: PLATE_PR_FEEDBACK_AGENTS repo var (comma list e.g. devin-ai-integration[bot],openhands-agent).
- Merge gate: require feedback-resolution check in branch protection.
- Legacy workflow is manual-only dispatch for troubleshooting.

### 3. Label Rules, PR/Issue Creation Discipline, Documentation Rules

- Exactly one issue type label: Bug/Feature/Epic/Release/Research/Design/Question/Audit/Migration/Feedback Response.
- Exactly one PR type: Bug/Feature/Documentation/Feedback Response.
- Feedback Response: combined for feedback-response process work (no Epic milestone required).
- Epic: short-name supplemental (optional; milestones are canonical for Epics).
- area:*, risk:*, need:* stable families (need:reproduction/tests/human-review/security-review/wiki-sync/decision/design/docs/refinement/etc.).
- Do not create ad-hoc labels unless they change routing/enforcement/reporting/auditing/review burden/agent behavior. Use Projects fields for transient planning state.
- Every new PR: add exactly one required PR type label *at creation time* (unlabeled or multi fail CI immediately). Use `gh pr create --label "Feature"` etc. (checkboxes in template do not set labels).
- PR titles: clean, concise, human-only. No bracketed prefixes ([Feature], [WIP], DRAFT: etc.). No issue refs/closing keywords in title (put in body only). GitHub native fields for type/links/Draft status/milestones.
- For multiline bodies (any env): use --body-file or here-strings (avoid literal \n in double-quotes from PowerShell).
- "Always include a closing keyword (`Closes #N` etc.) in the PR body" (enforced by pr-issue-link-check.yml warning gate; GitHub auto-closes on merge to default).
- Documentation rules: Every Feature PR changing process/templates/agent surfaces authors fragment (see above). Doc PRs commit to appropriate docs/ subdir and explain impact. Changes altering behavior update both impl evidence + doc evidence. Fragment-first is canonical for PLATE changes.
- CLI body safety patterns documented.

### 4. Other Major Flows / Rules

**Autopilot doctrine & Atomic PR:**
- Humans judgment; agents toil.
- Small independently revertible PRs (soft ≤10 files for impl; split if grows; additive-first ordering).
- Prefer squash merges (clean history). Never push directly to main. Name branches type/short-desc. Each main squash commit = stand-alone unit.
- Pacing: ≤5 open PRs unless all auto-merge eligible.
- Human checkpoints: summary comment on Epic when all children resolved; stop and let human review before next epic. Do not start new epic autonomously.
- Resource consciousness: targeted tool calls, batch parallel reads, stop investigating after sufficient evidence.

**Autonomous mode** (opt-in via presence of .github/AUTONOMOUS_MODE on default; delete to disable):
- Agent may merge own eligible risk:low PRs (via gh pr merge --auto --squash or label).
- Eligibility (all true): risk:low label, does not modify AGENTS/SPEC/CODEOWNERS/workflows, no credential/payment/auth/security changes, no need:human-review or need:security-review, no change to public claims in README/marketing.
- How: gh pr create with labels including risk:low + auto-merge + required types; then gh pr merge --auto --squash.
- .github/workflows/auto-merge.yml also gates on the marker + label.
- One-time GitHub settings for auto-merge + Actions perms.
- Security: cannot self-escalate (agent cannot create/modify the AUTONOMOUS_MODE file or relax protections).

**Upstream PLATE Template Synchronization:**
- Sectional only (PLATES-CORE:BEGIN/END block-id markers).
- Copy only relevant core blocks; preserve local customizations outside markers.
- Atomic PR (Feature or Documentation) with Closes, update fragments, run checks.
- Do not wholesale overwrite on upgrades.
- Configure upstream remote if needed.

**Wiki Sync:** Opt-in only. If requested but not configured, add need:wiki-sync + escalate. Prefer scoped, auditable, reversible.

**Escalation Rules:** Escalate to human for: product intent ambiguous, ACs conflict, required label missing and can't infer, workflow would need weakening, secret/permission required, public claim might change, agent cannot produce required evidence.

**Prohibited Actions:**
- Merge own PRs unless autonomous + fully eligible.
- Bypass required checks, remove doc gates, weaken tests to pass CI, fabricate results.
- Silently rewrite product intent, expose secrets, enable write automation w/o approval.
- Create/delete .github/AUTONOMOUS_MODE themselves.
- Treat chat history as more authoritative than repo artifacts.
- Close issue without corresponding PR carrying `Closes #N` (or Fixes/Resolves) in *body*.
- Open PR resolving specific issue without including the closing keyword in body.

**Before closing any issue:** usage report comment.

**Other surfaces/flows the what-next must know when to trigger:**
- plate_health / plate_features / plate_bootstrap before any mutating work.
- plate_plan_epic (and its internal Q&A/children creation per its own design).
- Full curiosity/Q&A loop (list/synthesize/get/record/answer + contemplate + present forms for interactive; batched question processing).
- pr_babysit + resolve (as detailed ceremony above).
- release status / notes / cut + migrate.
- agents / skills / delegate_to_agent (for orchestrator spin-up of specialized per config).
- e2e tools when in test-related Feature work.
- Self: agents can/should call plate_what_next for their own guidance ("OK, I just ... what do I do now?").
- Contemplation from answers during Q&A or planning.

**State signals** (live queryable by the MCP): labels (type + need: + Epic: + area: + risk:), milestone, sub-issues/children status, open Questions for context, .agentic/ dir + unreleased fragments count + specific files, .plate/config or bootstrap signals, PLATE_SESSION_STATE blocks in bodies (phase, turn, children list, extracted), git/branch state for babysit, PR review threads state, etc.

## Recommendation

- Encode the enumerated flows as a maintainable static structure (e.g. role/phase keyed data + small resolver functions with comments linking back to exact AGENTS § or process.yml line; plus tests that assert "for this state, what-next returns ref to §X and requires fragment").
- v1 coverage priority (highest value / most common agent toil first): Feature loop + fragment authoring + PR creation discipline + basic babysit detection, then Research/Design/Question loops + usage reports, Epic planning integration, Release ceremony steps, full babysit loop details, autonomous/eligibility checks, cross-cutting (labels at create, sub-issues, session state, escalation).
- The output prompt_snippet should be concise "PLATE-specific instructions" segment (not full AGENTS dump) + exact citations so the specialized agent or orchestrator can act precisely.
- Drift prevention: the committed research md + the MCP code + AGENTS.md must be updated together on process changes (via fragments); consider a test that loads the enumerated list and spot-checks coverage.
- Feed any gaps found (e.g. missing MCP for certain ceremony steps) back as follow-ups to #284/#285 or new children on #282.
- After this Research: commit the expanded `docs/research/what-next-mcp-exhaustive-flows.md` (update this file), open Documentation PR with Closes #286 (and reference #282), post summary + usage report comment on #286 before close.

## Links / Related
- Epic #282
- Sibling Research #283 (contract, live state sources, static flow strategy)
- Design #284, Feature #285
- AGENTS.md (source of truth for process)
- .agentic/process.yml, releases/unreleased/README.md
- docs/research/README.md

(Expand this document with the full detailed decision tables during the Research work. Initial seed created alongside opening #286.)