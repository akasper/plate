# Research: Babysit Base Branch Out-of-Sync Merge Resolution

**Issue**: [#197](https://github.com/akasper/plate/issues/197) - Babysit agent does not handle out-of-sync base branch
**Epic**: [#112](https://github.com/akasper/plate/issues/112) - CLI-driven PR Feedback Babysitting
**Date**: 2026-05-30
**Status**: Implemented

## Problem Statement

The `plate pr babysit` feature (CLI and MCP tool `plate_pr_babysit`) monitors PRs for unresolved third-party agent feedback but does not detect or handle situations where the PR's feature branch falls behind or conflicts with the base branch.

This breaks the babysitting loop on active repositories where the base branch moves frequently, requiring manual intervention to update branches before the babysitter can continue addressing review feedback.

## Research Questions

1. How can we detect when a PR branch is out of sync with its base branch?
2. What is the appropriate default action for handling out-of-sync branches?
3. How should configurability be exposed to support different strategies?
4. What are the implementation constraints given existing architecture?

## Detection Approach

### GitHub PR Merge State

GitHub's GraphQL API provides `mergeStateStatus` on the PullRequest type with these relevant values:

- **CLEAN**: Branch is up to date and can be merged
- **BEHIND**: Branch is behind the base branch but has no conflicts
- **DIRTY**: Branch needs to be rebased (similar to BEHIND but with pending changes)
- **CONFLICTING**: Branch has merge conflicts with the base branch

**Decision**: Use `mergeStateStatus` as the primary detection signal. Consider BEHIND, DIRTY, and CONFLICTING as "out of sync" states requiring intervention.

### Implementation Location

The detection logic belongs in the babysit core (`pr_babysit.py`) alongside review thread detection, since both are PR health checks performed during babysitting.

**Decision**: Create a `_detect_base_branch_out_of_sync()` helper function and extend the existing GraphQL query to fetch `mergeStateStatus`, `baseRefName`, and `headRefName`.

## Default Action: Copilot Merge-Request Trigger

### Options Considered

1. **Manual notification only**: Report the state but take no action
   - Pro: Safe, no automation risk
   - Con: Requires human intervention, breaks autopilot goal

2. **Local automated rebase**: Use worktree isolation to rebase locally and push
   - Pro: Fully automated, no human interaction
   - Con: Complex, potential for merge conflicts requiring human resolution, risky for CI stability

3. **Copilot merge-request trigger**: Post a comment triggering GitHub Copilot's native branch update assistance
   - Pro: Leverages native GitHub/Copilot flow, auditable, reversible
   - Con: Requires Copilot to be enabled on the repository

**Decision**: Default to **Copilot merge-request trigger** (option 3) for consistency with existing babysit pattern where we post a `@copilot` trigger comment for actionable work.

### Trigger Comment Format

Following the existing `_BABYSIT_MARKER` pattern, introduce `_MERGE_TRIGGER_MARKER`:

```markdown
<!-- plate-pr-merge-trigger -->
@copilot This PR branch (`feature-branch`) is out of sync with the base branch (`main`).
Merge state: `BEHIND`

Please update this branch to resolve the merge conflict or bring it up to date with the base branch.
```

This matches GitHub's UI flow where users can click to request Copilot assistance with branch updates.

### Deduplication

Use marker-based deduplication (similar to `_has_existing_babysit_comment`) to avoid posting duplicate merge triggers on subsequent babysit cycles.

## Configurability

### Strategy Options

Expose a `branch_update_strategy` parameter with three values:

1. **copilot-request** (default): Post Copilot merge-request trigger comment
2. **local-rebase**: Local worktree rebase (stub for future implementation)
3. **none**: Detect and report only, take no action

### Configuration Surface

- **CLI**: Add `--branch-update-strategy` flag to `gh plate pr babysit`
- **MCP**: Add `branch_update_strategy` parameter to `plate_pr_babysit` tool schema
- **API**: Add `branch_update_strategy` parameter to `babysit_pr()` function

**Default**: `copilot-request` (safe, leverages native GitHub capabilities)

### Validation

Validate strategy value against the set `["copilot-request", "local-rebase", "none"]` and raise `ValueError` for invalid values.

For `local-rebase`, raise `NotImplementedError` with a clear message until the feature is implemented.

## Implementation Constraints

### TDD Approach Required

Per AGENTS.md, feature work must follow TDD:
1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor as needed

### Backward Compatibility

The changes must not break existing babysit usage:
- Preserve existing `BabysitReport` fields
- Add new fields as optional with defaults
- Maintain backward compatibility for `_load_review_threads()` (create `_load_pr_data()` that returns more data)

### Data Classes

Extend `BabysitReport` with:
- `out_of_sync: bool = False`
- `merge_state: str | None = None`
- `merge_trigger_posted: bool = False`
- `merge_trigger_url: str | None = None`

## Architecture Decisions

### Function Responsibilities

- `_detect_base_branch_out_of_sync(pr_data: dict) -> dict`: Pure detection logic, testable in isolation
- `_load_pr_data(client, repo, pr_number) -> dict`: Extended GraphQL query for PR data including merge state
- `_load_review_threads()`: Wrapper over `_load_pr_data()` for backward compatibility
- `_has_existing_merge_trigger_comment()`: Check for duplicate markers
- `_post_merge_trigger()`: Post Copilot merge-request trigger comment
- `babysit_pr()`: Orchestrate detection and action based on strategy

### Error Handling

- Invalid strategy values: Raise `ValueError` immediately
- `local-rebase` strategy: Raise `NotImplementedError` with clear message
- GraphQL failures: Let existing error handling bubble up (consistent with review thread loading)

## Acceptance Testing

### Unit Tests

1. Detection logic:
   - `test_detect_base_branch_out_of_sync_behind()`
   - `test_detect_base_branch_out_of_sync_conflicting()`
   - `test_detect_base_branch_out_of_sync_dirty()`
   - `test_detect_base_branch_out_of_sync_clean()`

2. Integration:
   - `test_babysit_pr_detects_out_of_sync_and_posts_copilot_trigger()`
   - `test_babysit_pr_respects_branch_update_strategy_none()`

### Manual Verification

After implementation:
1. Test CLI: `gh plate pr babysit <number> --act --branch-update-strategy copilot-request`
2. Test MCP: Invoke `plate_pr_babysit` with `branch_update_strategy: "copilot-request"`
3. Verify trigger comment format and deduplication
4. Check JSON output includes new fields

## Documentation Impact

### Files to Update

1. **AGENTS.md**: Document new capability in §Third-Party Agent Feedback section
2. **CLI help**: Already included via `add_argument()` help text
3. **MCP schema**: Already included in tool description
4. **.agentic/releases/**: Add per-feature change file describing implementation and verification

## Implementation Summary

**Implemented**: 2026-05-30

### Core Changes

- `src/plate_core/pr_babysit.py`:
  - Added `_detect_base_branch_out_of_sync()` function
  - Extended `BabysitReport` dataclass with merge state fields
  - Created `_load_pr_data()` to fetch PR merge state via GraphQL
  - Added `_has_existing_merge_trigger_comment()` and `_post_merge_trigger()`
  - Updated `babysit_pr()` to accept `branch_update_strategy` parameter and handle out-of-sync detection

- `src/plate_core/cli.py`:
  - Added `--branch-update-strategy` CLI flag with choices validation
  - Updated `cmd_pr_babysit()` to pass strategy and display merge state in output

- `src/plate_core/mcp_server.py`:
  - Added `branch_update_strategy` parameter to `plate_pr_babysit` tool invocation
  - Updated MCP tool schema to document the new parameter

- `tests/test_pr_babysit.py`:
  - Added 6 new tests for detection and integration
  - All existing tests remain passing

### Test Results

All 207 tests pass, including:
- 5 original babysit tests
- 6 new base branch sync detection tests
- Full repository test suite

### Default Behavior

When `--act` is specified and a PR is detected as out of sync:
1. Default strategy is `copilot-request`
2. Posts a `@copilot` trigger comment with merge context
3. Deduplicates to avoid multiple triggers
4. Returns merge state in `BabysitReport`

### Configuration

```bash
# Default: copilot-request
gh plate pr babysit 123 --act

# Explicit strategy
gh plate pr babysit 123 --act --branch-update-strategy copilot-request

# Detect only, no action
gh plate pr babysit 123 --act --branch-update-strategy none

# Future: local-rebase (currently NotImplementedError)
gh plate pr babysit 123 --act --branch-update-strategy local-rebase
```

### MCP Usage

```json
{
  "name": "plate_pr_babysit",
  "arguments": {
    "pr_number": 123,
    "act": true,
    "branch_update_strategy": "copilot-request"
  }
}
```

## Conclusion

The implementation successfully addresses the issue by:
1. Detecting out-of-sync base branches via `mergeStateStatus`
2. Defaulting to safe Copilot merge-request triggers
3. Providing configurability via `branch_update_strategy`
4. Following TDD approach with comprehensive test coverage
5. Maintaining backward compatibility
6. Supporting both CLI and MCP surfaces

The solution is conservative (leverages native GitHub capabilities), auditable (posts visible trigger comments), and reversible (comments can be deleted, strategy can be changed to `none`).

## References

- Issue [#197](https://github.com/akasper/plate/issues/197)
- Epic [#112](https://github.com/akasper/plate/issues/112)
- GitHub GraphQL PullRequest.mergeStateStatus: https://docs.github.com/en/graphql/reference/enums#mergestatestatus
- Existing babysit implementation: `src/plate_core/pr_babysit.py`
