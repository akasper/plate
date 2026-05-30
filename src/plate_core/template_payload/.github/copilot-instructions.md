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

## High-level architecture

This repository is a **PLATE template**, not an application codebase. The important architecture is the process wiring between durable project artifacts, machine-readable rules, and GitHub enforcement:

- `SPEC.md` defines the intended goal state.
- `CURRENT.md` records the implemented state and verification evidence.
- `AGENTS.md` defines local agent operating rules and escalation boundaries.
- `.agentic\process.yml` mirrors the same process in machine-readable form for automation and audits.
- `.github\labels.yml`, `.github\ISSUE_TEMPLATE\`, and `.github\PULL_REQUEST_TEMPLATE.md` define the work intake and review metadata.
- `.github\workflows\label-check.yml` enforces required issue and PR type labels.
- `.github\workflows\pr-documentation-check.yml` enforces that `Feature` PRs update `CURRENT.md`.
- `.github\workflows\pr-issue-link-check.yml` warns (and fails for `Feature`/`Bug` PRs) if the PR body contains no closing keyword (`Closes #N`).
- `.github\workflows\question-handling.yml` supports the `/question-batch` issue-comment slash command for triaging open Question issues.
- `.github\workflows\auto-merge.yml` enables autonomous PR merging when `.github/AUTONOMOUS_MODE` is present and the PR carries the `auto-merge` label.
- `.github\workflows\plates-address-pr-feedback.yml` monitors `pull_request_review` and `pull_request_review_comment` events. When a known third-party agent (Devin, OpenHands, etc.) leaves feedback on a PR that is not already labeled `Feedback Response`, it posts a deduplicated `@copilot` trigger comment directly on that PR (no new issue, no associated response PR). Configure the agent list via the `PLATE_PR_FEEDBACK_AGENTS` repository variable (comma-separated logins); the workflow falls back to built-in pattern matching when the variable is absent. Set `COPILOT_TRIGGER_PAT` for reliable Actions-side `@copilot` routing.
- `.github\workflows\feedback-resolution-check.yml` fails when a PR has unresolved active review threads or `reviewDecision=CHANGES_REQUESTED`. Make this check required in branch protection so auto-merge waits until commentary is actually addressed.
- `.github\workflows\sync-wiki-on-merge.yml` runs only for merged `Feature` PRs on `main`, then copies scoped documentation sources into the GitHub wiki.
- `.github\agents\` contains custom Copilot agent definitions (`.agent.md` files) that appear in the agent picker for all collaborators. See `docs\research\custom-agent-packaging.md` for the packaging pattern.
- `docs\research\` stores committed artifacts for closed Research issues (see `docs\research\README.md`).
- `docs\design\` stores committed artifacts for closed Design issues (see `docs\design\README.md`).

Read those pieces together when making process changes. A change in one of them usually implies matching updates in the others.

## Key conventions

- Treat repository artifacts as the source of durable truth. If behavior, process, or evidence changes, update the relevant artifact instead of relying on chat history.
- If `AGENTS.md`, `.agentic\process.yml`, and the template files disagree, preserve the PLATE intent and keep them aligned.
- Labels are stable process metadata, not casual tags. Use type labels (`Bug`, `Feature`, `Epic`, `Documentation`, `Research`, `Design`, `Question`, `Audit`, `Migration`) and prefixed labels (`Epic:`, `area:`, `risk:`, `need:`) according to the existing taxonomy. Do not introduce `priority:` or `status:` labels; those belong in GitHub Projects fields.
- `Feature` issues must carry both the `Feature` label and a matching `Epic: short-name` label. Their issue template expects acceptance criteria, test expectations, and documentation impact.
- `Bug` work should include a reproduction path or explicitly signal the gap with `need:reproduction`, plus a regression test plan.
- `Research` issues must close with a committed artifact in `docs/research/` or a `SPEC.md` update — not just an issue comment. See `docs/research/README.md`.
- `Design` issues must close with a committed artifact in `docs/design/` or `docs/wiki/Features/`. See `docs/design/README.md`.
- `Question` issues are information goals. Batch triage with `/question-batch` or `scripts/question_batch.sh`, and when an answer changes agent guidance, update both `AGENTS.md` and `.agentic/skills.yml` in the closing PR.
- Every PR must carry a type label (`Bug`, `Feature`, or `Documentation`). **Critical:** The checkboxes in the PR template body do **not** apply GitHub labels — labels must be set explicitly via the CLI or GitHub API. Preferred approach: include `--label "<type>"` in `gh pr create` so the label is applied atomically at PR creation. If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before doing anything else. `Feature` PRs must update `CURRENT.md`; documentation-only changes should use the `Documentation` label.
- When a PR is opened without a type label, the `label-check.yml` CI workflow fails immediately **and posts a repair comment on the PR** with the exact `gh pr edit` command to fix it. Look for the ⚠️ bot comment on the PR — it contains the precise repair command for that PR number.
- **Every PR that resolves a specific issue must include `Closes #N` (or `Fixes #N` / `Resolves #N`) in the PR body, except for `Feedback Response` PRs.** GitHub will then automatically close the linked issue on merge. The `pr-issue-link-check.yml` workflow warns (and fails for `Feature`/`Bug` PRs) if the closing keyword is absent.
- PRs that do not resolve a tracked issue (chores, dependency bumps) should be labeled `no-issue` to silence the closing-keyword check.
- **Autopilot doctrine:** Prefer many small PRs (≤ 10 files each) over one large PR. Each PR should have a single clear purpose and be independently revertable. Prefer squash merges. Post an epic summary comment when all child issues are resolved, then pause for human review before starting the next epic.
- **Autonomous mode** is enabled when `.github/AUTONOMOUS_MODE` exists on the default branch. When active, agents may label eligible `risk:low` PRs `auto-merge` and call `gh pr merge --auto --squash` after `gh pr create`. Full eligibility rules in `AGENTS.md §Autonomous Mode`. Never use `auto-merge` on PRs touching `AGENTS.md`, `SPEC.md`, workflows, credentials, auth, payments, or public claims. Agents may never create or delete the `AUTONOMOUS_MODE` marker file themselves.
- `.github\workflows\auto-merge.yml` enforces the marker file check as a second gate.
- Prefer small, scoped documentation and wiki updates. The wiki sync workflow is intentionally conservative and currently treats `CURRENT.md`, `docs\wiki`, and `docs\features` as the sync inputs.
- For newly generated repositories, start with `docs/bootstrap/new-repository-checklist.md` and run `scripts/bootstrap_github.sh` (macOS/Linux/WSL) or `scripts\BootstrapGitHub.ps1` (Windows) before making project-specific changes.
- Do not weaken tests, documentation gates, or workflow checks to make a change pass. Human review and merge authority remain outside agent authority except as defined in `AGENTS.md §Autonomous Mode`.
- **Before opening any Feature issue that depends on an external API**, verify that `SPEC.md §External Integrations` contains an entry for that API and confirm it is reachable. If API availability is uncertain, open a Research issue first.

