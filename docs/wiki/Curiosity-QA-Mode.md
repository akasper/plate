# Curiosity / Q&A Mode

**Epic:** [#139](https://github.com/akasper/plate/issues/139) (label `Epic: curiosity-qanda`)

Informational goals are first-class citizens in PLATE, captured as `Question` issues and driven through a structured Q&A / Contemplation loop that guarantees the four invariants:

- Never lose user-provided information
- The agent can reliably find previous answers
- Users can revisit, revise, or correct prior answers
- Every answer drives forward progress (new issues, artifact updates)

## Core Flows

### 1. Normal Q&A
- Discover/prioritize via `plate_list_questions` + `plate_synthesize_priorities` (or `gh plate qanda --list`).
- Present using **native host primitives** (Copilot CLI TUI/forms preferred per Design #144) or `gh plate qanda` fallback (now with basic interactive prompting).
- Record via `plate_record_answer` (or `gh plate qanda --record`).
- Contemplation Engine (#149) appends full transcript (Answer Model #150 provenance), creates forward-progress issues/artifacts, closes only when `answer_signal` verifiably met.

### 2. Blocking / Last-Resort Obstacle Handling (#147)
When an agent hits a hard informational obstacle on any open Issue (Research/Design/Feature/etc.):

1. After exhausting internal reasoning + tools, call `plate_create_blocking_question` (original_issue + blockage_point + missing_info + suggested_questions + partial_work).
2. Tool creates linked `Question` with structured `PLATE-BLOCKING-DUMP` (Answer Model style), posts standardized "Paused for human input" status on the original, returns the new Question #.
3. Agent surfaces the Question # to the user and **discontinues** work on the original in that session.

Decision procedure and exact format are in `QANDA_CURIOSITY_GUIDANCE` (in `src/plate_core/agent_guidance.py`) and `plugin/agents/plate.agent.md`.

### 3. Resumption / Merge (#148)
When a human answers a blocking Question:

- Record answer (source="blocking" recommended).
- Contemplation detects the blocking marker/dump, posts a clear "**Unblocked by answer to Question #N**" report on the original Issue (excerpt + provenance + link + resumption note).
- Merge key information into context (report is the auditable minimum; body updates and follow-on children follow normal contemplation rules).
- Resume or hand off the original work.

Full bidirectional traceability is preserved via comments, markers, and links.

## Surfaces
- **MCP tools**: `plate_list_questions`, `plate_get_question`, `plate_record_answer`, `plate_get_answers`, `plate_synthesize_priorities`, `plate_create_blocking_question`, `plate_contemplate` (and `plate_resume` patterns via the engine).
- **CLI**: `gh plate qanda` (list / view / interactive record / synthesize). Primary experience inside Copilot CLI uses native forms + the plate agent + MCP.
- **Guidance**: Centralized in `QANDA_CURIOSITY_GUIDANCE`; referenced from personas and AGENTS.md.

## Key Artifacts (delivered in the Epic)
- Designs: #142 (Answer Model), #143 (Contemplation contract), #144 (UX + native TUI preference), #145 (MCP/CLI surfaces).
- Research: #140 + `docs/research/curiosity-qanda-inventory.md`.
- Impl PRs: #210 (#147 creation), #211 (#148 resumption), #213 (#151 interactive fallback + native enforcement), #214 (#155 tests), plus earlier slices (#160 guidance, #162 Answer Model, #163 MCP, #164 engine).
- Release notes: `.agentic/releases/unreleased/` entries for each Feature slice.

## Usage Example (blocking + resume loop)
See the comments and traces on Issues/PRs under label `Epic: curiosity-qanda` (and the parent #139 history) for live dogfood examples created during autonomous implementation.

## Open / Future
- Richer TUI widgets (choice, multi-step) and MCP "native hint" signaling (#151 follow-up).
- Full E2E + GIF evidence (#155 / #156).
- Baseline catalog skills for the new flows (#157).
- Wiki sync and more living examples.

Maintained as part of the PLATE Curiosity vision. All changes followed strict atomic PR discipline with usage reports and human checkpoints.