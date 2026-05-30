# E2E Testing with Playwright

This directory contains end-to-end tests using [Playwright](https://playwright.dev/). These tests validate real user workflows in the application.

## Prerequisites

- Node.js 18 or higher
- npm 9 or higher

## Setup

Install dependencies (if not already done):

```bash
npm install
```

## Running Tests

### Run all tests

```bash
npm run test:e2e
```

### Run tests in watch mode

Automatically reruns tests as files change:

```bash
npm run test:e2e:watch
```

### Run tests in headed mode

Opens a visible browser window so you can see tests executing:

```bash
npm run test:e2e:headed
```

### Run tests with debugger

Opens headed browser with the Inspector panel, allowing step-through debugging:

```bash
npm run test:e2e:debug
```

### Run a specific test file

```bash
npx playwright test tests/e2e/specs/example.spec.ts
```

### Run tests matching a pattern

```bash
npx playwright test --grep "login"
```

## Environment Variables

Configure these environment variables to customize test behavior:

- `BASE_URL` - Base URL for the application (default: `http://localhost:3000`)
- `CI` - Set to `true` to enable CI mode (retry logic, parallelization)

Example:

```bash
BASE_URL=https://staging.example.com npm run test:e2e
```

## Test Results

After running tests, results are available in:

- **HTML Report**: `playwright-report/index.html` - View with `npx playwright show-report`
- **Test Videos**: `test-results/` - Videos are only retained on failure
- **Test Traces**: `test-results/` - Traces are captured on first retry for debugging

### Viewing test results

```bash
# View the HTML report
npx playwright show-report

# View a specific trace
npx playwright show-trace test-results/example-should-load/trace.zip
```

## Debugging

### Using the Inspector

Run tests with the debugger to step through your test code:

```bash
npm run test:e2e:debug
```

The Inspector panel allows you to:
- Step through test code
- Inspect page elements
- Execute commands in the console

### Using traces

Playwright traces capture:
- DOM snapshot
- Network log
- Console messages
- Test timeline

Traces are automatically captured on first retry. View them with:

```bash
npx playwright show-trace test-results/your-test-name/trace.zip
```

## Recording & Sharing Demo GIFs

### Recording a Test with Demo GIF

Use the `e2e-record.sh` script to record tests and optionally generate GIFs for documentation:

```bash
# Record a test (headless mode)
./scripts/e2e-record.sh homepage

# Record with visible browser
./scripts/e2e-record.sh "user login" --headed

# Record with low-quality GIF (smaller file, ~1.5 MB for 5 sec)
./scripts/e2e-record.sh checkout --quality low

# Record and skip GIF prompt
./scripts/e2e-record.sh "form submission" --skip-gif
```

**Output:**
- Video: `test-results/videos/test-name.webm`
- GIF (if generated): `tests/e2e/fixtures/gifs/test-name-demo.gif`

See `./scripts/e2e-record.sh --help` for all options.

### Converting Existing Videos to GIFs

When a test fails, Playwright automatically records a video. Convert it to a GIF:

```bash
# Default (medium quality, ~3 MB)
./scripts/gif-from-video.sh test-results/your-test-name/video.webm output.gif

# Low quality for small files (~1.5 MB)
./scripts/gif-from-video.sh test-results/your-test-name/video.webm output.gif --quality low

# Trim to specific time range
./scripts/gif-from-video.sh test-results/your-test-name/video.webm output.gif --start 00:00:02 --duration 5
```

See `./scripts/gif-from-video.sh --help` for all options.

### Size Guidelines

Choose quality based on your needs:

| Quality | File Size (10s) | Recommended For | Command |
|---------|-----------------|-----------------|---------|
| Low | ~1.5 MB | Wiki, README, GitHub issues | `--quality low` |
| Medium | ~3.0 MB | Feature announcements | `--quality medium` |
| High | ~8 MB | ❌ Not recommended | `--quality high` |

**Recommendation:** Use `low` for documentation (faster load, smaller repo).

### CI/CD Integration

Tests that run in CI can automatically generate and upload demo GIFs:

1. **Add `demo` label to your PR** to enable GIF generation
2. **Tests run and record videos on failure**
3. **CI automatically converts videos to GIFs** (medium quality)
4. **GIFs are uploaded as 90-day artifacts**
5. **PR comment includes links** to download and embed GIFs

See [`docs/playwright-e2e-guide.md`](../../docs/playwright-e2e-guide.md) for complete guide on GIF generation and embedding in documentation.

## Page Object Model

Tests use the Page Object Model pattern for maintainability. Page objects abstract selectors and actions:

```typescript
// pages/login-page.ts
export class LoginPage extends BasePage {
  emailInput = this.page.locator('input[type="email"]');
  passwordInput = this.page.locator('input[type="password"]');
  
  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    // ...
  }
}

// specs/login.spec.ts
const loginPage = new LoginPage(page);
await loginPage.login('user@example.com', 'password');
```

## Best Practices

1. **Use Page Objects** - Encapsulate selectors and actions in page objects (under `pages/`)
2. **Use Fixtures** - Create reusable test fixtures (under `fixtures/`) for setup/teardown
3. **Meaningful Names** - Use descriptive test names that explain what is being tested
4. **Single Responsibility** - Each test should verify one user workflow
5. **Use Data Attributes** - Prefer `data-testid` attributes for reliable selector targeting
6. **Async/Await** - Always use async/await for async operations
7. **Assertions** - Use Playwright's built-in assertions with `expect()`

## CI/CD Integration

When tests run in CI (GitHub Actions):

- 4 workers run tests in parallel
- Failed tests retry twice
- Videos are retained on failure for debugging
- Traces are captured for analysis
- Results are reported to the GitHub Actions workflow

## Troubleshooting

**Tests fail with "browser not found"**
- Run `npx playwright install` to download browsers

**Tests fail with "page.goto: net::ERR_CONNECTION_REFUSED"**
- Ensure the dev server is running (`npm run dev`)
- Check that `BASE_URL` is correct

**Tests are slow**
- Reduce parallelization: `npx playwright test --workers=1`
- Check for missing waits or assertions that complete too quickly

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Debugging Tests](https://playwright.dev/docs/debug)
