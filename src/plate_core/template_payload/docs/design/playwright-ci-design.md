# Playwright Configuration & CI Workflow Design for PLATE Repositories

**Status:** Design Document  
**Last Updated:** 2024  
**Scope:** End-to-end testing architecture for PLATE-based projects

---

## 1. Playwright Config (`playwright.config.ts`)

### Design Rationale

Playwright configuration balances three priorities:
1. **Debugging capability:** Retain videos, traces, and screenshots on failure for investigation
2. **Test speed:** Minimize overhead, parallelize where safe (local serial, CI parallel)
3. **CI cost:** Affordable artifact storage and runner time

### Recommended Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e/specs',
  fullyParallel: process.env.CI ? true : false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 4 : 1,

  reporter: [
    ['html'],
    ['github'], // GitHub built-in reporter for PR comments
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure', // Keep Playwright trace only when tests fail
    video: 'retain-on-failure', // Record videos only for failed tests
    screenshot: 'only-on-failure', // Capture screenshots only for failures
  },

  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev', // Start dev server locally
        reuseExistingServer: true,
      },

  projects: [
    {
      name: 'chromium',
      use: { ...devices.chromiumLinux },
    },
    // Optional: Add Firefox and WebKit per-project if needed
    // {
    //   name: 'firefox',
    //   use: { ...devices.firefox },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices.webkit },
    // },
  ],

  timeout: 30 * 1000, // 30s per test
  expect: { timeout: 5 * 1000 }, // 5s for assertions
});
```

### Configuration Settings Explanation

| Setting | Local | CI | Rationale |
|---------|-------|----|-----------| 
| `workers` | 1 | 4 | Serial local testing prevents port conflicts; CI runner has resources for parallelism |
| `retries` | 0 | 1 | Fast feedback locally; CI retries catch flaky tests |
| `trace` | on-failure | on-failure | Traces add ~10MB per failure; retain only for debugging |
| `video` | on-failure | on-failure | Videos ~5–10MB; valuable for understanding failure replay |
| `screenshot` | on-failure | on-failure | Lightweight debugging artifact (~100KB–500KB) |
| `timeout` | 30s | 30s | Reasonable default; adjust per-test if needed |
| `expect.timeout` | 5s | 5s | Assertion timeout shorter than test timeout |
| `forbidOnly` | false | true | Allow `.only()` locally for development; fail CI if left behind |
| `fullyParallel` | false | true | Serial locally for clarity; parallel in CI for speed |

### Browser Selection

**Initial:** Chromium only
- Widest web compatibility
- Fastest performance
- Smallest footprint

**Optional per-project:** Firefox and WebKit
- Add if testing browser-specific quirks
- Enable incrementally based on project requirements
- Document in project's README

---

## 2. Test Structure & Organization

### Directory Layout

```
tests/e2e/
├── README.md                          # Setup & run instructions
├── fixtures/
│   ├── test-data.json                 # Mock API responses, user fixtures
│   ├── expected-screenshots/
│   │   └── dashboard-initial-load.png
│   └── gifs/                          # Generated demo GIFs (gitignored)
│       └── feature-x-workflow.gif
├── pages/                             # Page Object Model (POM)
│   ├── base.page.ts
│   ├── login.page.ts
│   ├── dashboard.page.ts
│   └── form.page.ts
├── utils/
│   ├── auth-helper.ts                 # Custom fixture for auth setup
│   ├── api-mocks.ts                   # MSW or Playwright route mocks
│   └── custom-fixtures.ts
├── specs/
│   ├── example.spec.ts                # Passing example test
│   ├── auth.spec.ts                   # Authentication flow
│   └── [feature-x].spec.ts            # Feature-specific tests
└── test-results/                      # Generated (gitignored)
    ├── [test-name]-failed-1.webm
    ├── [test-name]-trace.zip
    └── playwright-report/
```

### Page Object Model (POM) Pattern

**Why:** Centralizes selectors and interactions, reducing test maintenance when UI changes

```typescript
// pages/login.page.ts
import { Page, Locator } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.locator('input[name="email"]');
    this.passwordInput = page.locator('input[name="password"]');
    this.loginButton = page.locator('button:has-text("Log in")');
    this.errorMessage = page.locator('[role="alert"]');
  }

  async navigate() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
  }

  async getErrorText() {
    return this.errorMessage.textContent();
  }
}
```

### Custom Fixtures for Reusability

```typescript
// utils/custom-fixtures.ts
import { test as base, Page } from '@playwright/test';
import { LoginPage } from '../pages/login.page';

