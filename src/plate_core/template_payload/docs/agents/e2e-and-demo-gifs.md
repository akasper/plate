# E2E And Demo Gifs

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

**Demo GIF Recording for UI Features**

When implementing a Feature that includes UI changes or user interactions:

1. **Create a Playwright test** that reproduces the feature workflow (login, create an account, navigate a flow, etc.). Ensure the test is deterministic and takes 5-15 seconds.

2. **Record the test** using the local recording scripts:
   - **macOS/Linux:** `./scripts/e2e-record.sh "test-name" --headed`
   - **Windows:** `.\scripts\e2e-record.ps1 -TestName "test-name" -Headed`
   - The `--headed` flag shows the browser during recording; the script captures video automatically.

3. **Generate a demo GIF** when prompted by the script:
   - Choose quality: `low` (fastest, smallest), `medium` (default), or `high` (best quality)
   - Accept the suggested name or provide a custom name
   - GIF is saved to `tests/e2e/fixtures/gifs/`

4. **Include the GIF in your PR description** or wiki article:
   ```markdown
   ![Feature Demo](../../fixtures/gifs/feature-name-demo.gif)
   ```

5. **Commit the GIF** with your PR. GIFs are durable documentation and should be versioned alongside code changes.

**Troubleshooting:** See `scripts/README.md` for complete documentation, ffmpeg installation, GIF size optimization, and troubleshooting.

**Example workflow:**
```bash
# Write the test
# ... edit tests/e2e/features.spec.ts ...

# Record with visible browser
./scripts/e2e-record.sh "should create new account" --headed

# When prompted, generate a medium-quality GIF
# GIF is saved: tests/e2e/fixtures/gifs/create-account-demo.gif

# Commit and include in PR
git add tests/e2e/fixtures/gifs/create-account-demo.gif
```

**E2E Testing Expectations**

Playwright E2E tests provide reproducible test coverage and visual evidence for user-visible features:

- **Scope:** E2E tests cover browser-based user workflows, API integrations visible in the UI, and critical user paths (login, checkout, account setup, etc.). Do not test internal logic or non-browser services—those belong in unit or integration tests.

- **Coverage expectations:**
  - New UI features ship with at least 1 Playwright spec covering the happy path
  - Critical workflows include error condition coverage (form validation errors, API failures, network issues)
  - Page Object Model pattern (`tests/e2e/pages/`) keeps tests maintainable
  - Tests are deterministic and run consistently (avoid hard waits; use `waitForSelector`, `waitForLoadState`, etc.)

- **Demo GIFs for user-visible features:**
  - Record 2–5 seconds of key user interaction (feature demo, not the entire test)
  - Show the success state or primary feature behavior
  - Commit GIF to `tests/e2e/fixtures/gifs/feature-name.gif`
  - Embed in .agentic/releases/, PR description, or wiki: `![Feature demo](tests/e2e/fixtures/gifs/feature-name.gif)`

- **Local testing:**
  - Run tests: `npm run test:e2e` or `npm run test:e2e:watch`
  - Debug tests: `npm run test:e2e:debug` (opens inspector + headed browser)
  - Record demos: `npm run record:e2e feature-name --headed`

- **CI integration:**
  - `.github/workflows/test-e2e.yml` runs all E2E tests on every PR
  - Videos retained only on failure (configured in `playwright.config.ts`)
  - GIF generation triggered when PR has `demo` label
  - Artifacts uploaded with 90-day retention for debugging

- **Documentation:**
  - Full guide: `docs/playwright-e2e-guide.md`
  - Setup and examples: `tests/e2e/README.md`
  - Recording scripts: `scripts/README.md`
