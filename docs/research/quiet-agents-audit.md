# Quiet Agents: Instruction Sources, Brevity Guidance, and Noise Vectors Audit

**Epic:** Quiet Agents (interactively planned)  
**Date:** 2026 (planning session)  
**Status:** Initial audit artifact (committed as part of the epic)  
**Purpose:** Durable reference for why quiet rules were added, what surfaces control agent output/comment behavior, and where future cost/UX or autonomous-mode work should look.

## 1. Where Agents Pull Support Instructions (Primary Sources, Exposure Order)

1. `plugin/agents/plate.agent.md` (core "plate" persona, ~46 lines)
   - Thin router. Mandates `plate_what_next` first, `plate_delegate_to_agent` (short task_description), live MCP/health/release surfaces over broad prose.
   - Native Q&A preference.
   - Existing brevity: "Keep responses concise and action-oriented." (line 32)
   - Special modes explicitly call out Q&A/curiosity and Information audit (cross-ref to agent_guidance.py).

2. `src/plate_core/agent_guidance.py`
   - Reusable embedded guidance blocks returned by `get_agent_guidance_sections()`.
   - `QANDA_CURIOSITY_GUIDANCE` (lines ~58-123): native TUI preference, question handling flow, blocking last-resort procedure (creates Question + posts pause status on original), resumption (posts "Unblocked..." report + append-only merge).
   - `INFORMATION_AUDIT_GUIDANCE`.
   - `PLAYWRIGHT_E2E_GUIDANCE`.
   - Referenced from plate persona and docs.