type TestFixtures = {
  loginPage: LoginPage;
  authenticatedUser: void;
};

export const test = base.extend<TestFixtures>({
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },

  authenticatedUser: async ({ page }, use) => {
    // Mock auth token
    await page.context().addCookies([
      {
        name: 'auth_token',
        value: 'test-jwt-token',
        domain: 'localhost',
        path: '/',
      },
    ]);
    await use();
  },
});

export { expect } from '@playwright/test';
```

### Example Spec Files

**Passing Example:**
```typescript
// specs/example.spec.ts
import { test, expect } from '../utils/custom-fixtures';

test.describe('Example Suite', () => {
  test('should navigate to homepage', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Dashboard/);
  });

  test('should display welcome message', async ({ page }) => {
    await page.goto('/');
    const heading = page.locator('h1');
    await expect(heading).toContainText('Welcome');
  });
});
```

**Authentication Workflow:**
```typescript
// specs/auth.spec.ts
import { test, expect } from '../utils/custom-fixtures';

test.describe('Authentication', () => {
  test('should login with valid credentials', async ({ loginPage, page }) => {
    await loginPage.navigate();
    await loginPage.login('user@example.com', 'password123');
    
    // After login, redirected to dashboard
    await page.waitForURL('/dashboard');
    await expect(page.locator('h1')).toContainText('Dashboard');
  });

  test('should show error on invalid credentials', async ({ loginPage }) => {
    await loginPage.navigate();
    await loginPage.login('user@example.com', 'wrongpassword');
    
    const error = await loginPage.getErrorText();
    expect(error).toContain('Invalid credentials');
  });

  test('should persist session after reload', async ({ page, authenticatedUser }) => {
    await page.goto('/dashboard');
    await page.reload();
    
    // Should still be logged in
    await expect(page).not.toHaveURL('/login');
  });
});
```

---

## 3. Local Test Execution

### NPM Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:watch": "playwright test --watch",
    "test:e2e:debug": "playwright test --debug --headed",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:report": "playwright show-report"
  }
}
```

### Script Usage

| Command | Use Case | Behavior |
|---------|----------|----------|
| `npm run test:e2e` | Full test run | Headless, exit code 0/1 for CI |
| `npm run test:e2e:watch` | Development | Rerun tests on file change, interactive UI |
| `npm run test:e2e:debug` | Debugging | Headed browser + Inspector (pause/step through) |
| `npm run test:e2e:headed` | Visual inspection | Headed browser, normal speed |
| `npm run test:e2e:report` | Report review | Open generated HTML report |

### Environment Variables

```bash
# .env.local (gitignored)
BASE_URL=http://localhost:3000
PLAYWRIGHT_DEBUG=0  # Set to 1 for trace collection

# Or set on CLI:
BASE_URL=https://staging.example.com npm run test:e2e
```

### Local Prerequisites

1. **Install dependencies:**
   ```bash
   npm install
   npm exec playwright install  # Install browser binaries
   ```

2. **Start development server (if not using `webServer` config):**
   ```bash
   npm run dev
   ```

3. **Run tests:**
   ```bash
   npm run test:e2e
   ```

### Typical Local Workflow

```
Developer writes feature → Writes E2E spec
  ↓
npm run test:e2e:watch (watches for changes)
  ↓
Spec fails → Fix implementation
  ↓
Spec passes → npm run test:e2e:debug (verify visually)
  ↓
Debug if needed (Inspector pauses, step through)
  ↓
Commit spec + implementation
```

---

## 4. CI Workflow (`test-e2e.yml`)

### GitHub Actions Workflow File

**Location:** `.github/workflows/test-e2e.yml`

