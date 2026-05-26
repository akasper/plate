# Tests

PLATE projects should make behavior verifiable and traceable. Test commands are project-specific, but the evidence model is stable: every implemented feature should link to the tests, recordings, fixtures, or manual verification that prove it works.

| Test Type | Purpose | Evidence Location |
|---|---|---|
| Unit | Verify isolated logic. | Project-specific test output. |
| Integration | Verify components or services together. | Project-specific test output. |
| E2E | Verify primary user workflows. | Test output and recordings when available. |
| Regression | Prevent fixed bugs from returning. | Linked Bug issue and PR. |
| Manual | Capture temporary verification when automation is not yet practical. | PR evidence table and follow-up issue if needed. |

Generated projects should replace this file with stack-specific commands and artifact locations.
