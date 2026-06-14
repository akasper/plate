"""Agent guidance and prompting strategies for PLATE development."""

from __future__ import annotations


PLAYWRIGHT_E2E_GUIDANCE = """
## Playwright E2E Testing

PLATE repos have built-in Playwright E2E support for testing UI features.

### Workflow: Implementing a UI Feature

When implementing a UI feature, follow these steps:

1. **Write or update Playwright test** in `tests/e2e/specs/`
   - Use the existing test structure and page objects in `tests/e2e/pages/`
   - Run: `npm run test:e2e` to validate tests locally

2. **Record a demo with headed mode**
   - Run: `npm run test:e2e:headed` to see the test in action
   - Or use: `npm run record:e2e <feature-name>` to record and generate GIF

3. **Generate GIF and commit**
   - The GIF is generated in `tests/e2e/fixtures/gifs/`
   - Commit the GIF to track visual changes
   - Reference in CURRENT.md with embed + test link

4. **Update CURRENT.md**
   - Embed the GIF: `![Feature Demo](tests/e2e/fixtures/gifs/feature-name.gif)`
   - Link to test: `[View test](tests/e2e/specs/feature-name.spec.ts)`
   - Document the feature behavior

5. **Push and create PR**
   - PR will include visual demo and linked test

### Available Commands

- `npm run test:e2e` — Run all tests headless
- `npm run test:e2e:watch` — Watch mode for development
- `npm run test:e2e:headed` — Run with visible browser
- `npm run test:e2e:debug` — Debug mode
- `npm run record:e2e <name>` — Record test and generate GIF

### MCP Tools

Use these MCP tools when implementing E2E tests:

- `@copilot init-playwright` — Scaffold Playwright setup if missing
- `@copilot record-e2e-gif` — Record and generate demo GIF for a test
- `@copilot validate_e2e_tests` — Verify Playwright setup is correct

### Documentation

See [Playwright E2E Guide](../docs/playwright-e2e-guide.md) for detailed setup and patterns.
"""


QANDA_CURIOSITY_GUIDANCE = """
## Curiosity / Q&A Mode and Informational Goals

PLATE supports a Curiosity-driven workflow where informational goals are tracked as `Question` issues and surfaced through Q&A mode.

### When to use Q&A mode
- The user explicitly invokes `/qanda`, "answer open questions", or similar.
- You detect multiple open `Question` issues relevant to the current Epic or task.
- You need structured user input to unblock work or seed new work.

### How to present questions (critical preference)
- **Inside GitHub Copilot CLI (primary interface):** Strongly prefer using any *native* TUI, form, or interactive questioning primitives provided directly by the Copilot CLI itself. Only fall back to a custom terminal TUI if native capabilities are unavailable or insufficient for the question.
- **Direct `gh plate qanda` usage or fallback:** Use lightweight custom TUI tools (e.g. gum/huh) or simple prompts.
- The goal is the most seamless possible experience for the user in their primary interface.

### Question handling flow
1. Use available MCP tools (or future equivalents such as `plate_list_questions`, `plate_get_question`) to discover and prioritize open Questions.
2. Present the question using the native preference above.
3. When the user provides an answer, capture it with full provenance (see Answer Model).
4. Trigger contemplation logic (via MCP tools or rules) and produce a Contemplation Log.
5. Create forward progress (new issues, artifact updates) as defined in the Contemplation contract.
6. Treat the Question body's `Answer signal` as checklist-style markdown criteria. A Question is only ready to close when every checklist item is backed by explicit citations or links in the effective answer history; revised answers can invalidate previously satisfied items until new cited evidence exists.
7. For hard informational obstacles during other work, create a blocking `Question` issue (with a clear structured information dump) as a deliberate last resort, post a status on the original Issue, and pause work on it.
8. When a blocking Question is later answered, offer to merge the new information back into the original Issue and resume the blocked work.

### Blocking / informational obstacle pattern (Feature #147 / Epic #139)
**Decision procedure (invoke ONLY as deliberate last resort):**
1. You have performed internal reasoning + used available tools/MCP calls (reads, searches, contemplation on prior answers, etc.) and still cannot safely proceed without risking incorrect work or violating requirements/scope.
2. The blocker is informational (ambiguity, missing context, human judgment needed on tradeoffs/risks/users, conflicting signals) — not a simple implementation detail you can experiment on.
3. Continuing would violate "never lose information" or "create forward progress" invariants, or risk significant rework.
4. No open Question already covers this exact need.

When criteria met:
- Call `plate_create_blocking_question` (MCP) with:
  - original_issue_number (the blocked task)
  - blockage_point (exact sentence/requirement/step where stuck)
  - missing_info (what human must clarify)
  - suggested_questions (2-5 crisp questions for the human; this becomes the Question title/body focus)
  - partial_work (what you have done/understood so far — never lose this)
  - extra_context (links to artifacts, prior answers, etc.)
- The tool creates the Question (with structured PLATE-BLOCKING-DUMP per Answer Model style), posts a standardized pause status on the original Issue with bidirectional link, and returns the new Question #.
- Surface the new Question # to the user (mention in chat, or use Q&A mode).
- **Discontinue** further work on the original Issue in this session. Hand off cleanly.
- Later (after human answers): see Resumption pattern below + #148.

This is the concrete last-resort escape hatch. Over-use is a risk — prefer reasoning first. Document the decision in your reasoning trace.

### Resumption pattern (Feature #148 / Epic #139)
When you (or a future session) detect that a previously blocking Question (one containing PLATE-BLOCKING-DUMP or explicit "blocking" marker + link to original Issue) has been answered:
1. Use `plate_get_question` + `plate_get_answers` (or record_answer path) to fetch the full answer + provenance from the blocking Question.
2. Identify the original blocked Issue from the dump/block (or Question body links).
3. Perform structured merge:
   - Post a clear, human/machine-readable "**Unblocked by answer to Question #N**" report comment on the original (key excerpts, provenance, link back, actions taken).
   - Update the original Issue body/sections/comments with the new info where it changes scope/understanding (append-only where possible).
   - Create any follow-on artifacts or child issues warranted by the new information (via normal contemplation rules).
4. Resume or hand off work on the original Issue (or mark it ready for next agent).
5. Close the blocking Question only if its answer_signal is met (normal contemplation closure).

**MCP integration**: The `plate_record_answer` (source=\"blocking\") + contemplation path, or a dedicated `plate_resume_from_blocking_question` tool (to be added), triggers the above. Always produce auditable unblock report. Preserve full bidirectional traceability. No data loss.

This completes the loop started by #147 creation. Dogfood the full create → answer → resume in this repo.

### Related MCP tools (examples)
- Future tools for listing/synthesizing Questions, recording answers, triggering contemplation, and managing blocking/resumption flows.
- Always prefer the most native user experience the host environment (Copilot CLI) can provide.
"""


