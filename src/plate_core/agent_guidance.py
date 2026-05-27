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


def get_agent_guidance_sections() -> dict[str, str]:
    """Return guidance sections for agents."""
    return {
        "playwright_e2e": PLAYWRIGHT_E2E_GUIDANCE,
    }
