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

### Question handling flow (v2.1 Contemplation Engine)
1. Use available MCP tools (or future equivalents such as `plate_list_questions`, `plate_get_question`) to discover and prioritize open Questions.
2. Present the question using the native preference above.
3. When the user provides an answer, capture it with full provenance (see Answer Model).
4. **Trigger Contemplation Engine v2.1** (via MCP tools or rules):
   - Parses `answer_signal` from Question body (supports checklist, artifact, keyword formats per #326)
   - Evaluates accumulated evidence against signal criteria
   - Produces full transcript with citations
   - Creates typed child issues (Feature/Research/Design) with back-refs when gaps identified
   - Only signals close when answer_signal is verifiably met (evidence-based with confidence)
   - Includes mandatory === USAGE REPORT === block on closure per AGENTS.md
5. Create forward progress (new issues, artifact updates) as defined in the Contemplation contract.
6. For hard informational obstacles during other work, create a blocking `Question` issue (with a clear structured information dump) as a deliberate last resort, post a status on the original Issue, and pause work on it.
7. When a blocking Question is later answered, the v2.1 engine merges the new information back into the original Issue with an auditable unblock report and resumes the blocked work.

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

### Resumption pattern (Feature #148 / Epic #139 / v2.1 enhancement)
When you (or a future session) detect that a previously blocking Question (one containing PLATE-BLOCKING-DUMP or explicit "blocking" marker + link to original Issue) has been answered:
1. Use `plate_get_question` + `plate_get_answers` (or record_answer path) to fetch the full answer + provenance from the blocking Question.
   - Prefer the committed fast path from `plate_get_answers` when `docs/curiosity/answers.yml` and `docs/curiosity/answers/*.md` are present.
   - If you are working from historical Questions that predate committed storage, run `plate_backfill_answers` (or `gh plate qanda --backfill`) once before synthesis/resumption.
2. Identify the original blocked Issue from the dump/block (or Question body links).
3. **Trigger Contemplation Engine v2.1** on the answer — the engine will:
   - Evaluate the answer against signal criteria
   - Create typed child issues if gaps remain
   - Post a structured "Unblocked by answer to Question #N" report on the original Issue with:
     * Answer excerpt and evaluation status
     * List of created follow-up issues
     * Next steps guidance
     * Full provenance link
4. Update the original Issue body/sections/comments with the new info where it changes scope/understanding (append-only where possible).
5. Resume or hand off work on the original Issue (or mark it ready for next agent).
6. Close the blocking Question only if its answer_signal is met (normal contemplation closure).

**MCP integration**: The `plate_record_answer` (source=\"blocking\") + contemplation path, or a dedicated `plate_resume_from_blocking_question` tool (to be added), triggers the above. Always produce auditable unblock report. Preserve full bidirectional traceability. No data loss.

This completes the loop started by #147 creation. Dogfood the full create → answer → resume in this repo.

### v2.1 Contemplation Engine specifics
The v2.1 engine (Feature #343 / Epic #257) provides:
- **Real signal parsing**: Extracts answer_signal from Question body in checklist format (`- [ ] item`), artifact format (mentions `docs/`, `commit`, etc.), or keyword format
- **Evidence-based evaluation**: Checks accumulated answers against parsed criteria, provides citations from answer excerpts
- **Strict closure**: Only signals close when signal is met with medium-to-high confidence; includes === USAGE REPORT === per AGENTS.md
- **Typed child creation**: Creates Feature/Research/Design issues based on identified gaps in answers, with full back-refs to parent Question
- **Enhanced resumption**: Blocking Question answers trigger detailed unblock reports on original Issues with evaluation status and created children

### Related MCP tools (examples)
- Future tools for listing/synthesizing Questions, recording answers, triggering contemplation, and managing blocking/resumption flows.
- Always prefer the most native user experience the host environment (Copilot CLI) can provide.
"""


INFORMATION_AUDIT_GUIDANCE = """
## Information Audits and Goals Page (Epic #218, #221 core engine, #222 defaults catalog)

PLATE supports proactive Information Audits to discover Informational Goals (gaps against the project's high-level Goals) and generate well-formed `Question` issues.

### When to perform an Information Audit
- At start of Epic or major task, or periodically (e.g. via `plate_perform_information_audit` or equivalent).
- When the Goals page or context seems stale/missing signals for prioritization or Question generation.
- To seed or refine open Questions for Curiosity/Q&A mode.
- Scoped by agent_type (general, marketing, engineering) or scope (repo, epic, etc.).

### How to run
- Prefer MCP tool `plate_perform_information_audit` (or future gh plate / Copilot surface).
- Start with `dry_run: true` to review proposals before creating Issues.
- Set `include_defaults: true` to incorporate platform + extension defaults from the catalog (#222).
- Provide `agent_type` for specialized scoping/heuristics.
- Use `max_questions` to cap output.

### Inputs to use
- The Wiki `Goals` page (per convention #219/#224) as primary strategic signal: read Mission, Core Principles, How We Intend to Succeed, Current State & Evidence, Open Questions.
- Other surfaces: code patterns, open issues/PRs/discussions, existing Questions, bootstrap state.
- Never assume Goals page is the *only* source (per contract rule #1).

### Output and Question generation (per #220 model)
- Proposed Questions include:
  - title/body following Question template + provenance (where gap noticed, e.g. "Goals § Mission", specific file/issue), related_goals, priority_rationale, refinement_note.
  - Use PLATE-INFORMATIONAL-GOAL markers for Answer Model / Contemplation compatibility.
- Link back to originating Goal(s) and forward to artifacts that should be updated on resolution.
- Support continuous refinement: broad → specific; detect clusters of related Questions.

### Best practices and integration
- Quality over quantity: use heuristics + reasoning to avoid noise; cap and prioritize.
- After audit, feed proposals into Curiosity flows (list/prioritize/present via native TUI or gh plate qanda, record answers, contemplate).
- Contribute back: if audit reveals missing/stale Goals page content, propose updates or new high-level goals.
- For hard obstacles during audit or other work, fall back to blocking Question pattern (#147).
- When blocking Question answered, resume via unblock report + merge (as in Q&A section).

### Examples
- General audit: `plate_perform_information_audit --dry-run --include-defaults` → review 3-5 high-signal Questions tied to Mission/risks.
- Marketing agent: scope to users/GTM gaps, produce Questions for personas or value prop.
- After Goals page populated: re-audit to surface "Current State & Evidence" gaps or risks.

See design #223 for the 10 enforceable behavior rules (open-ended, provenance, refinement, quality, scoping, defaults+extensibility, integration, auditability, human-in-loop, wiki as strategic home).

Use the catalog (`plate_informational_goals`) to inspect defaults.

**MCP tools (core):**
- `plate_perform_information_audit` (dry_run, scope, agent_type, max_questions, include_defaults)
- `plate_informational_goals` / `plate_informational_goal <id>` (from #222 catalog)
- Existing Curiosity tools for follow-up (list/get/record/prioritize/contemplate/blocking/resume).

Always produce auditable output (logs, provenance). Prefer native Copilot TUI for presenting proposals if available.
"""

def get_agent_guidance_sections() -> dict[str, str]:
    """Return guidance sections for agents."""
    return {
        "playwright_e2e": PLAYWRIGHT_E2E_GUIDANCE,
        "qanda_curiosity": QANDA_CURIOSITY_GUIDANCE,
        "information_audit": INFORMATION_AUDIT_GUIDANCE,
    }
