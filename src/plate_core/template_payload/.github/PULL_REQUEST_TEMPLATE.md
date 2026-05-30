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

  Copilot and Grok Build: PR titles are for humans. Keep titles clean and descriptive. Never use bracketed prefixes of any kind ([Feature], [WIP], etc.) and never put (Closes #N) or similar metadata in the title. Use labels, Draft status, milestones, and body closing keywords instead.
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
| Closes Issue | `Closes #N` — **required** if this PR resolves a specific issue |
| Epic | TBD |
| ADR / Discussion | TBD |

## Tests and Evidence

| Evidence Type | Command, Artifact, or Explanation | Result |
|---|---|---|
| Failing test captured first, if applicable | TBD | TBD |
| Unit tests | TBD | TBD |
| Integration tests | TBD | TBD |
| E2E tests | TBD | TBD |
| E2E tests pass locally | `npm run test:e2e` | TBD |
| E2E demo GIF (if UI change) | `npm run record:e2e feature-name --headed` | TBD |
| Manual verification | TBD | TBD |
| Regression coverage | TBD | TBD |

## Testing & Visual Evidence (E2E / Demo)

- [ ] Local E2E tests pass: `npm run test:e2e`
- [ ] CI E2E tests passing (check Actions tab)
- [ ] Demo recorded & verified (if UI/user-visible change):
  - [ ] Test spec created: `tests/e2e/specs/feature-name.spec.ts`
  - [ ] Demo recorded: `npm run record:e2e feature-name --headed`
  - [ ] GIF generated and committed: `tests/e2e/fixtures/gifs/feature-name.gif`
  - [ ] GIF embedded in this PR or `CURRENT.md`
  - [ ] GIF size verified (warn <3MB, fail >5MB)

📹 **Recording a demo?** See [Playwright E2E Guide](../../docs/playwright-e2e-guide.md) and `AGENTS.md §Demo GIF Recording for UI Features`

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
- [ ] I included `Closes #N` (or `Fixes #N` / `Resolves #N`) in the Linked Work section above for every issue this PR resolves.
- [ ] I committed a git artifact to the appropriate `docs/` directory for every Research, Design, Audit, or Migration issue this PR closes.
- [ ] I left enough evidence for a human reviewer to verify the change without relying on chat history.
