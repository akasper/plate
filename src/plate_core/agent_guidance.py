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
6. For hard informational obstacles during other work, create a blocking `Question` issue (with a clear structured information dump) as a deliberate last resort, post a status on the original Issue, and pause work on it.
7. When a blocking Question is later answered, offer to merge the new information back into the original Issue and resume the blocked work.

### Blocking / informational obstacle pattern
When you cannot safely proceed on a task (Research, Design, Feature, etc.) without additional human clarity:
- Create a linked `Question` issue.
- Include a thorough but concise information dump (current understanding, exact blocker, what input would unblock you).
- Update the original Issue with a clear "paused pending answer to Question #N" comment.
- Do not continue significant work on the original Issue in the same session.

### Resumption pattern
When you (or a future session) see that a previously blocking Question has been answered:
- Retrieve the answer + provenance.
- Merge the key information into the original Issue (via comment and/or targeted updates).
- Resume or unblock the original work, producing a clear "unblocked by answer to Question #N" record.

### Related MCP tools (examples)
- Future tools for listing/synthesizing Questions, recording answers, triggering contemplation, and managing blocking/resumption flows.
- Always prefer the most native user experience the host environment (Copilot CLI) can provide.
"""


def get_agent_guidance_sections() -> dict[str, str]:
    """Return guidance sections for agents."""
    return {
        "playwright_e2e": PLAYWRIGHT_E2E_GUIDANCE,
        "qanda_curiosity": QANDA_CURIOSITY_GUIDANCE,
    }
