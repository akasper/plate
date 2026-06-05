# Contributing to a PLATE Repository

This repository uses PLATE to keep human judgment, agent execution, and durable GitHub evidence aligned. Contributions should begin with a typed issue, proceed through testable implementation, and end with a pull request that links intent, evidence, documentation, and risk.

## Issue Rules

Every issue must carry exactly one issue type label: `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Audit`, or `Migration`. Feature issues, and optional Epic issues when used, must also be assigned to the GitHub milestone that represents the Epic. Question issues are information goals and are not tied to an Epic milestone by default. Mutable planning state such as status, priority, target date, owner, iteration, and release target belongs in GitHub Projects fields.

## Branch and Pull Request Rules

PLATE uses a three-tier branch model: `epic/<short-name>` branches for feature work within an Epic, a persistent `release` branch for Epic integration, and `main` for stable tagged releases. Feature and Bug PRs should target the epic branch for their Epic. When all child issues in an Epic are resolved, open a PR from `epic/<name>` → `release` (Epic-close ceremony). When a release is ready, open a PR from `release` → `main`, apply a semver tag, and hard-reset `release` to the tag (Release ceremony). See `AGENTS.md §Branch Model and Ceremonies` for the full step-by-step guide.

Use short descriptive branch names such as `feature/onboarding-copy`, `bug/login-regression`, or `docs/current-state-audit`. PR titles must be clean and written for human readers — do not use any bracketed prefixes (e.g. `[Feature]`, `[Bug]`, `[Documentation]`, `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or similar) and do not put issue references such as `(Closes #N)` in the title. All metadata lives in GitHub's native fields (labels, Development sidebar or body closing keywords, draft status, milestones). See AGENTS.md for details. Every pull request must carry exactly one PR type label: `Bug`, `Feature`, or `Documentation`. Feature PRs that change PLATE process, templates, or agent surfaces must author a fragment under `.agentic/releases/unreleased/<slug>.json`.

Use clean, descriptive PR titles that summarize the change without legacy status prefixes. Do not use `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or similar prefixes in titles. Use GitHub's native Draft PR status instead (`gh pr create --draft` or the "Create draft pull request" option in the UI) to signal work-in-progress. Draft status is reversible and keeps titles readable in PR lists, search results, notifications, and commit history.

If a pull request is opened with GitHub CLI, include the type label in the create command itself, for example `gh pr create --label "Feature"`, instead of treating labeling as a separate best-effort follow-up step.

When a pull request belongs to an Epic, set its milestone to match the Epic milestone. `Feature`, `Bug`, and issue-driven `Documentation` PRs must also link at least one tracked issue using either a closing keyword in the PR body or the Development sidebar. Use `no-issue` only for true chores or maintenance PRs that intentionally do not resolve tracked work.

For batched Question triage through GitHub CLI, use `scripts/question_batch.sh` (or `scripts/QuestionBatch.ps1` on Windows) to list open Question issues quickly.

## Test-First Preference

Bug fixes should include regression coverage. Feature work should add or update tests before or alongside implementation. If a test cannot be automated yet, document the manual verification evidence and create follow-up work when automation is still required.

## Merge Authority

Agents and automation may prepare pull requests, but a human must approve merges, releases, permission changes, public claims, and any weakening of required gates.

## Testing UI Features with Playwright E2E

New user-visible features should include Playwright E2E tests for reproducible coverage and visual evidence:

1. **Create an E2E spec** in `tests/e2e/specs/`:
   ```typescript
   // tests/e2e/specs/feature-name.spec.ts
   import { test, expect } from '@playwright/test';
   import { LoginPage } from '../pages/login-page';
   
   test('user can perform feature action', async ({ page }) => {
     const loginPage = new LoginPage(page);
     await loginPage.navigate();
     // ... test steps ...
     await expect(page).toHaveURL(/feature-success/);
   });
   ```

2. **Follow Page Object Model pattern** (see `tests/e2e/pages/`) for readable, maintainable tests

3. **Run tests locally before opening PR:**
   ```bash
   npm run test:e2e
   ```

4. **Record a demo GIF** (2–5 sec) for user-visible features:
   ```bash
   npm run record:e2e feature-name --headed
   ```
   - Choose quality (low/medium/high) when prompted
   - Verify GIF is < 3MB
   - Commit GIF to `tests/e2e/fixtures/gifs/feature-name.gif`

5. **Embed demo in PR or CURRENT.md:**
   ```markdown
   ![Feature demo](tests/e2e/fixtures/gifs/feature-name.gif)
   ```

See `docs/playwright-e2e-guide.md`, `tests/e2e/README.md`, and `AGENTS.md §E2E Testing Expectations` for full guidance.
