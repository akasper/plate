# Research: Inventory of Informational Goals / Questions for Curiosity-Driven Development (Q&A Mode)

- **Issue:** #140 (Research child of Epic #139 "Curiosity-Driven Development: Q&A Mode for Informational Goals")
- **Researched by:** Grok (xAI), following AGENTS.md Research work loop
- **Date:** 2026-05-30
- **Status:** Complete

## Research Question

What is the current state of handling for "informational goals" (user questions that are not actionable Feature/Bug/Research/Design tickets) in the PLATE agentic system and GitHub workflows? What gaps exist relative to the four critical invariants required for a robust Curiosity / Q&A Mode? What reuse opportunities (especially the `plate_plan_epic` MCP stub) and architectural patterns exist to implement first-class Question issues, a /qanda synthesis surface, a Contemplation engine for answer ingestion, and a last-resort blocking workflow when agents encounter hard informational obstacles on open Issues?

## Sources

- `.github/ISSUE_TEMPLATE/` (epic, research, design, feature templates and existing question-handling patterns/workflows)
- `docs/research/README.md` (required Research artifact format, work loop steps, and template structure)
- `AGENTS.md` (full Autopilot Doctrine, Research/Design/Feature loops, PR title rules for humans, and emerging Q&A/Curiosity guidance sections)
- `SPEC.md` (existing product intent language around informational goals and agent workflows)
- `plugin/agents/plate.agent.md` (core agent persona and guidance, including new Q&A section)
- `src/plate_core/agent_guidance.py` (QANDA_CURIOSITY_GUIDANCE reusable constant and related sections)
- `src/plate_core/` (bootstrap.py, cli.py dispatch, github_client.py, contemplation.py, MCP entry points and schemas)
- Existing Question handling (comment patterns, batch scripts, .github/workflows for question-related automation)
- GitHub Copilot CLI slash command patterns and strong user preference for *native* TUI primitives over custom implementations
- MCP server capabilities (especially the `plate_plan_epic` stub and related planning/synthesis tools)
- Full breakdown of Epic #139 and its children (#140 Research, Designs #142–145, Features #147–157 including the blocking Question last-resort workflow)
- Prior conversation context defining the exact 4 invariants and the agent blocking pattern

## Findings

### Current State of Question / Informational Goal Handling

- Informational goals are currently handled ad-hoc as GitHub issues, sometimes using special templates or comment-driven batching.
- Partial synthesis exists via scripts and comment patterns, but there is no first-class "Question" issue type with dedicated lifecycle, provenance, or automatic linkage back to blocking work.
- Agent guidance in personas and AGENTS.md acknowledges the need but is incomplete for a closed-loop Curiosity mode.
- No durable Answer Model with indexing, provenance tracking, or easy user revisit/update paths.

### Gaps vs. the Four Critical Invariants

1. **Never lose user-provided information**: Ad-hoc Questions and context easily get lost when agents move on or sessions end.
2. **Agent can find/retrieve prior answers**: No persistent, queryable store with provenance (who answered, when, in response to which exact question version).
3. **User can change mind / revisit old questions**: No clean mechanism to update, re-open, or evolve prior informational goals.
4. **Blocking workflow support**: When any agent (on any open Issue of Design/Research scope) hits a hard informational obstacle, there is no standardized last-resort pattern: create a linked `Question` Issue, perform a structured information dump, pause the original work, and cleanly resume/merge the answer later.

### TUI / Surface Opportunities and Native Preference

Repeated explicit user clarification: wherever possible in the primary integration (GitHub Copilot CLI), prefer *native* TUI primitives (slash commands like /qanda, interactive prompts, etc.) over any custom TUI provided by plate. Custom TUI only as fallback or for direct `gh plate qanda` usage. The /qanda surface should synthesize open Questions into a prioritized, actionable list for the user.

### MCP / CLI Surfaces and Strong Reuse Opportunities

- The `plate_plan_epic` MCP stub (and related planning tools) is an excellent foundation for the Contemplation engine, priority synthesis, and Q&A session planning.
- Thin CLI wrapper (`gh plate qanda`) and deep GitHub Copilot integration (slash commands + native TUI hooks) are the primary surfaces.
- Bootstrap seeding for known/planned/applied Questions will be required for the mode to be immediately useful.
- Full MCP tool surface needed for list_questions, get_question, record_answer (with PLATE-ANSWER blocks), get_answers, synthesize_priorities, and contemplate.

### Answer Model, Provenance, and Contemplation Engine Needs

A durable store (initially YAML in `docs/curiosity/answers.yml` persisted via GitHub comments with special blocks) plus provenance is mandatory to satisfy the invariants. The Contemplation engine must, on answer ingestion:
- Update the original Question with exact question + answer + provenance.
- Create new linked tickets (Feature/Research/Design) only when genuinely warranted.
- Directly update wiki, marketing, discussions, or existing PRs when appropriate.
- Close the goal Question when complete.
- Support the special blocking/resumption case for agents that created a last-resort Question.

## Recommendation

This research closes #140 and fully unblocks the remainder of Epic #139.

Proceed to the Design children:
- #142: Answer Model & Provenance Strategy (storage, indexing, 4 invariants, blocking workflow)
- #143: Contemplation Engine contract/behavior (including blocking/resumption)
- #144: Q&A Mode UX/TUI/Trigger Surface (with strong native Copilot CLI TUI preference)
- #145: MCP/CLI Surfaces + bootstrap seeding

Then the Feature implementation slices (#147 last-resort blocking Question creation for obstacles, #148 merge answered content + resume, #149 core Contemplation runtime, #150 Answer Model implementation, #151 Q&A TUI/CLI/MCP surfaces, #152–157 supporting work including tests, docs, and baseline catalog updates).

Maintain strict PLATE discipline on the Epic: dedicated `Epic: curiosity-qanda` label + area:agent + need:docs, PLATE_SESSION_STATE JSON in the Epic body, atomic branches/PRs with correct labels + "Closes #N", required artifacts in `docs/research/` and `docs/design/`, usage reports, and human checkpoints via Epic comments.

The native TUI preference and the blocking Question last-resort workflow are critical user requirements that must be reflected throughout the Designs and implementation.

All four invariants must be satisfied by the final Answer Model + Contemplation design.