## Recording and GIF generation for UI features

When implementing a Feature that includes UI changes, use the local recording and GIF generation scripts to create demo artifacts for documentation and PRs:

**Quick reference:**
- **macOS/Linux:** `./scripts/e2e-record.sh <test-name> --headed` records a test and offers to generate a GIF
- **Windows:** `.\scripts\e2e-record.ps1 -TestName <test-name> -Headed` does the same
- GIFs are saved to `tests/e2e/fixtures/gifs/` and should be committed with the PR
- Full guidance: see `scripts/README.md`

**Typical workflow:**
1. Write a Playwright test that reproduces the feature (5-15 seconds)
2. Record with `--headed` flag to see the browser during recording
3. When prompted, generate a GIF (choose quality: low, medium, or high)
4. Commit the GIF and include it in the PR description: `![Feature Demo](../../fixtures/gifs/feature-name-demo.gif)`

**Dependencies:** Node.js 18+, npm, Playwright (in project), ffmpeg (optional for GIF generation). See `scripts/README.md` for installation and troubleshooting.

## Playwright E2E Testing

Use Playwright to provide reproducible test coverage and visual evidence for user-visible features. See full guidance in `AGENTS.md §E2E Testing Expectations`, `docs/playwright-e2e-guide.md`, and `tests/e2e/README.md`.

### When to Write E2E Tests

- **Do write:** UI features, user workflows, form submissions, navigation, API integrations visible in the UI, critical paths (login, signup, checkout)
- **Do not write:** Internal business logic, non-browser services, utility functions—those belong in unit tests

### Writing Playwright Specs

1. **Use Page Object Model pattern** (`tests/e2e/pages/` directory) to keep tests maintainable and readable
2. **Test happy path + error conditions:**
   - Happy path: user successfully completes the workflow
   - Error conditions: form validation, API failures, network issues