```yaml
name: E2E Tests

on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize, reopened]
  schedule:
    - cron: '0 2 * * *' # Nightly at 2 AM UTC

concurrency:
  group: e2e-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test-e2e:
    name: Playwright Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci
        env:
          CI: true

      - name: Install Playwright browsers
        run: npx playwright install --with-deps

      - name: Start dev server
        run: npm run dev &
        env:
          CI: true

      - name: Wait for server
        run: |
          timeout 60 bash -c 'until curl -s http://localhost:3000 > /dev/null; do sleep 1; done'
        env:
          BASE_URL: http://localhost:3000

      - name: Run E2E tests
        run: npm run test:e2e
        env:
          BASE_URL: http://localhost:3000
          CI: true

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30

      - name: Upload test videos
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-videos
          path: test-results/**/*.webm
          retention-days: 30

      - name: Upload traces
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-traces
          path: test-results/**/*.zip
          retention-days: 30

      - name: Publish test report
        if: always()
        uses: EnricoMi/publish-unit-test-result-action@v2
        with:
          files: |
            junit.xml

      - name: Comment PR with results
        if: always() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const testResults = require('./test-results.json');
            
            const passed = testResults.stats.expected;
            const failed = testResults.stats.unexpected;
            const status = failed === 0 ? '✅' : '❌';
            
            const comment = `${status} **E2E Tests:** ${passed} passed, ${failed} failed

            📊 [View HTML Report](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment,
            });

  process-gifs:
    name: Generate Demo GIFs (Optional)
    needs: test-e2e
    if: success() && contains(github.event.pull_request.labels.*.name, 'demo')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v3
        with:
          name: playwright-videos
      - name: Convert videos to GIFs
        run: |
          for video in test-results/**/*.webm; do
            gif_name="tests/e2e/fixtures/gifs/$(basename "$video" .webm).gif"
            ffmpeg -i "$video" -vf "fps=10,scale=1280:-1:flags=lanczos" "$gif_name"
          done
      - name: Upload GIFs
        uses: actions/upload-artifact@v3
        with:
          name: demo-gifs
          path: tests/e2e/fixtures/gifs/**/*.gif
          retention-days: 90
```

### Workflow Stages

```
┌─────────────────────────────────────────────────────────────┐
│                    Trigger: PR / Push / Schedule             │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   ┌─────────────┐              ┌──────────────────┐
   │ Checkout    │              │ Setup Node + npm │
   │ code        │              │ Install deps     │
   └─────┬───────┘              └────────┬─────────┘
         │                               │
         └───────────────┬───────────────┘
                         ▼
            ┌────────────────────────┐
            │ Install Playwright     │
            │ browsers               │
            └────────────┬───────────┘
                         ▼
            ┌────────────────────────┐
            │ Start dev server       │
            │ Wait for readiness     │
            └────────────┬───────────┘
                         ▼
            ┌────────────────────────┐
            │ Run Playwright tests   │
            │ (4 workers parallel)   │
            └────────────┬───────────┘
                         ▼
            ┌────────────────────────┐
            │ Collect artifacts:     │
            │ - HTML report          │
            │ - Videos (on failure)  │
            │ - Traces (on failure)  │
            └────────────┬───────────┘
                         ▼
            ┌────────────────────────┐
            │ Comment PR with        │
            │ results + report link  │
            └────────────────────────┘
```

### Cost Breakdown

| Component | Cost per Run | Monthly (5 PRs) |
|-----------|---|---|
| 1 × Ubuntu Runner (2–5 min) | $0.008/min × 3.5 avg = $0.028 | $0.14 |
| Artifact Storage (30 days) | Free tier (25GB/month) | Included |
| **Total per month** | — | **~$0.14** |

**Assumptions:**
- 5 Feature PRs/month
- Average test run: 2–5 minutes (scales with test count)
- GitHub Actions free tier: 2000 min/month (included for public repos)

---

## 5. Artifact Naming & Storage

### Playwright Auto-Generated Artifacts

```
test-results/
├── auth.spec.ts-0/
│   ├── login-with-valid-credentials-failed-1.webm      # Video
│   ├── login-with-valid-credentials-trace.zip          # Trace
│   └── login-with-valid-credentials-failed-1.png       # Screenshot
├── dashboard.spec.ts-0/
│   ├── dashboard-load-failed-1.webm
│   ├── dashboard-load-trace.zip
│   └── dashboard-load-failed-1.png
└── …

playwright-report/
├── index.html                     # Main report
├── [test-name]-failed-1.html      # Individual test report
└── …
```

### GitHub Actions Artifact Upload & Retention

**Local storage:** GitHub Actions artifacts tab (default 30 days)

```yaml
# From workflow: artifacts retained per upload
- HTML report: 30 days
- Videos: 30 days (only on failure)
- Traces: 30 days (only on failure)
- Screenshots: 30 days (only on failure)
```

**Accessibility:**
1. **GitHub UI:** Actions > [Workflow Run] > Artifacts
2. **PR Comment:** Direct links to report
3. **API:** Download via GitHub REST API

### GIF Generation & Storage

**If committing GIFs:**
```
tests/e2e/fixtures/gifs/
├── login-flow.gif         (~2MB, max 5MB)
├── dashboard-dashboard.gif (~2MB)
└── …
```

**If ephemeral (CI only):**
- Generate in optional `process-gifs` job
- Upload as artifact (90 days)
- Link in PR comment

**Recommendation:** Start ephemeral; commit only high-value demos (~1–2 per project).

---

## 6. Integration with Existing PLATE Infrastructure

### Validation Script Integration

Update `scripts/validate.sh` (or equivalent):

```bash
#!/bin/bash
set -e

