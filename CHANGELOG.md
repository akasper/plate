# Changelog

All notable changes to this project should be recorded here. Each release entry should link issues, pull requests, tests, documentation updates, wiki pages, migration notes, and audit findings where applicable.

## Unreleased

| Type | Change | Issue | PR | Evidence |
|---|---|---|---|---|
| Feature | Playwright E2E feature detection and MCP scaffolding tools: `init_playwright`, `record_e2e_gif`, `validate_e2e_tests` MCP tools; enhanced `gh plate features` CLI with better formatting and Playwright E2E detection; agent guidance for E2E testing workflow. | — | — | `src/plate_core/features.py`, `src/plate_core/cli.py`, `src/plate_core/mcp/tools.py`, `src/plate_core/agent_guidance.py`, `README.md` |
| Feature | Add `feedback-resolution-check.yml` to block merge while PR commentary is still unresolved: fails when active review threads remain unresolved or when `reviewDecision=CHANGES_REQUESTED`. Intended as a required branch-protection check for seamless auto-merge after feedback is addressed inline. | — | #63 | `.github/workflows/feedback-resolution-check.yml`, `AGENTS.md`, `.github/copilot-instructions.md`, `CURRENT.md`. |
| Process | Initial project setup: PLATE template scaffold applied, labels synced, branch protection configured, `README.md` and `SPEC.md` written for plate_core. | — | #1 | `README.md`, `SPEC.md`, `AGENTS.md`, `CURRENT.md` |
