# Tests

PLATE projects should make behavior verifiable and traceable. Test commands are project-specific, but the evidence model is stable: every implemented feature should link to the tests, recordings, fixtures, or manual verification that prove it works.

See `docs/audits/test-coverage-audit-*.md` and `docs/research/test-classification-inventory.md` (from Epic #350) for the project's own classification of tests into **feature-proof** (directly prove documented claims/surfaces), **supporting** (regression/migration/hygiene), and **infra**, plus the bidirectional matrix against Goals/SPEC/design claims.

| Test Type | Purpose | Evidence Location |
|---|---|---|
| Unit | Verify isolated logic. | Project-specific test output. |
| Integration | Verify components or services together. | Project-specific test output. |
| E2E | Verify primary user workflows. | Test output and recordings when available. |
| Regression | Prevent fixed bugs from returning. | Linked Bug issue and PR. |
| Manual | Capture temporary verification when automation is not yet practical. | PR evidence table and follow-up issue if needed. |

**Convention for proof references (dogfooded via #350/#361/#362)**: In design docs, use an explicit `## Acceptance Evidence` section with "Proving tests: `tests/test_foo.py:Class.method` (and e2e spec if applicable). See the audit/research artifacts for the full matrix." Update tests with docstrings that declare the claim they prove when it is a high-level documented capability.

Generated projects should replace this file with stack-specific commands and artifact locations. (Updated for #350 convention.)
