# Task Management

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Task Management (for agents)

The plate persona and all delegated agents **must** use the `todo_write` tool (or host equivalent) for any complex multi-step PLATE work with 3+ steps. This includes:

- Babysit / "get this PR green" / full feedback resolution sessions (inspect gates, address threads via encapsulated helpers, targeted fixes, re-babysit, merge, release sync).
- Interactive Q&A, contemplation, or Epic refinement rounds.
- Delegation packets, subagent work, information audits, or autonomy procedures.
- Any release ceremony step or long ceremony.

**Rules:**
- Invoke `todo_write` **at the very start** of the effort with a clear list (id, content, status).
- Mark each item `completed` **immediately** when that step finishes. **Never batch** multiple completions.
- Use statuses and content to give the user live visibility and to record blockers (e.g. `need:human-review`).

**Examples in context:**
- For babysit of a PR: list items like "run CI diagnosis + get_pr_merge_gates", "use plate_get_actionable_review_threads + resolve addressed via plate_resolve_review_thread", "push to existing branch", "re-babysit until CLEAN", "merge + reset release".
- For Q&A: "present via native ask_user_question", "record answer + create artifacts per AC", "complete chosen option follow-through before offering more" (if option promises review/babysit/address feedback, use pr-babysit skill in worktree to execute fully before next; never advance unaddressed). (Addresses #503.)

This is now part of the plate default persona (see Special modes) and agent_guidance TASK_MANAGEMENT_GUIDANCE. Failure to use it for qualifying work is a drift from #515.
