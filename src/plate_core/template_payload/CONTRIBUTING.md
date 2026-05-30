# Contributing to a PLATE Repository

This repository uses PLATE to keep human judgment, agent execution, and durable GitHub evidence aligned. Contributions should begin with a typed issue, proceed through testable implementation, and end with a pull request that links intent, evidence, documentation, and risk.

## Issue Rules

Every issue must carry exactly one issue type label: `Bug`, `Feature`, `Epic`, `Research`, `Design`, `Question`, `Audit`, `Migration`, or `Feedback Response`. Feature and Epic issues must also carry exactly one `Epic: short-name` label. Question issues are information goals and are not tied to an Epic label. `Feedback Response` issues (when used) are exempt from the Epic requirement. Mutable planning state such as status, priority, target date, owner, iteration, and release target belongs in GitHub Projects fields.

## Branch and Pull Request Rules

Use short descriptive branch names such as `feature/onboarding-copy`, `bug/login-regression`, or `docs/current-state-audit`. Every pull request must carry exactly one PR type label: `Bug`, `Feature`, `Documentation`, or `Feedback Response`. Feature and Bug PRs must include a closing keyword (`Closes #N`) to link the issue they resolve. `Feedback Response` PRs do not require a closing keyword; if used, the `.github/workflows/auto-label-feedback-responses.yml` workflow automatically applies both `risk:low` and `auto-merge`, making them eligible for autonomous auto-merge when AUTONOMOUS_MODE is active.

If a pull request is opened with GitHub CLI, include the type label in the create command itself, for example `gh pr create --label "Feature"`, instead of treating labeling as a separate best-effort follow-up step. For non-Feedback-Response PRs, consider applying a `risk:*` label at creation time to clarify review burden for reviewers (see §Risk Assessment and Labeling in `AGENTS.md`).

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

