# Tests

## Running tests

```bash
# Run all tests
go test ./...

# Run tests with verbose output
go test -v ./...

# Run a single test
go test -v -run TestRootCommand ./cmd/...
```

## Building

```bash
# Build the extension binary
go build -o gh-plate .

# Install as a gh extension (from the repo root)
gh extension install .
```

## Test evidence model

PLATE projects should make behavior verifiable and traceable. Every implemented feature should link to the tests, recordings, fixtures, or manual verification that prove it works.

| Test Type | Purpose | Evidence Location |
|---|---|---|
| Unit | Verify isolated command logic. | `go test -v ./...` output. |
| Integration | Verify components together. | Project-specific test output. |
| E2E | Verify primary user workflows. | Test output and recordings when available. |
| Regression | Prevent fixed bugs from returning. | Linked Bug issue and PR. |
| Manual | Capture temporary verification when automation is not yet practical. | PR evidence table and follow-up issue if needed. |
