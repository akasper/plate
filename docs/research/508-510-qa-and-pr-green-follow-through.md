# Research: Q&A follow-through and Full PR Green ownership (#508–#512)

- **Issues:** #508, #509, #510, #511, #512
- **Date:** 2026-07-25 (updated 2026-07-26 for #509/#511/#512 closeout)
- **Status:** Closed via guidance harden + this closeout note

## Problem (session evidence)

During Epic #470 dogfood sessions:

1. **#508** — `ask_user_question` options promised "review / babysit / address feedback" but the agent advanced or merged (e.g. PR #502 path) without completing babysit + thread resolution.
2. **#509** — Q&A sometimes used plain text instead of **defaulting first** to native TUI `ask_user_question` (arrow-key forms); user had to request the configurator.
3. **#510** — "get CI passing" was executed category-by-category only after the human named the next failing gate (labels, then feedback-resolution, then tests), instead of one comprehensive pass.
4. **#511** — After addressing PR feedback, threads were not always **resolved** via encapsulated helpers, so `feedback-resolution` stayed red until the human prompted.
5. **#512** — Combined doc gap: without named checklists, agents needed sequential human corrections for TUI Q&A + full PR green.

## Root cause

Guidance already described follow-through and Full PR Green in prose (#503, #517, #519, #528), but lacked **named checklists** agents treat as hard stop criteria, and regression tests keyed to those checklist headers. Thread resolution and TUI-default rules were present but not always treated as mandatory first moves.

## Resolution

| Item | Change |
|---|---|
| #508 | `Q&A Follow-Through Checklist (#508)` in `agent_guidance.py` + persona bullet |
| #509 | Mandatory native TUI default for PLATE Q&A in guidance + AGENTS Q&A paragraph |
| #510 | `Merge Gates Checklist (#510)` under Full PR Green + persona one-pass rule |
| #511 | Encapsulated `plate_resolve_review_thread` / babysit `--act` required after address (#516/#605); AGENTS babysit steps 7–8 |
| #512 | Parent gap closed by #508–#511 package + persona/AGENTS thin pointers |
| Proof | Phrase regression tests in `tests/test_pr_babysit.py`; this closeout note |

## Related shipped surfaces

- pr-babysit / `plate_get_pr_merge_gates` / `plate_resolve_review_thread` (#516, #605)
- PR review scope (#496)
- Quiet ops + todo_write for multi-step (#515)
- AGENTS.md Default Persona, Q&A paragraph, babysit Full PR Green loop

## Non-goals

- Host TUI auto-run of checklists (still agent-owned)
- Replacing human approval for Feature/Bug merges when risk is off
- Hand-rolled GraphQL resolve mutations (agents must use helpers only)
