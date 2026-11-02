# Plate Process Contract

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## PLATE Process Contract

This table documents the responsibilities and tooling for each core PLATE process element:

| Process Element | Responsibility | Tool/Script | Status | Evidence |
|---|---|---|---|---|
| Unit & Integration Tests | Developer + Copilot | Project-specific stack (Jest, pytest, cargo test, etc.) | Required for all PRs | `.github/workflows/ci.yml` runs project commands |
| E2E Specs | Developer + Copilot | Playwright (`npm run test:e2e`) | Required for UI features | `.github/workflows/test-e2e.yml`, `tests/e2e/specs/*.spec.ts` |
| Demo GIFs | Developer + Copilot | `npm run record:e2e` + GIF generation scripts | Required for user-visible features | `tests/e2e/fixtures/gifs/`, PR description/.agentic/releases/ |
| E2E CI Validation | Copilot + Actions | `.github/workflows/test-e2e.yml` | All PRs (videos retained on failure) | Test report, artifact links |
| GIF Processing (CI) | Actions + ffmpeg | `.github/workflows/test-e2e.yml` `process-gifs` job | Triggered by `demo` label | Artifacts with 90-day retention, PR comment with GIF links |
| Feature Documentation | Developer + Copilot | per-feature change files in `.agentic/releases/` update | Required for `Feature` PRs | CI gate: `pr-gates` in `.github/workflows/plate-pr-gates.yml` |
| Release Notes | Human + Copilot | `CHANGELOG.md` | Recommended for `Feature` PRs | Links and evidence in CHANGELOG entry |
| Issue Closure Traceability | Developer + Copilot | Closing keywords + linked PR for most issue types; `<!-- PLATE-TASK-CLOSED -->` completion comment for Task issues | Required | GitHub auto-close on PR merge or Task completion comment |
| Process Drift Audit | Copilot | Custom audit skills | Per-epic or quarterly | `docs/audits/` committed artifacts |

### Playwright E2E Key Responsibilities

**Developer responsibilities:**
- Write E2E specs for new UI features using Playwright (Page Object Model pattern)
- Record demo GIFs locally using `npm run record:e2e` for user-visible features
- Run `npm run test:e2e` locally before opening PR
- Commit GIFs and specs to the repository

**Copilot responsibilities (when assisting Feature work):**
- Help write or review Playwright specs and Page Objects
- Execute `npm run record:e2e` and GIF generation locally when needed
- Verify all tests pass in CI before PR merge
- Update per-feature change files in `.agentic/releases/` with evidence links to test files and demo GIFs

**CI/Actions responsibilities:**
- Run `npm run test:e2e` on every PR (`.github/workflows/test-e2e.yml`)
- Retain videos only on failure (configured in `playwright.config.ts`)
- Generate optimized GIFs from videos when PR has `demo` label
- Validate GIF size (warn at 3MB, fail at 5MB)
- Upload GIF artifacts with 90-day retention
- Post PR comment with GIF embedding instructions and artifact links

### Playwright E2E Key Tools and Commands

| Tool/Command | Purpose | When to Use |
|---|---|---|
| `npm run test:e2e` | Run all E2E tests locally | Before opening PR |
| `npm run test:e2e:watch` | Watch mode for development | While writing/debugging tests |
| `npm run test:e2e:debug` | Run with Playwright Inspector + headed browser | Debugging test failures |
| `npm run record:e2e <name> --headed` | Record test execution and generate demo GIF | After test is deterministic and passes locally |
| `.github/workflows/test-e2e.yml` | CI gate for all PRs | Automatic on PR; validates all tests pass |
| `tests/e2e/README.md` | Setup and usage documentation | First time using Playwright in this repo |
| `docs/playwright-e2e-guide.md` | Comprehensive Playwright guide | Reference for best practices and troubleshooting |
| `scripts/README.md` | Recording and GIF generation scripts | Recording demos locally |

### Task Issues

A **Task** is a human-only blocker or explicitly requested human action item. Use Task when:
- A human must take an action the agent cannot safely perform
- The work is action-first rather than information-first
- The blocker may be external to the repository (credentials, DNS, approvals, cloud setup)

Task issues must include in their body:
- **Human action required**
- **Why the agent cannot safely proceed**
- **Context and affected artifacts**
- **Best-effort instructions**
- **Done signal**
- **Related links**

Task issues do **not** require an `Epic: short-name` label. If a Task is clearly Epic-related, it should inherit the Epic milestone instead. They close with a short completion comment that includes `<!-- PLATE-TASK-CLOSED -->`.

### Spike Issues

A **Spike** is a time-boxed investigation with a defined question and a hard timebox. Use Spike (not Research) when:
- The question has a clear binary or bounded answer ("can we use X for Y?")
- The work should be discarded or converted if it runs over the timebox
- You need an answer to unblock a decision, not a general-purpose findings document

Spike issues must include in their body:
- `**Timebox:**` duration (e.g., "4 hours", "1 day")
- `**Question:**` the specific question to answer
- `**Done signal:**` what constitutes a sufficient answer

Spike issues do **not** require an `Epic: short-name` label. They close with a short findings note (committed artifact or inline comment).

### Stub Issues

In PLATE, a **Stub** is an issue that still needs a lot of detail. It serves the purposes of:

1. Adding structure while working through uncertainty.
2. Serving as a memory placeholder for humans who want to make a sidenote while they are focused on another task.
3. Providing a surface for pre-planning.

Any kind of Issue — Epic, Feature, Documentation, Bug, Research, Design, Question, Audit, Migration, Release, etc. — can be a Stub. Being a stub just means that it still needs to be defined via the process.

Stubs are a normal and encouraged part of the workflow. They let the project maintain forward structure and memory even when individual items are not yet fully specified.

### Marking and Working with Stubs
- An issue is (or remains) a stub when its description, acceptance criteria, scope, or other key details are still to be worked out.
- `need:*` labels (especially `need:decision`, `need:docs`, `need:tests`, `need:design`) indicate specific areas that still need work.
- The `status:stub` label can be used to explicitly mark an issue that is intentionally in stub state.
- In interactive planning flows, child stubs are commonly created with the `need:refinement` label (see next section). The deferred-gate rules for `need:refinement` remain valid for these.

### need:refinement Semantics

The `need:refinement` label is applied to planning child stubs created during interactive epic planning. It signals that the issue is intentionally incomplete and not yet ready for implementation.

**Gates deferred by `need:refinement`:**
- Acceptance criteria completeness check
- per-feature change files in `.agentic/releases/` update requirement (the stub has no implementation yet)

**Gates that are NEVER deferred, even for `need:refinement` stubs:**
- Exactly one PLATE issue type label must be present
- `Feature` stubs must carry the Epic milestone when one is already established
- Any PR that closes the issue must include a closing keyword (`Closes #N`)

Remove `need:refinement` from an issue when its AC and scope are sufficiently defined for implementation to begin. Agents may remove this label autonomously when adding full AC in a planning follow-up session.

The authoritative definition of Stubs lives in the root `AGENTS.md` of a PLATE repository (see the "Stub Issues" section). This shipped copy aligns with it for convenience in new repositories.

Before closing any issue through an agent-run implementation or answer flow, post a final comment that includes a structured usage block:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Feature` and `Question` issue closures are harvested by `.github/workflows/plates-on-issue-closed.yml` and appended to `.agentic/COSTS.md`. `Task` issues are exempt from the usage-report requirement and instead require the lightweight Task completion comment.
