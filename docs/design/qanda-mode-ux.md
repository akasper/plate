# Q&A Mode UX, TUI Forms, and Trigger Surface — Design Spec

- **Issue:** #144
- **Designed by:** (populated via PR #146 babysit cycle addressing final devin review thread)
- **Date:** 2026-05-30
- **Status:** Draft

## Problem

Design the user experience and technical surface for Q&A mode — how users (and agents) enter the mode, how questions are presented, what form widgets are used, how answers are submitted, and how the mode integrates with existing Copilot CLI and `gh plate` surfaces. This completes the design artifacts for the Curiosity / Q&A Epic #139.

**Important clarification (added 2026-05-30):** When the user is interacting through the primary interface (GitHub Copilot CLI), the system must prefer using Copilot CLI's *native* TUI / interactive questioning or form capabilities (whatever primitives are available to agents/plugins) over the plate tool launching its own custom TUI, wherever such native options are available and sufficient.

## Constraints

- Must feel native to Copilot CLI users.
- Prefer terminal-first, lightweight dependencies (alignment with PLATE philosophy).
- Must support both rich interactive sessions and simple text fallback.
- Should be recordable for visual evidence (existing GIF patterns from e2e).
- Strong preference for native Copilot CLI TUI primitives in the primary interface.
- Custom TUI (e.g. gum/huh or plate-internal) only as fallback for direct `gh plate` usage or when native is insufficient.
- Non-interactive / headless fallback for CI/scripted use.
- Integration with plate agent persona, MCP tools (#145), and Contemplation contract (#143).

## Design Decision

**Trigger mechanisms (entry points):**

1. Dedicated `/qanda` slash command (in Copilot CLI and gh-plate contexts).
2. Explicit mode inside `/agent plate` ("enter Q&A / Curiosity mode").
3. Direct `gh plate qanda` CLI subcommand (for scripting/headless).
4. Optional auto-suggest from plate_plan_epic when open informational goals exist.

**Native vs. Custom TUI Decision Tree (primary rule per 2026-05-30 clarification):**

- If running inside GitHub Copilot CLI (detected via env/context/plugin):
  - Prefer native Copilot TUI/form primitives for question list + individual Q&A forms (text input, choice, multi-line, confirmation).
  - Only fall back to custom TUI if native primitives cannot express the required widget or prioritization UI.
- If running via direct `gh plate qanda` (outside Copilot):
  - Use lightweight custom TUI (e.g. based on existing patterns or minimal deps like gum/huh for cross-platform terminal forms).
- Headless / non-interactive: Always support `--json` + piped input or explicit form data flags; no TUI launched.

**Question presentation and prioritization UI:**

- List view: Prioritized open Questions (from `plate_list_open_questions` / synthesis in #145), showing title, answer_signal excerpt, priority score, last activity, link.
- Individual question screen: Full question text + history (per Answer Model #142), form for answer submission, "revise prior answer" option, cancel.
- ASCII/wireframe mockups (native Copilot style approximated; custom fallback similar):

```
Q&A Mode - Open Informational Goals (3)
────────────────────────────────────────
1. [P:0.92] What is the primary purpose of this software?          (last: 2h ago)
2. [P:0.75] Who are the target users and what problems...?         (last: 1d ago)
3. [P:0.61] How should answer provenance be captured?              (new)

Select # or (q)uit / (r)efresh / (s)earch: _
```

(Individual form:)
```
Question #999: What is the primary purpose...?
────────────────────────────────────────────────
[Full history per #142 shown abbreviated]

Your answer (multi-line; Ctrl-D or native submit when done):
> 

[Submit] [Revise prior] [Cancel] [Help]
```

**Form widget patterns:**

- Text (single + multi-line)
- Choice / single-select + multi-select
- Confirmation (yes/no + explicit)
- Optional structured fields for provenance metadata
- Revision flow: "This is a correction to my prior answer on <date>" (links via revision_of)

**Error handling, cancellation, revision:**

- Explicit cancel at any point (no partial state loss).
- Validation + re-prompt on malformed input.
- On revision: appends new answer per model; triggers Contemplation re-evaluation (#143).
- Timeouts / session expiry with clear resume guidance.

**Visual evidence / recording:**

- Leverage existing playwright-e2e + e2e-record.sh / gif-from-video patterns in plate_template and tests/e2e.
- Record native Copilot flows (where possible) + custom gh plate fallback.
- Store in docs/design or spike-videos/ as in prior PRs.

**Integration points:**

- Agent persona updates (plate.agent.md + AGENTS.md Question loop) to invoke these surfaces.
- MCP tools from #145 drive the forms (plate_present_qanda_form delegates per the native decision tree).
- Full transcript + answer ingest feeds Contemplation contract and Answer Model.

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Pure chat-based Q&A inside the agent (no structured forms) | Simple but loses structured form benefits, widget consistency, and easy revision UX |
| Separate dedicated TUI binary | Too heavy for v1; violates lightweight terminal-first philosophy |
| Using GitHub issue forms directly (no agent/TUI) | Not agent-driven enough; poor integration with Copilot CLI primary interface and Contemplation |
| Always launching custom terminal TUI even in Copilot CLI | Violates the explicit native-experience preference clarification (2026-05-30) |

## Artifact

- Trigger and entry point design with the native-Copilot vs. custom-TUI decision tree (this document)
- Wireframes / ASCII mockups of list view + individual question + form screens (above + expanded in full doc)
- Widget pattern catalog + headless fallback spec
- Error/cancellation/revision flows
- Visual demo/GIF requirements and recording integration notes
- Cross-references to #142 (storage/provenance), #143 (contract), #145 (MCP/CLI surfaces + bootstrap)

## Open Questions

- Exact detection mechanism for "inside Copilot CLI" context (env var, plugin API surface, or MCP call).
- Depth of native form primitive support (may require coordination with Copilot team for richer widgets).

## Acceptance Evidence

- In a Copilot CLI session, `/qanda` or agent mode uses native forms (no custom TUI launched) and records clean GIF via existing harness.
- Direct `gh plate qanda ask <id>` launches appropriate fallback TUI or headless path.
- Full answer submission flows through to Answer Model write + Contemplation actions with correct provenance.
- Revisions append correctly without losing history.
- All flows documented in AGENTS.md and agent personas; pass E2E recording verification.

This design satisfies Design issue #144 (including the native preference clarification) and completes the four required design artifacts for Epic #139 children. It directly addresses the final placeholder violation in the devin review thread (original databaseId 3328893056). Cross-references research inventory #140 (pending) and all siblings. All changes on the existing PR branch. (1 code change this babysit cycle; cap respected.)

(The prior three design files were already populated in commit d3f4d40f8518c7a58ba3d9ec6ee6fef86aeb0c43.)