# Copilot Instructions

## Build, test, and lint

The implementation stack has not yet been selected (see the open Research issue). `tests\README.md` is a placeholder, and `.github\workflows\ci.yml` currently contains a scaffold step that only echoes `"Tests would run here"`.

When the stack is selected and implemented, update this section with:

- the full test command
- the single-test command for that stack
- any build and lint commands that CI actually uses

## Playwright E2E Testing

PLATE repos have built-in Playwright E2E support. Use the MCP tools and agent guidance to scaffold and manage tests:

- **`@copilot init-playwright`** — Initialize Playwright setup in a repository
- **`@copilot record-e2e-gif`** — Record and generate demo GIF from a test
- **`@copilot validate-e2e-tests`** — Verify E2E setup and detect missing configuration

See `src/plate_core/agent_guidance.py` for full workflow guidance and `src/plate_core/mcp/tools.py` for implementation details.

## High-level architecture

`plate_core` is a **shared library** that powers two deployment surfaces from a single codebase:

| Surface | Entry point | Target audience |
|---|---|---|
| `gh plate` extension | `cmd/plate/` | Human developers and scripts — terminal TUI using `gum`/Charm |
| `plate-mcp` MCP server | `mcp/server/` | AI agents — first-class tool calls via `/mcp` in Copilot CLI |

Both surfaces delegate to the same core packages in `pkg/`:

- `pkg/github/` — GitHub REST and GraphQL API client wrappers
- `pkg/health/` — PLATE health check logic (labels, branch protection, epics, stale issues)
- `pkg/epic/` — epic state queries (child issues, blocked items, auto-merge queue)
- `pkg/features/` — optional feature detection (secrets presence, AUTONOMOUS_MODE marker, etc.)

The PLATE methodology artifacts that govern **this project's development process** are:

- `SPEC.md` — intended goal state and personas
- `CURRENT.md` — implemented state and verification evidence
- `AGENTS.md` — local agent operating rules and escalation boundaries
- `.agentic\process.yml` — machine-readable process configuration
- `.github\labels.yml`, `.github\ISSUE_TEMPLATE\`, and `.github\PULL_REQUEST_TEMPLATE.md` — work intake and review metadata

Read those pieces together when making process changes. A change in one usually implies matching updates in the others.

## Key conventions

- Treat repository artifacts as the source of durable truth. If behavior, process, or evidence changes, update the relevant artifact instead of relying on chat history.
- If `AGENTS.md`, `.agentic\process.yml`, and implementation files disagree, preserve the PLATE intent and keep them aligned.
- Labels are stable process metadata, not casual tags. Use type labels (`Bug`, `Feature`, `Epic`, `Documentation`, `Research`, `Design`, `Question`, `Audit`, `Migration`) and prefixed labels (`Epic:`, `area:`, `risk:`, `need:`) according to the existing taxonomy. Do not introduce `priority:` or `status:` labels; those belong in GitHub Projects fields.
- `Feature` issues must carry both the `Feature` label and a matching `Epic: short-name` label. Their issue template expects acceptance criteria, test expectations, and documentation impact.
- `Bug` work should include a reproduction path or explicitly signal the gap with `need:reproduction`, plus a regression test plan.
- `Research` issues must close with a committed artifact in `docs/research/` or a `SPEC.md` update — not just an issue comment. See `docs/research/README.md`.
- `Design` issues must close with a committed artifact in `docs/design/` or `docs/wiki/Features/`. See `docs/design/README.md`.
- Every PR must carry a type label (`Bug`, `Feature`, or `Documentation`). **Critical:** The checkboxes in the PR template body do **not** apply GitHub labels — labels must be set explicitly via the CLI or GitHub API. Preferred approach: include `--label "<type>"` in `gh pr create` so the label is applied atomically at PR creation. `Feature` PRs must update `CURRENT.md`; documentation-only changes should use the `Documentation` label.
- When a PR is opened without a type label, the `label-check.yml` CI workflow fails immediately **and posts a repair comment on the PR** with the exact `gh pr edit` command to fix it.
- **Copilot PR title rule:** Use clean, human-readable PR titles with no bracketed prefixes (`[Feature]`, `[Documentation]`, `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, etc.) and no issue-closing metadata in the title (`Closes #N`, `Fixes #N`, `Resolves #N`). Put closing keywords in the PR body only. This is enforced by `.github/workflows/pr-title-check.yml`.
- **Grok Build parity rule:** If work is delegated to or mirrored by Grok Build, preserve the exact same PR-title rule and body-only closing-keyword placement.
- **Every PR that resolves a specific issue must include `Closes #N` (or `Fixes #N` / `Resolves #N`) in the PR body.**
- Use local babysitting for third-party PR feedback: `gh plate pr babysit <number>` (or `/agent plate` with "babysit PR <number>"). This is the primary flow for addressing agent feedback inline on the same branch.
- `.github\workflows\feedback-resolution-check.yml` fails when a PR has unresolved active review threads or `reviewDecision=CHANGES_REQUESTED`. Make this check required in branch protection so auto-merge waits until commentary is actually addressed.
- PRs that do not resolve a tracked issue (chores, dependency bumps) should be labeled `no-issue` to silence the closing-keyword check.
- **Autopilot doctrine:** Prefer many small PRs (≤ 10 files each) over one large PR. Each PR should have a single clear purpose and be independently revertable. Prefer squash merges.
- **Autonomous mode** is enabled when `.github/AUTONOMOUS_MODE` exists on the default branch. When active, agents may label eligible `risk:low` PRs `auto-merge` and call `gh pr merge --auto --squash` after `gh pr create`. Full eligibility rules in `AGENTS.md §Autonomous Mode`.
- Do not weaken tests, documentation gates, or workflow checks to make a change pass. Human review and merge authority remain outside agent authority except as defined in `AGENTS.md §Autonomous Mode`.
- **Before opening any Feature issue that depends on an external API**, verify that `SPEC.md §External Integrations` contains an entry for that API and confirm it is reachable. If API availability is uncertain, open a Research issue first.
- **Stack selection is a human decision.** Do not introduce implementation files in a specific language until the Research issue is resolved and the stack is confirmed.