def get_agent_guidance_sections() -> dict[str, str]:
    """Return guidance sections for agents."""
    return {
        "playwright_e2e": PLAYWRIGHT_E2E_GUIDANCE,
        "qanda_curiosity": QANDA_CURIOSITY_GUIDANCE,
        "information_audit": INFORMATION_AUDIT_GUIDANCE,
        "quiet_operations": QUIET_OPERATIONS_GUIDANCE,
    }


INFORMATION_AUDIT_GUIDANCE = """
## Information Audits and Goals Page

PLATE supports structured Information Audits (Epic #218 / #221, cross-cutting beta roadmap) to keep SPEC.md aligned with implemented state (release fragments as durable evidence, working tests as strong signal, code/docs/wiki as supporting).

- Evidence hierarchy and owner-vision intake (via Q&A where needed).
- Auditable reports: stale claims, undocumented implementation, vision/reality gaps, with per-finding confidence (high/medium/low).
- Generates follow-on artifacts (Question/Research/Design/Feature/Bug/Doc) with provenance; supports draft SPEC patches (insertion-first).
- Exposed via `plate_perform_information_audit` (CLI + MCP), health signals, and `plate_what_next` prioritization when findings exist.
- Human approval boundaries preserved for public claims/vision/SPEC changes.

Use when drift is suspected or after landing beta Epics. See docs/research/ and the 257/221 fragments for details. Ties into Goals page bootstrap (#224) and extension goals.
"""