3. **Keep tests deterministic and focused:**
   - One feature per spec file (e.g., `tests/e2e/specs/user-login.spec.ts`)
   - Use `waitForSelector`, `waitForLoadState`, not hard waits
   - Aim for 2–3 specs per Feature PR
   - Test duration: 5–15 seconds (avoid slow, flaky tests)
4. **Example Page Object:**
   ```typescript
   // tests/e2e/pages/login-page.ts
   export class LoginPage extends BasePage {
     async fillEmail(email: string) { /* ... */ }
     async fillPassword(password: string) { /* ... */ }
     async clickLogin() { /* ... */ }
     async verifyLoginSuccess() { /* ... */ }
   }
   ```
5. **Example Spec:**
   ```typescript
   // tests/e2e/specs/user-login.spec.ts
   test('user can log in with valid credentials', async ({ page }) => {
     const loginPage = new LoginPage(page);
     await loginPage.navigate();
     await loginPage.fillEmail('user@example.com');
     await loginPage.fillPassword('correct-password');
     await loginPage.clickLogin();
     await loginPage.verifyLoginSuccess();
   });
   ```

### Running Tests

| Command | Purpose |
|---|---|
| `npm run test:e2e` | Run all E2E tests (non-headed) |
| `npm run test:e2e:watch` | Watch mode for development |
| `npm run test:e2e:debug` | Headed browser + Playwright Inspector |
| `npm run test:e2e -- --ui` | UI mode for test debugging |

**Always run `npm run test:e2e` locally before opening a PR.**

### Recording Demos

For user-visible features, record a 2–5 second demo GIF:

1. **Ensure the test is deterministic and passes locally** (`npm run test:e2e`)
2. **Record with headed browser:** `npm run record:e2e feature-name --headed`
3. **When prompted, generate a GIF** (choose quality: low, medium, or high)
4. **GIF is saved to:** `tests/e2e/fixtures/gifs/feature-name.gif`
5. **Verify GIF size:**
   - Aim for <1MB (warn >3MB, fail >5MB)
   - Use `low` quality for large interactions; `medium` for typical demos
6. **Embed in PR description or CURRENT.md:**
   ```markdown
   ![Feature demo](tests/e2e/fixtures/gifs/feature-name.gif)
   ```
7. **Commit and push** with your Feature PR

See `AGENTS.md §Demo GIF Recording for UI Features` for full details.

### CI Integration

- `.github/workflows/test-e2e.yml` runs `npm run test:e2e` on every PR
- Videos are retained only on failure (configured in `playwright.config.ts`)
- GIF generation is triggered when PR has `demo` label
- Artifacts uploaded with 90-day retention
- GIF artifacts include embedding instructions in PR comment

### MCP Tools (Phase 2)

When available via `.agentic/extensions.yml`:
- `@copilot init-playwright` — Scaffold E2E setup in a new repo
- `@copilot validate-e2e-tests` — Check setup completeness
- `@copilot record-e2e-gif` — Generate demo GIF from test

### Troubleshooting

- **Test timeouts:** Use `page.waitForLoadState('networkidle')` for SPAs; increase timeout for slow endpoints
- **Flaky tests:** Add explicit waits instead of hard-coded delays; check for race conditions
- **GIF size too large:** Reduce test duration (2–5 sec), use `low` quality, or trim video with ffmpeg
- **Permission errors on Windows:** Run PowerShell as Administrator if recording fails

See `docs/playwright-e2e-guide.md` and `scripts/README.md` for detailed troubleshooting.

## Interactive epic planning

When a user in Copilot chat expresses intent to plan a large feature or epic, use the `interactive-epic-planning` skill (see `.agentic/skills.yml`). The complete behavior spec is in `AGENTS.md §Interactive Epic Planning` and `.agentic/skills.yml`.

Quick reference:
- Detect intent via 3-tier signal scoring; only ask the confirmation question at HIGH (≥5 points).
- Create the Epic issue as soon as you have a name and problem statement — do not wait for full AC.
- Run at most 8 Q&A turns; stop at 3 minimum if the user signals completion.
- After each turn, update the Epic body and post `📝 Updated #N` in chat.
- Create child stubs (Research → Design → Feature) as the need becomes clear; tag them `need:refinement`.
- Before creating, check for duplicate epics (Jaccard ≥ 0.5 on title tokens).
- Store session state in `<!-- PLATE_SESSION_STATE: {...} -->` at the end of the Epic body.
- Post a planning summary comment when the session ends.
