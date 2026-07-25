# Research: Q&A follow-through and Full PR Green ownership (#508, #510)

- **Issues:** #508, #510
- **Date:** 2026-07-25
- **Status:** Closed via guidance harden (this PR)

## Problem (session evidence)

During Epic #470 dogfood sessions:

1. **#508** — `ask_user_question` options promised "review / babysit / address feedback" but the agent advanced or merged (e.g. PR #502 path) without completing babysit + thread resolution.
2. **#510** — "get CI passing" was executed category-by-category only after the human named the next failing gate (labels, then feedback-resolution, then tests), instead of one comprehensive pass.

## Root cause

Guidance already described follow-through and Full PR Green in prose (#503, #517, #519, #528), but lacked **named checklists** agents treat as hard stop criteria, and regression tests keyed to those checklist headers.

## Resolution

| Item | Change |
|---|---|
| #508 | `Q&A Follow-Through Checklist (#508)` in `agent_guidance.py` + persona bullet |
| #510 | `Merge Gates Checklist (#510)` under Full PR Green + persona one-pass rule |
| Proof | Phrase regression tests in `tests/test_pr_babysit.py` |

## Related shipped surfaces

- pr-babysit / `plate_get_pr_merge_gates` / `plate_resolve_review_thread` (#516, #605)
- PR review scope (#496)
- Quiet ops + todo_write for multi-step (#515)

## Non-goals

- Host TUI auto-run of checklists (still agent-owned)
- Replacing human approval for Feature/Bug merges when risk is off