echo "Running E2E tests..."

# Check if project has E2E tests
if [ -d "tests/e2e" ]; then
  npm run test:e2e
else
  echo "⚠️  No E2E tests found, skipping..."
fi

echo "✅ Validation passed"
```

### AGENTS.md Feature Loop Integration

Add to **AGENTS.md** under Feature Loop:

```markdown
### E2E Testing
- **When:** Feature implementation is complete
- **What:** Agent writes minimal E2E spec(s) covering:
  - Happy path (feature works)
  - Error case (graceful failure handling)
  - Navigation/state (feature integrates with app)
- **Output:** Committed spec file(s) in `tests/e2e/specs/`
- **Example:** Feature "Dark mode toggle" → `tests/e2e/specs/theme.spec.ts`
- **Format:** Use Page Object Model; extend `custom-fixtures.ts` if needed
```

### Copilot Instructions Integration

Add to `copilot-instructions.md`:

```markdown
## E2E Testing Standards

### When Writing Features
- Include E2E tests alongside implementation
- Use Page Object Model (POM) pattern in `tests/e2e/pages/`
- Test happy path + key error cases
- Reference fixtures in `tests/e2e/utils/`

### Commands
- Local: `npm run test:e2e` or `npm run test:e2e:watch`
- Debug: `npm run test:e2e:debug` (headed + inspector)
- Report: `npm run test:e2e:report`

### CI/CD
- Tests run automatically on PR + push
- Failures block merge (via branch protection)
- Reports and videos available in Actions artifacts
```

### Skip Condition: Opt-Out for Non-Browser Projects

**In `.github/workflows/test-e2e.yml`:**

```yaml
jobs:
  test-e2e:
    if: ${{ !contains(github.repository_topics, 'no-e2e') }}
    # ... rest of job
```

**Or check for presence of tests:**

```yaml
steps:
  - name: Check if E2E tests exist
    id: check-tests
    run: |
      if [ -d "tests/e2e/specs" ] && [ "$(ls tests/e2e/specs/*.spec.ts 2>/dev/null | wc -l)" -gt 0 ]; then
        echo "has-tests=true" >> $GITHUB_OUTPUT
      else
        echo "has-tests=false" >> $GITHUB_OUTPUT
      fi

  - name: Run E2E tests
    if: steps.check-tests.outputs.has-tests == 'true'
    run: npm run test:e2e
