# Copilot Instructions

## Build, test, and lint

The implementation stack has not yet been selected (see the open Research issue). `tests\README.md` is a placeholder, and `.github\workflows\ci.yml` currently contains a scaffold step that only echoes `"Tests would run here"`.

When the stack is selected and implemented, update this section with:

- the full test command
- the single-test command for that stack
- any build and lint commands that CI actually uses

## Quick routing

Start with `gh plate context list/show` or the matching MCP tools `plate_contexts` / `plate_context` when the task is figuring out where authoritative truth lives.

Then use the lightest surface that can answer the question:

- process / ceremony / PR rules -> `AGENTS.md`
- intended product or process goal state -> `SPEC.md`
- implemented behavior / release evidence -> `.agentic/releases/`
- agent or skill discovery -> `gh plate agents list/show`, `gh plate skills list/show`, or matching MCP tools
- release targeting -> `gh plate release status`
- deep rationale / prior tradeoffs -> `docs/design/*`, `docs/research/*`

## High-level architecture

`plate_core` is the shared runtime behind PLATE's human and agent surfaces. The key project artifacts are:

- `AGENTS.md` — operating rules, ceremonies, escalation, and merge policy
- `SPEC.md` — intended goal state
- per-feature change files in `.agentic/releases/` — implemented behavior and migration evidence
- `.agentic\process.yml` — machine-readable process mirror
- `.github\labels.yml`, `.github\ISSUE_TEMPLATE\`, `.github\PULL_REQUEST_TEMPLATE.md` — work intake and review metadata

## Key conventions

- Repository artifacts are durable truth; update the artifact, not chat history.
- `AGENTS.md` is authoritative for process details. Keep this file focused on routing and first-step guidance.
- Run `gh plate release status` before opening PRs that target the integration branch.
- Apply exactly one PR type label at creation time.
- `Feature` PRs that change PLATE behavior, templates, or agent surfaces must add a fragment under `.agentic/releases/unreleased/`.
- Keep changes small, reversible, and evidence-backed.
- Stack selection remains a human decision until the Research issue is resolved.

## Playwright E2E

Use Playwright for user-visible features. Prefer the dedicated tools and docs over repeating guidance here:

- `@copilot init-playwright`
- `@copilot record-e2e-gif`
- `@copilot validate-e2e-tests`

See `src/plate_core/agent_guidance.py`, `src/plate_core/mcp/tools.py`, and `docs/playwright-e2e-guide.md` for the full workflow.

## Interactive epic planning

When the user wants to plan an epic, use the `interactive-epic-planning` skill and follow the detailed contract in `AGENTS.md` plus `.agentic/skills.yml`. Keep the chat flow small: create the Epic once you have a name and one-sentence problem, then refine with child stubs.
