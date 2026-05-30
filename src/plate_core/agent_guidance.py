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
- `@copilot validate-e2e-tests` — Verify Playwright setup is correct

### Documentation

See [Playwright E2E Guide](../docs/playwright-e2e-guide.md) for detailed setup and patterns.
"""


QANDA_CURIOSITY_GUIDANCE = """
## Curiosity / Q&A Mode (Epic #139, Design #144)

The plate agent supports Curiosity and Q&A flows for gathering context and answering repository questions via interactive sessions.

### Native TUI Preference (Primary Integration Interface)

When the user is in GitHub Copilot CLI (the primary integration interface for this agent), the plate agent and tools **must prefer Copilot CLI's native TUI / interactive questioning or form capabilities** over launching a custom TUI (gum, etc.), wherever native options are available and sufficient.

This ensures the most seamless possible experience for users without spawning external processes or context switches.

### Constraints
- Must operate inside existing Copilot CLI session.
- Prefer zero-dependency native prompting (questions, selects, text inputs) provided by the host CLI.
- Only fall back to subprocess TUI launchers when native capabilities are demonstrably insufficient for the required interaction complexity.
- Keep guidance reusable across agent surfaces (Copilot CLI, MCP, etc.).

### TUI Technology Recommendation
- **Preferred**: Native Copilot CLI interactive features (question prompts, forms, multi-selects where exposed by the CLI runtime).
- **Fallback only**: Minimal custom TUI via approved libraries if native surface lacks required widget; document the specific gap.

### Alternatives Rejected
- Always using gum or equivalent custom TUI for Q&A: rejected because it breaks the seamless experience inside the primary Copilot CLI interface and introduces unnecessary process/TTY overhead.
- Building a full custom TUI in the agent itself: rejected for scope and duplication with host CLI capabilities.

See also: plugin/agents/plate.agent.md (workflow item 11 and behavior rule 7) and docs/design/qanda-mode-ux.md.
"""


def get_agent_guidance_sections() -> dict[str, str]:
    """Return guidance sections for agents."""
    return {
        "playwright_e2e": PLAYWRIGHT_E2E_GUIDANCE,
        "qanda_curiosity": QANDA_CURIOSITY_GUIDANCE,
    }
