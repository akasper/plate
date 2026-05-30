# MCP/CLI Surfaces + Bootstrap Seeding Integration — Design Spec

- **Issue:** #145
- **Designed by:** (populated via PR #146 babysit cycle addressing devin review threads)
- **Date:** 2026-05-30
- **Status:** Draft

## Problem

Design the new MCP tools, CLI command surface (`gh plate qanda` or equivalent), and bootstrap integration needed to support the full Q&A / Curiosity vision. Special attention to reuse and extension of the existing `plate_plan_epic` stub and schema.

## Constraints

- Must feel consistent with existing `gh plate` and MCP tool patterns (e.g. plate_plan_epic, plate_pr_babysit, plate_bootstrap, delegation)
- Must support the interactive planning schema already defined in `plate_plan_epic`
- Bootstrap changes must remain optional / non-breaking for existing users
- JSON output contracts for agent consumption (aligns with --json flags everywhere)
- Relationship to existing delegation and research-agent flows

## Design Decision

**New MCP tools** (implemented in plate-mcp + src/plate_core/mcp_server.py + exposed via plugin/agents):

- `plate_list_open_questions(repo?: string, labels?: string, limit?: int, include_answered?: bool)` → `{ questions: [{number, title, answer_signal, priority_score, url, last_activity, comment_count}], total }`
- `plate_synthesize_question_priority(questions: array, criteria?: string)` → ranked list + rationale (reuses synthesis logic from research agent)
- `plate_present_qanda_form(question_id: int, prefer_native: bool)` → triggers TUI/form (see UX design #144 for native Copilot vs custom decision); returns submitted answer or cancellation
- `plate_ingest_answer(question_id: int, answer_text: string, session_metadata: object)` → executes the full Contemplation contract (#143), writes Answer Model (#142), returns `{ created_issues: [...], updated_artifacts: [...], closed: bool }`

All new tools follow existing patterns: documented in plugin/agents/plate.agent.md, support JSON, registered in baseline catalog.

**CLI surface** (`gh plate` extension):

```
gh plate qanda list [--repo OWNER/REPO] [--json]
gh plate qanda ask <question-id>   # or "answer"
gh plate qanda priority [--criteria "..."]
```

Commands delegate to MCP where possible for consistency. Help text and examples included in the design artifact.

**Integration with plate_plan_epic schema:**

Extend the PLATE_SESSION_STATE JSON (stored in Epic comments) and the planning schema:

```json
{
  "phase": "...",
  "qanda_mode": true,
  "informational_goals": [
    { "question_id": 999, "priority": 0.8, "status": "open|answered", "last_answer_excerpt": "..." }
  ],
  ...
}
```

`plate_plan_epic` will surface open Questions as first-class planning items alongside Features/Research when qanda_mode active. New tools compose directly without new top-level command surface duplication.

**Bootstrap seeding integration:**

In `gh plate bootstrap --apply` (and interactive flow):

- After core setup, optional step: "Seed initial informational goals for Curiosity / Q&A?"
- Examples prompted: "What is the primary purpose of the software under development?", "Who are the target users and what problems do they face?"
- If accepted, creates a `Question` issue (labeled Question + Epic: curiosity-qanda) with initial `answer_signal` derived from prompt.
- Controlled by `--seed-qanda` flag or repo variable; fully optional, no breaking changes to existing bootstrap.
- Seeded Questions appear in subsequent `plate_list_open_questions` and planning.

**Relationship to other surfaces:**

- Reuses delegation patterns (`plate_agent_delegate`)
- Composes with PR babysit, epic planning, and question-batch flows
- JSON-first for Copilot agent consumption

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Building a completely separate planning surface from `plate_plan_epic` | Missed reuse opportunity; fragments the agent experience and schema |
| Making Q&A purely agent-internal with no dedicated CLI/MCP surface | Weaker discoverability, scripting support, and human entry points |

## Artifact

- Full proposed tool signatures with input/output JSON schemas (above + complete field docs)
- Updated `plate_plan_epic` schema extensions (delta patch)
- CLI command help text, usage examples, and --json output samples
- Bootstrap seeding design + sequence (ASCII diagram)
- Integration architecture (MCP ↔ CLI ↔ agent persona ↔ GitHub)
- Registration steps for baseline catalog and plate.agent.md

## Open Questions

- Exact wire-up of `plate_present_qanda_form` to native Copilot CLI TUI primitives (depends on UX Design #144 clarification of "prefer native")
- Whether `plate_synthesize_question_priority` lives in core or as extension (initially core for v1)

## Acceptance Evidence

- `gh plate qanda list --json` returns well-formed open Questions from a test repo
- `gh plate bootstrap` with seeding flag creates valid Question without side effects on other artifacts
- New MCP tools appear in `gh plate mcp list` and are callable from Copilot agent sessions
- `plate_plan_epic` in qanda_mode includes informational goals from the model
- All tools documented and pass existing test_mcp.py patterns

This design satisfies the scope and decision criteria in Design issue #145. It reuses existing patterns heavily and will reference the research inventory from #140 (docs/research/curiosity-qanda-inventory.md) and sibling designs (#142 storage, #143 contract, #144 UX) once available. Changes made on the existing PR branch per babysit protocol.