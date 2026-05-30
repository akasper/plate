<!--
  ⚠️  AGENT REQUIRED ACTION — LABELS
  The "Required PR Type Label" checkboxes below are documentation only.
  Checking a box here does NOT apply a GitHub label to this PR.
  You MUST apply exactly one type label via the CLI or GitHub API:

    Preferred (at creation time):
      gh pr create --label "Feature" ...
      gh pr create --label "Bug" ...
      gh pr create --label "Documentation" ...

    If the PR is already open:
      gh pr edit NUMBER --add-label "Feature"

  Valid PR type labels: Bug | Feature | Documentation

  Missing or multiple labels cause immediate CI failure (PLATE Label Check).
  When CI fails, a repair comment will be posted on this PR with the exact command.

  PR titles are for humans. Keep them clean and descriptive. Never use bracketed prefixes of any kind ([Feature], [WIP], etc.) and never put (Closes #N) or similar metadata in the title. Use GitHub labels, the Development sidebar or body closing keywords, draft status, and milestones instead (see AGENTS.md).
-->

# PLATE Pull Request

## Summary

Explain the change in product or process terms. Identify whether this PR changes behavior, tests, documentation, process configuration, public claims, or release posture.

## Required PR Type Label

Select exactly one PR type label and apply it to this pull request.

- [ ] `Bug`
- [ ] `Feature`
- [ ] `Documentation`

## Linked Work

| Link Type | URL or Reference |
|---|---|
| Linked Issue(s) | `Closes #N` / `Fixes #N` / `Resolves #N`, or a Development sidebar link — **required** for `Feature`, `Bug`, and issue-driven `Documentation` PRs unless `no-issue` is applied |
| Epic Milestone | GitHub milestone for the parent Epic, when applicable |
| ADR / Discussion | TBD |

## Tests and Evidence

| Evidence Type | Command, Artifact, or Explanation | Result |
|---|---|---|
| Failing test captured first, if applicable | TBD | TBD |
| Unit tests | TBD | TBD |
| Integration tests | TBD | TBD |
| E2E tests or recording | TBD | TBD |
| Manual verification | TBD | TBD |
| Regression coverage | TBD | TBD |

## Documentation and Traceability

| Artifact | Required for This PR? | Updated or Explanation |
|---|---|---|
| `SPEC.md` | TBD | TBD |
| `CURRENT.md` | Required for `Feature` PRs | TBD |
| Wiki or docs source | TBD | TBD |
| Release notes / `CHANGELOG.md` | TBD | TBD |
| Public claims / marketing | TBD | TBD |
| `.agentic/*` process metadata | TBD | TBD |

## Risk and Rollback

| Question | Answer |
|---|---|
| Risk label applied, if any | TBD |
| User, data, security, or public-claim risk | TBD |
| Rollback plan | TBD |
| Follow-up issue needed | TBD |

## Agent Self-Review

- [ ] I followed `AGENTS.md` and did not change product intent without human approval.
- [ ] I used GitHub Projects fields, not labels, for mutable planning state.
- [ ] I did not weaken tests, remove required gates, or bypass review.
- [ ] I updated `CURRENT.md` for a Feature PR or explained why this PR is not a Feature.
- [ ] I linked every required issue using either a closing keyword in the PR body or the Development sidebar, and I used a closing keyword whenever merge should close the issue.
- [ ] I committed a git artifact to the appropriate `docs/` directory for every Research, Design, Audit, or Migration issue this PR closes.
- [ ] I left enough evidence for a human reviewer to verify the change without relying on chat history.
