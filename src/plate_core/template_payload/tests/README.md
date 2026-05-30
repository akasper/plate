# Tests

PLATE projects should make behavior verifiable and traceable. Test commands are project-specific, but the evidence model is stable: every implemented feature should link to the tests, recordings, fixtures, or manual verification that prove it works.

## Default assumption: Playwright for E2E

Unless a downstream project documents a better stack-specific alternative, PLATE should assume **Playwright** for end-to-end browser testing.

Recommended default Playwright evidence settings:

```ts
use: {
  video: 'retain-on-failure',
  trace: 'on-first-retry',
  screenshot: 'only-on-failure'
}
```

This keeps video capture enabled by default without making every successful run expensive to retain forever. If a project needs always-on recording for demos, audits, or regulated workflows, it can opt up from this baseline.

| Test Type | Purpose | Evidence Location |
|---|---|---|
| Unit | Verify isolated logic. | Project-specific test output. |
| Integration | Verify components or services together. | Project-specific test output. |
| E2E (Playwright default) | Verify primary user workflows with reproducible browser automation. | Playwright report, traces, and retained videos. |
| Regression | Prevent fixed bugs from returning. | Linked Bug issue and PR. |
| Manual | Capture temporary verification when automation is not yet practical. | PR evidence table and follow-up issue if needed. |

## Writing Playwright tests

- Focus on one primary user workflow per spec file.
- Use stable selectors (`getByRole`, `getByLabel`, `getByTestId`) over brittle CSS selectors.
- Treat video, screenshots, and traces as review artifacts, not just debugging leftovers.
- Keep fixtures and seeded data deterministic so recordings are useful evidence.
- If a feature changes the user-visible flow, link the resulting Playwright evidence in the PR and, when relevant, in wiki-facing documentation.

Generated projects should replace this file with stack-specific commands and artifact locations, but Playwright is the default starting point for browser-based E2E coverage.