3. `AGENTS.md` (root + template_payload mirror, ~40kB / 453 lines — known read hotspot)
   - Full doctrine: work loops (Feature/Bug/Research/etc.), resource consciousness ("Prefer targeted tool calls... Stop investigating after sufficient evidence"), pacing, atomic PR discipline, human checkpoints (Epic summary comment when all children resolved), Issue Artifact Rules (PR with Closes #N or Task completion comment with `<!-- PLATE-TASK-CLOSED -->`), usage-report requirement on agent-driven closures, babysit flow (local `gh plate pr babysit`, resolve threads via GraphQL, push to same branch; no new PR), autonomous mode rules.
   - Babysit section notes the shift to local/MCP babysitting and deprecation of the old workflow.

4. `src/plate_core/data/baseline_catalog.yml` (exposed via `plate_agents`/`plate_skills`/`plate_delegate_to_agent`/`plate_what_next`)
   - Per-agent `constraints` blocks (many repeat "Keep planning outputs concise and actionable", "Keep the response scoped to the delegated task").
   - what-next-plate-process skill, delegation metadata, example prompt segments, informational goals with "concise description" Answer signals.

5. MCP tool schemas + descriptions (`src/plate_core/mcp_server.py`)
   - Always present in tool-calling agent context. Vary from short to multi-sentence explanatory paragraphs (e.g. plate_pr_babysit, plate_contemplate, plate_create_blocking_question, plate_what_next).

6. `plate_what_next` + delegation surfaces (`mcp_server.py:79-118` for `_what_next`, `baseline_catalog.py:284-396` for packet/prompt builders)
   - Return `next_action`, `prompt_segment` (multi-sentence flows), `rationale`.
   - `build_delegation_packet` + short rendered prompt; constraints pulled from catalog + hardcoded scoping text.
   - Mandated by plate persona.

7. Context map + layered architecture
   - `docs/wiki/Agent-Context-Map.md`, `gh plate context` / `plate_context*`, design `cost-control-layered-agent-context-architecture.md`.
   - Purpose: reduce broad reads of AGENTS/SPEC by providing canonical "first step + authoritative artifact + machine surface + optional references".

8. Contemplation / Answer / Blocking machinery (become future context)
   - `src/plate_core/contemplation.py`: always posts `<!-- PLATE-CONTEMPLATION:BEGIN ... -->` log + (if close-ready) closure report with criteria + `=== USAGE REPORT ===` block; may create follow-up Feature; posts unblock report on original for blocking Questions.
   - `src/plate_core/mcp/curiosity_tools.py`: `RecordAnswerTool` (always posts PLATE-ANSWER block), `CreateBlockingQuestionTool` (creates Question with PLATE-BLOCKING-DUMP + pause comment on original), Get/Synthesize/List tools.

9. CLI human-readable output (noise when agents shell `gh plate` inside loops instead of MCP)
   - `src/plate_core/cli.py:284-355` (cmd_pr_babysit): watch loop unconditionally prints "Detected threads: X, actionable: Y...", "Sleeping Ns...\n", "No new babysit trigger posted.", base sync details, etc. Single-run similar multi-line report.
   - cmd_qanda (~592-703): "Prioritized open Questions...", "Tip: ...", "Next: Contemplation will...", full usage help on fallback.
   - Other cmds (health, epic status, release status, delegate, features, etc.) produce multi-line human prose.

10. Template payload (shipped to downstream via bootstrap)
    - `.github/copilot-instructions.md` ("Keep the chat flow small", "update the artifact, not chat history", routing to thin surfaces).
    - `.github/agents/plate-configurator.agent.md`.
    - Mirrored AGENTS.md + docs.

11. Secondary / reference: `.agentic/skills.yml`, design/research docs (per context map: open only when lighter surfaces insufficient), issue bodies / Answer signals, host TUI loop harnesses (Grok /loop, Copilot /every — outside PLATE but shaped by persona final-answer format).

## 2. Current Brevity / Quiet / Comment Discipline Guidance (Audit)

- Extremely sparse and non-prescriptive for the reported pain points.
- plate.agent.md:32: "Keep responses concise and action-oriented." (single sentence).
- baseline_catalog.yml: repeated "concise and actionable", "scoped" language in agent constraints and Answer signals ("A concise description...", "3-5 measurable outcomes...").
- AGENTS.md: "Resource consciousness", "Pacing", "Atomic PR discipline", "do not create more than five open PRs simultaneously", human checkpoints only at defined points, "Post a summary comment on the Epic issue when all child issues are resolved", usage-report requirement.
- QANDA_CURIOSITY_GUIDANCE: excellent on *native TUI preference* (to avoid dumping questions into chat) and blocking/resumption flows, but silent on "minimal front matter when the question text itself is presented".
- Babysit section in AGENTS: correctly pushes local `gh plate pr babysit` + thread resolution on the same branch, but does not explicitly say "on a no-op watch turn with 0 actionable, do not post a 'Checked, nothing this cycle' comment on the PR or tracking issue".
- No "looped turn must be terse bullet list of one-sentence items" rule.
- No "post GitHub comment / create issue only on verifiable forward progress or defined checkpoint" rule in the persona or reusable guidance.
- Contemplation engine intentionally always posts logs (auditability / "never lose information"); no accompanying guidance telling supervising agents not to add their own prose status around routine evaluations.
- Prior cost-control work (layered context #394, narrow delegation packets #395, thin surfaces, hotspots research #392, context map) has already attacked *instruction volume* and repeated state discovery. This epic continues that direction with explicit quiet discipline.

## 3. Noise Vectors (Highest-Leverage Emission Points)

**Terminal / loop turn summaries (user highest priority in this epic):**
- `cli.py:284-355` (babysit watch + single run) — the dominant source when agents run `gh plate pr babysit --watch` or equivalent inside /loop or /every.
- Similar unconditional multi-line output in qanda, health, release status, delegate, etc.
- Contrast: MCP equivalents (`plate_pr_babysit` etc.) return clean dicts — under-instructed for quiet autonomous use.

**GitHub comments on no-progress turns:**
- Supervising agent (weak guidance) posts monitoring status on PRs during babysit loops.
- Engine always posts (PLATE-ANSWER, PLATE-CONTEMPLATION, closure reports with usage block, unblock reports, blocking pause status, CreateBlockingQuestion creates + comments). User direction for this epic: leave engine posting unchanged; quiet via agent discipline only ("only comment if meaningful forward progress").
- Babysit *triggers* themselves are already gated well (`_post_babysit_trigger` only on `act and actionable and no existing marker`; merge trigger similar; dedup helpers).

**Q&A / question front matter:**
- CLI qanda help/tips + "Next: Contemplation..." prose.
- Agent framing when surfacing questions or in blocking dumps.
- Synthesized rationales from SynthesizePrioritiesTool etc. can be wordy.

**Context / prompt bloat (allowed light touch):**
- Long tool descriptions in mcp_server.py.
- what_next `prompt_segment` (multi-sentence bootstrap/epic/release flows).
- Delegation rendered prompts (even as packets narrow).

(See subagent explore result for additional line citations on emission points and the 5 highest-leverage places: contemplation/curiosity comment paths, babysit+watch, what_next+delegation builders, CLI status/qanda prints, and the central instruction surfaces themselves.)

## 4. Recommendations Implemented in This Epic (per Approved Plan + User Answers)

- Guidance + persona + catalog constraints first (no new --quiet flags or engine changes this round).
- New prescriptive `QUIET_OPERATIONS_GUIDANCE` (or equivalent) in agent_guidance.py covering:
  - Terminal/loop: must be bullet list of one-brief-sentence items only.
  - GitHub comments: only on meaningful forward progress (examples + counter-examples) or defined human checkpoints. Engine markers exempt.
  - Q&A: minimal framing only.
  - Prefer MCP structured data; collapse noisy CLI output internally.
- Strengthen plate.agent.md (Behavior rules + looped ops note).
- Propagate to baseline_catalog.yml constraints + light what_next/delegation prompt tightening.
- Light MCP tool description trims (context hot spots).
- Short audit doc (this file) + minimal AGENTS.md cross-ref + required fragment.
- Non-negotiables respected: usage reports, Issue Artifact Rules, contemplation markers, --json contracts, traceability all unchanged.

## 5. Verification Notes (for the Implementing Fragment / PRs)

- Manual: simulate /loop babysit turn under updated persona → expect 1-5 terse bullets, no raw multi-line CLI dump as final answer, no spurious PR comment.
- Inspect: `gh plate agents show plate`, `plate_agent`, delegation packets, `plate_what_next`, MCP tool list (lighter descriptions).
- Existing tests (catalog, mcp, pr_babysit, cli, contemplation, curiosity) must continue to pass (no logic changes).
- Fragment must cite this doc + persona/guidance/catalog changes + concrete "before/after" style evidence.

This audit was produced via targeted exploration (list_dir, read_file with limits, grep, open_page_with_find equivalents via grep, + dedicated explore subagent) in plan mode before any implementation edits. It serves as the Research artifact for the Quiet Agents epic.

Cross-references: cost-control-layered-agent-context-architecture.md, cost-control-narrow-delegation-packets.md, cost-control-agent-context-hotspots.md, qanda-*.md, contemplation-engine-contract.md, Agent-Context-Map.md, AGENTS.md §Resource consciousness / Human checkpoints / Issue Artifact Rules / babysit flow, plugin/agents/plate.agent.md, src/plate_core/agent_guidance.py.