QUIET_OPERATIONS_GUIDANCE = """
## Quiet Operations, Brevity, and Comment Discipline (Long-Running / Looped Agents)

PLATE supports long-running autonomous operation (e.g. Copilot CLI `/every`, Grok Build `/loop`, babysit watch, repeated what_next cycles). The default posture must be quiet: protect both the human reader's attention and every agent's context window.

### Terminal / loop turn summaries (highest priority)
- When operating in any looped or long-running session, your *final visible response* (the part the /loop orchestrator, watch mode, or human tailing the terminal will see) **MUST** be a bullet-point list.
- Each bullet is **one brief sentence**.
- No introductory paragraphs, no "Summary of this turn:", no "I did X because...", no closing zinger or sign-off.
- If the turn produced multiple observations, use 1-5 (max ~7) bullets.
- Pure no-op / monitoring example (clean babysit turn):
  - Babysit PR #123: 0 actionable threads, base branch in sync (UP TO DATE).
  - No GitHub comment posted (quiet rule: only on meaningful forward progress).
  - Used MCP plate_pr_babysit for structured data; any CLI output was collapsed internally.
- True nothing example: "- No-op turn: state unchanged, 0 progress items."
- Prefer MCP surfaces (plate_pr_babysit, plate_health, plate_epic_status, plate_what_next, etc.) that return clean dicts. When you must invoke a CLI command that produces multi-line human output, collapse or ignore the raw text and emit only the terse bullets.

### GitHub comments on Issues, PRs, and Questions
- Post a comment **only** when the turn produces verifiable forward progress that creates or updates a durable repository artifact, resolves a blocker, or satisfies a defined human checkpoint.
- Progress examples (allowed/encouraged):
  - Code change committed locally and pushed to the PR branch.
  - Review thread resolved via `plate_resolve_review_thread` (or equivalent GraphQL).
  - New or updated `.agentic/releases/unreleased/*.json` fragment, wiki source, or other required artifact.
  - New child issue (Feature/Research/Design/Question) created from contemplation that advances Epic scope.
  - Blocking Question created as a deliberate last resort (#147), with pause status on the original.
  - Unblock report posted on an original issue after a blocking Question is answered (#148).
  - Answer that newly satisfies one or more Answer signal checklist items, making the Question PR-ready (the closure report with usage block is the required artifact).
- Do-not examples (forbidden in loops / routine turns):
  - Pure monitoring: babysit_pr report shows 0 actionable_threads and no sync change.
  - Routine contemplation: evaluated Answer signal, no new criteria satisfied, no artifacts created.
  - "Re-checked health / release status / epic status."
  - Status updates or "still working" notes in a watch/loop.
- The engine's own PLATE-ANSWER / PLATE-CONTEMPLATION / PLATE-BLOCKING-DUMP markers and required usage-report blocks on closure are **exempt** (they are the auditable record per Issue Artifact Rules). Do not add your own prose comments around routine ones.
- Human checkpoints remain (e.g. "Post a summary comment on the Epic issue when all child issues are resolved"). These are explicit, not routine.

### Q&A / Curiosity question presentation
- When invoking native interactive primitives (ask_user_question or host TUI forms) or falling back: transmit **only** the question text, the Answer signal checklist (if present), and the absolute minimum options or context required for the decision.
- Omit all front matter except when the question is *itself about* process rationale or vision: no "As the PLATE agent working on Epic #N...", no "To make progress toward the Goals page...", no "Per the QANDA_CURIOSITY_GUIDANCE...".
- The host session already carries full context (current Epic, recent artifacts, prior answers). Extra framing wastes human attention and inflates context for any agent that later reads the transcript.

### General rules
- Briefer is better for humans *and* for any downstream agent or orchestrator that ingests this turn's output.
- "Update the artifact, not chat history" (echoes copilot-instructions and layered context design).
- Resource consciousness (AGENTS.md) + Atomic PR discipline still apply; quiet rules make them practical for overnight / multi-hour autonomous runs.
- These rules are enforced primarily through the plate persona, catalog constraints on delegated agents, and what_next / delegation prompt segments. See also AGENTS.md §Resource consciousness, §Human checkpoints, §Issue Artifact Rules, and the babysit / Curiosity sections.

### Long-running command / background task protocol
When using or encountering backgrounded commands (e.g. `run_terminal_command(..., background=true)`, host-initiated long pytest in worktree, babysit repro, or any long-running verification):
- **Immediately record the task_id** (or identifier) returned by the backgrounding call or system reminder.
- **Schedule proactive polling**: do not wait for system reminders. Explicitly plan and invoke `get_command_or_subagent_output` (or the `monitor` tool) at intervals (e.g., after 30s, 2m, 5m, 10m) to surface partial output, progress, and early failures in your (terse) responses. At each poll, emit a terse one-bullet status update to the user (e.g., "still running after 2m, last output: ...") to close the visibility loop. Consider using or defining a lightweight "monitor" helper that the agent can invoke to handle scheduling and reporting for background tasks.
- If the task is killed by the system (e.g. SIGTERM / signal 15 after hours, timeout, OOM), or exceeds a practical threshold (e.g. >10min for verification), **treat the kill as data, not "the end"**:
  - Immediately retrieve the final/partial output via the get/monitor tool.
  - Analyze it (often the useful work/failure was completed before the kill).
  - Switch *immediately* to a cheap, targeted fallback (e.g. `pytest -k "exact failing test from CI log or partial output" --tb=line`, single file, or the minimal repro from the original CI job). Never blindly re-background a full expensive suite.
- In "pr-babysit", "get CI passing", "reproduce the failure (in worktree)", or equivalent flows: **default to cheap, CI-log-driven reproduction first** (use `gh run view` on the specific failing job to extract the exact -k filter, file, or error; run only that). Reserve broad backgrounded commands for last resort, and always with the monitoring + fallback plan above.
- The pr-babysit skill, "reproduce failure in worktree" guidance, and any verification instructions must encode this preference for log-first, kill-aware, cheap fallbacks over expensive long runs.

This protocol prevents wasted compute and ensures partial results from killed tasks are acted upon quickly. Agents must proactively use `get_command_or_subagent_output` / `monitor` rather than reacting to reminders.

### CI Diagnosis First Protocol (before expensive local verification or repro)
When the high-level instruction is "get CI passing", "reproduce the failure (in worktree)", "fix the red checks", "address feedback", or any verification/babysit task that might involve local commands (especially broad pytest in worktrees):

- **Always begin with cheap, precise GitHub-side diagnosis *before* launching any broad or long-running local command.** Never default to `python -m pytest ...` or similar without first knowing the exact current failure from CI.

  1. Run `gh pr checks <pr-number>` (or use MCP `plate_pr_babysit` / `gh plate pr babysit`) to see the full current set of gates and which are red (labels, feedback-resolution, test jobs, etc.).

  2. Identify the *specific failing job/run*: use `gh run list --branch <pr-head-branch> --limit 5` (or the equivalent from babysit report).

  3. Fetch the exact failure details with `gh run view <run-id> --job <job-id> --log-failed` (or `--log` for full; add `--json` for structured parsing). This shows the *real* error (often "missing Bug label", "unresolved threads from owner", or a specific test assertion), not an old/stale one.

- Only *after* the precise diagnosis (e.g. "the failure is the labels check, not the tests"), decide the minimal repro scope if local work is needed at all: targeted `pytest -k "exact-test-name"`, single file, or just the metadata fix. Prefer cheap one-liners over multi-hour full suites.

- Use (or document) common one-liners/helpers for the gh run view flags so they don't have to be memorized each time.

- Cross-reference the "Full PR Green / Make Mergeable Loop" (inspect all gates including these) and the long-running protocol (cheap fallback, record task_id if backgrounding any repro).

This is the primary way to avoid wasted expensive local runs and delayed diagnosis. The pr-babysit skill and "reproduce failure" guidance must encode "CI diagnosis first" as the mandatory starting step.

### Full PR Green / Make Mergeable Loop (for "get CI passing", babysit, address feedback)
When given instructions like "get this PR green", "make mergeable", "address all feedback", or "resolve CI":

1. At the start and after *every* push, comprehensively inspect *all* current failing gates using available surfaces (MCP plate_pr_babysit or `gh plate pr babysit`, `gh pr checks`, review threads via GraphQL or tool, labels, mergeStateStatus, title/doc checks, etc.). Build and maintain an internal model of the "current failing gates" (do not rely on user to diagnose the next one).

2. Address everything the agent can autonomously in the worktree:
   - Base sync (rebase or request copilot update per strategy).
   - Apply safe code suggestions from reviews.
   - Fix labels, title, or other metadata issues within scope.
   - Resolve review threads that have been addressed (via `plate_resolve_review_thread`).
   - Reproduce and fix test/CI failures that are locally actionable (prefer cheap targeted runs per long-running protocol).
   - (and any other gate surfaced by the comprehensive inspection at step 1)

3. Push all changes to the *existing* PR branch (never open a new PR for feedback response).

4. Re-inspect all gates.

5. Repeat the inspect-fix-push-reinspect cycle until no more agent-actionable items remain (only human-judgment items remain, e.g. credentials, high-risk decisions, or owner CHANGES_REQUESTED).

6. Only then produce the one-sentence summary for the human of what is left + current state. Use terse quiet output for loops.

For any PR health / conflict / feedback / 'get green' work, start by using the dedicated pr-babysit skill (gh plate pr babysit or plate_pr_babysit MCP) rather than hand-rolling raw git + gh commands. Use the dedicated `gh plate pr babysit` (or MCP `plate_pr_babysit`) surface by default. Escalate with `need:human-review` label + blocking comment for judgment items. This gives the agent ownership of the full "mergeable" state instead of sequential single-category fixes waiting for user prompts.

The pr-babysit skill should support (or be used in) a "until green" / comprehensive make-mergeable flow with the above loop, appropriate quiet reporting, and clear human escalation points.

Use this section for any monitoring, babysitting, contemplation, or repeated what_next work. The goal is dramatically less noise in Issues and terminals while preserving every required traceable artifact.
"""