```

---

## 7. Open Questions & Trade-offs

### Multi-Browser Testing

**Question:** Should we test Firefox and WebKit alongside Chromium?

**Trade-off:**
- **Pro:** Catches browser-specific bugs early
- **Con:** 3× test time, 3× CI cost, higher flakiness risk
- **Decision:** Start Chromium-only; add per-project on demand
- **Guidance:** Enable Firefox/WebKit if project targets non-Chrome users

**Implementation:** Uncomment `firefox` and `webkit` projects in `playwright.config.ts`

### Headless vs. Headed in CI

**Question:** Run tests headless in CI, or headed with screenshot on failure?

**Decision:** Headless (default)
- Faster (~15% speed gain)
- Lower resource usage
- Videos + screenshots sufficient for debugging
- Headed can be overridden locally

### Artifact Cost at Scale

**Question:** How many artifacts before cost becomes prohibitive?

**Analysis:**
- Current: 5 PRs/month → $0.14/month (negligible)
- Scaling: 100 PRs/month → $2.80/month (still acceptable)
- Threshold: ~500+ PRs/month before reconsidering artifact strategy

**If needed:** Implement artifact cleanup (e.g., keep only last 10 days, or compress)

### GIF Generation Timing

**Question:** Should GIF generation be:
1. Synchronous in workflow (block on completion)
2. Asynchronous post-processing (separate scheduled job)

**Decision:** Asynchronous via optional job
- Doesn't block test reporting
- Triggered only for `demo` label
- Failures don't fail the entire workflow

### Opt-Out Mechanism for E2E

**Question:** How should projects opt out of E2E if not browser-based?

**Options:**
1. Topic tag: Add `no-e2e` to GitHub topic
2. Config flag: `skip-e2e: true` in `package.json`
3. Directory check: Skip if `tests/e2e/specs` has no `.spec.ts` files

**Recommendation:** Combination of directory check + topic tag for clarity

---

## 8. Success Metrics

### What Success Looks Like

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Test Coverage** | E2E specs in 80%+ Feature PRs | Audit commits; check for spec files |
| **CI Reliability** | <5% flaky test rate | Track re-runs; review trace logs |
| **Debug Speed** | <10 min to root cause failure | Use videos + traces; document pattern |
| **Artifact Access** | 100% of reports visible in PR | Verify PR comment + artifacts tab |
| **Cost** | <$50/month | Monitor GitHub Actions billing |
| **Developer Adoption** | 100% of agents write specs | Audit agent-generated PRs |

### Evidence of Success

1. **Committed E2E specs** alongside features in PRs
2. **Videos/traces** actively used for debugging
3. **No manual regression** testing needed (tests catch issues)
4. **PR comments** consistently show test results + report links
5. **Cost stays <$50/month** even at 50+ PRs/month

### Anti-Patterns to Avoid

- ❌ Tests exist but are never run (workflow disabled or skipped)
- ❌ Videos recorded but never reviewed (storage bloat)
- ❌ Flaky tests that fail intermittently (erode trust)
- ❌ Tests that only check UI, not logic (brittle)
- ❌ No Page Object Model (selectors duplicated, maintenance nightmare)

---

## 9. Implementation Checklist

### Phase 1: Foundation (Weeks 1–2)

- [ ] Create `playwright.config.ts` with Chromium-only, `retain-on-failure` artifacts
- [ ] Set up directory structure: `tests/e2e/{pages,utils,specs,fixtures}`
- [ ] Add base Page Object classes
- [ ] Write 2–3 example specs (login, dashboard, form submission)
- [ ] Add NPM scripts: `test:e2e`, `test:e2e:watch`, `test:e2e:debug`
- [ ] Create `.github/workflows/test-e2e.yml` (basic, no GIF generation yet)
- [ ] Add `.github/dependabot.yml` rule for `@playwright/*` updates

### Phase 2: Polish & Adoption (Weeks 3–4)

- [ ] Update `AGENTS.md` with E2E testing guidelines
- [ ] Add to `copilot-instructions.md`
- [ ] Document in `tests/e2e/README.md`
- [ ] Add PR comment integration (results + report links)
- [ ] Optional: Add GIF generation job
- [ ] Test on 5+ real Feature PRs; gather feedback

### Phase 3: Scaling (Ongoing)

- [ ] Monitor artifact costs; adjust retention if needed
- [ ] Track flaky test patterns; refactor as needed
- [ ] Collect agent feedback; update patterns
- [ ] Consider Firefox/WebKit per-project requests
- [ ] Archive old test results; maintain report history

---

## 10. References & Examples

### Playwright Documentation

- [Playwright Config Reference](https://playwright.dev/docs/test-configuration)
- [Reporters](https://playwright.dev/docs/test-reporters)
- [GitHub Reporter](https://playwright.dev/docs/test-reporters#github-reporter)
- [Page Object Model Guide](https://playwright.dev/docs/pom)

### Example Repositories

- Playwright Project: https://github.com/microsoft/playwright/tree/main/tests/playwright-test
- Repo with E2E CI: See `.github/workflows/test.yml` patterns

### GitHub Actions

- [Artifact Upload/Download](https://github.com/actions/upload-artifact)
- [Concurrency](https://docs.github.com/en/actions/using-jobs/using-concurrency)
- [GitHub Script Action](https://github.com/actions/github-script)

---

## 11. Summary & Key Recommendations

### Configuration

✅ **Use `playwright.config.ts`** with:
- Chromium only (initially)
- `retain-on-failure` for videos, traces, screenshots
- 1 worker local, 4 workers CI
- 30s test timeout, 5s assertion timeout
- 0 retries local, 1 retry CI

✅ **Organize tests** with Page Object Model in `tests/e2e/{pages,utils,specs}`

### Local Development

✅ **Use `npm run test:e2e:watch`** during development

✅ **Use `npm run test:e2e:debug`** to troubleshoot (headed + inspector)

### CI/CD

✅ **Run on:** PR, push to main, scheduled nightly

✅ **Upload artifacts** for 30 days (GitHub default)

✅ **Comment PR** with results + HTML report link

✅ **Keep cost low** (<$50/month) by running serially locally, parallel in CI

### Integration

✅ **Document in AGENTS.md** & `copilot-instructions.md` so agents adopt pattern

✅ **Allow opt-out** for non-browser projects via directory check

✅ **Target success:** 80%+ of Feature PRs have E2E specs, <5% flaky rate

---

**Next Steps:** Implement Phase 1 checklist; iterate with real projects
