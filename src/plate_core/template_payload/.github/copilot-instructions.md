# Copilot Instructions

## Build, test, and lint

This template enforces baseline process validation through `bash scripts/validate_plate_repo.sh .` in `.github\workflows\ci.yml`.

Downstream PLATE repositories **must replace placeholder validation with concrete stack commands** once runtime manifests are present (`package.json`, `pyproject.toml`, `wally.toml`, `default.project.json`, etc.). The validator fails CI if runtime manifests exist but docs/CI still claim the placeholder template state.

When a downstream project adds a runtime or package manager, prefer the real project commands over inventing new ones, and update this file with:

- the full test command
- the single-test command for that stack
- any build and lint commands that CI actually uses
- the default Playwright command and artifact locations for E2E evidence when browser automation applies

For local setup preflight, run:

- `bash scripts/check_toolchain.sh .` (macOS/Linux/WSL)
- `.\scripts\CheckToolchain.ps1 -Root .` (Windows PowerShell)
- `.\scripts\ValidatePlateRepo.ps1 -Root .` (Windows PowerShell parity check for `validate_plate_repo.sh`)

Playwright guidance defaults:

- enable video capture by default; recommend `video: 'retain-on-failure'` as the conservative template setting
- keep `trace: 'on-first-retry'` and `screenshot: 'only-on-failure'` when the stack supports them
- preserve videos, traces, and HTML reports as PR evidence and future wiki-sync inputs when available

## Quick routing

Start with `gh plate context list/show` or the matching MCP tools `plate_contexts` / `plate_context` when the task is figuring out where authoritative truth lives.

Then use the lightest surface that can answer the question:

## PLATE Persona as Default (Epic #459)

In a PLATE repository (signaled by the presence of a `.plate/` directory or `.plate/config`, `AGENTS.md`, `.agentic/` structure, or equivalent GitHub repo state such as Epic labels or release artifacts), the `plate` agent persona (from `plugin/agents/plate.agent.md`) **must be the default**.

- Hosts (Copilot, Grok Build, etc.) should automatically prefer or surface the "plate" persona / MCP surfaces for repository work.
- No explicit `/agent plate` or special command is required for normal operation.
- Explicit opt-out is supported (e.g. `/plate agent off` or host UI equivalent) to fall back to the raw host/default persona for the session (priority: session > user > repo > global PLATE default).
- Re-enablement is the normal persona activation or removal of override.
- This default ensures consistent use of PLATE rules, quiet operations guidance, thin surfaces, delegation, ceremony flows, and safety gates.
- Power users can still choose other agents when desired; the opt-out is reversible and low-friction.

See the root `AGENTS.md` "Default PLATE Persona" section (including the "Workarounds for Default Persona and Auto-Discovery Without Host Coordination" subsection), `plugin/agents/plate.agent.md`, and Epic #459 for details and the opt-out UX contract. This is a core part of making PLATE "just work" without special prompting.

For the extent of what we can achieve without external host coordination: the AGENTS.md + persona + these instructions make PLATE the default *behavioral assumption* (including Quiet Agents #456 rules as fast follow) once the agent engages the local materials. TUI agents discover personas via plugin/ and .github/. Opt-out via explicit host persona or chat prefix (documented in AGENTS.md) provides the reliable switch. See AGENTS.md for full workaround details.

- process / ceremony / PR rules -> `AGENTS.md`
- intended goal state -> `SPEC.md`
- implemented behavior / release evidence -> `.agentic/releases/`
- release targeting -> `gh plate release status`
- bootstrap / onboarding -> `docs/bootstrap/new-repository-checklist.md`
- deep rationale / prior tradeoffs -> `docs/design/*`, `docs/research/*`

## High-level architecture

This repository is a PLATE template. The critical artifacts are:

- `AGENTS.md` — operating rules and merge policy
- `SPEC.md` — intended goal state
- `.agentic/releases/` — implemented behavior and migration evidence
- `.agentic\process.yml` — machine-readable process mirror
- `.github\labels.yml`, `.github\ISSUE_TEMPLATE\`, `.github\PULL_REQUEST_TEMPLATE.md` — work intake and review metadata
- `.github\workflows\ci.yml` — baseline process validation via `scripts/validate_plate_repo.sh`

## Key conventions

- Repository artifacts are durable truth; update the artifact, not chat history.
- Keep this file focused on routing and template-specific first steps; use `AGENTS.md` for the full process contract.
- Run `gh plate release status` before opening integration-branch PRs.
- Apply exactly one PR type label at PR creation time.
- Feature changes to PLATE behavior, templates, or agent surfaces require a fragment under `.agentic/releases/unreleased/`.
- Start new repositories with `docs/bootstrap/new-repository-checklist.md` and the bootstrap scripts.

## Playwright E2E and recording

For browser-facing downstream projects:

- **macOS/Linux:** `./scripts/e2e-record.sh <test-name> --headed`
- **Windows:** `.\scripts\e2e-record.ps1 -TestName <test-name> -Headed`
- use Playwright for user-visible features and keep recordings as PR evidence
- full guidance lives in `AGENTS.md`, `docs/playwright-e2e-guide.md`, `tests/e2e/README.md`, and `scripts/README.md`

## Interactive epic planning

When a user wants to plan a large feature or epic, use the `interactive-epic-planning` skill from `.agentic/skills.yml` and follow the detailed contract in `AGENTS.md`. Keep the chat flow small: create the Epic once you have a title and one-sentence problem, then refine with child stubs.
