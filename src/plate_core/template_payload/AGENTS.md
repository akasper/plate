# PLATE Agent Operating Rules

This repository follows the **Process Lifecycle Agentic Task Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, `CURRENT.md`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **installable template artifacts** because those files must evolve faster than a long-form book can safely absorb. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the template artifact, and any migration note required for existing users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update `CURRENT.md`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |

## Autopilot Doctrine

PLATE defaults to an **autopilot posture**: agents should proceed autonomously through a task queue and pause only at defined human checkpoints, rather than asking permission at each step. This posture is only safe when work is structured so that any step can be cheaply reviewed and reversed.

**Atomic PR discipline.** Structure every session as a sequence of small, independently revertable PRs. A PR should have a single clear purpose. Soft limit: ≤ 10 changed files for implementation work. Prefer many small PRs over one large one. If a branch grows beyond the soft limit, split it before opening the PR.

**Easy revert as the norm.** Prefer squash merges (keeps history clean). Never push directly to `main`. Name branches `type/short-description`. Each squash commit on `main` should read as a complete, stand-alone unit of work.

**PR titles are for humans.** Pull request titles must be clean, concise, and written exclusively for human readers. Do not include any bracketed label-style prefixes (for example `[Feature]`, `[Bug]`, `[Documentation]`, `[WIP]`, `[DRAFT]`, or any similar convention). Do not include issue references, closing keywords, or other metadata such as `(Closes #N)`, `Fixes #123`, or equivalent in the title.

All metadata belongs in GitHub's native fields instead:
- PR type via labels (`Bug`, `Feature`, `Documentation`, or `Feedback Response`)

- Linked issues via the Development sidebar or a closing keyword placed only in the PR *body*
- Work-in-progress state via the native Draft PR status
- Epic grouping via milestones

**Agent-specific naming guardrail (Copilot + Grok Build).** GitHub Copilot and Grok Build must both follow the same PR-title rule above. When opening PRs via CLI/API, set a clean human title and put closing keywords only in the PR body. The `PLATE PR Title Check` workflow enforces this.

**Resource consciousness.** Prefer targeted tool calls over exhaustive scans. Batch parallel reads. Stop investigating after sufficient evidence — do not read every file if you already know the answer. Avoid repeatedly regenerating content that has not changed.

**Human checkpoints.** Post a summary comment on the Epic issue when all child issues are resolved. At that point, stop and let the human review before starting the next epic. Do not start a new epic autonomously without instruction.

**Pacing.** Do not create more than five open PRs simultaneously unless they are all marked `auto-merge` and eligible. Sequence work to minimize merge conflicts; prefer additive-first ordering.

**Autonomous mode** (see §Autonomous Mode below) is the formal toggle for the self-merge aspect of this doctrine. The pacing and PR-discipline rules apply in both modes.

## Required Work Loop

Follow the loop that matches the issue type.

**Feature**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Feature` and has exactly one `Epic: short-name` label. |
| 2 | Identify acceptance criteria, expected tests, documentation impact, and risk. |
| 3 | Add or update tests before or alongside implementation. |
| 4 | Implement the smallest coherent change that satisfies the issue. |
| 5 | Update `CURRENT.md` to describe the implemented behavior and verification evidence. |
| 6 | If the feature includes UI changes, record a demo GIF (see Demo GIF Recording guidance below). |
| 7 | Open a PR labeled `Feature` with `Closes #N` in the body. Complete the PR template. When using GitHub CLI, apply the type label in the `gh pr create` command itself rather than relying on a later edit step. |
| 8 | Leave wiki-sync, release-note, and audit evidence for the human reviewer and post-merge workflows. |

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
  - Embed in CURRENT.md, PR description, or wiki: `![Feature demo](tests/e2e/fixtures/gifs/feature-name.gif)`

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

**Bug**

Reproduce the failure or document why reproduction is not yet possible. Add a regression test. Include `Closes #N` in the PR body. Label missing information with `need:reproduction`, `need:tests`, or `need:human-review`.

**Research**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the research question, options, decision criteria, and required output are clear. |
| 2 | Gather evidence. Prefer authoritative primary sources; document your search path. |
| 3 | Commit findings to `docs/research/<issue-slug>.md` (see `docs/research/README.md` for format). |
| 4 | If the findings change product intent, also update the relevant section of `SPEC.md`. |
| 5 | Open a Documentation PR with `Closes #N` in the body. |
| 6 | Post a summary comment on the issue before closing it. |

**Design**

| Step | Required Behavior |
|---|---|
| 1 | Confirm scope, constraints, and the feature or system being designed. |
| 2 | Produce a design artifact (wireframes, API contract, data model, architecture diagram, decision record). |
| 3 | Commit the artifact to `docs/design/<feature-slug>.md` or update `docs/wiki/Features/<feature>.md`. |
| 4 | Open a Documentation PR with `Closes #N` in the body. |

**Question**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Question` (or legacy `#question`) and clearly states the information goal and answer signal. |
| 2 | Use batched review to process open questions (`/question-batch` slash command or `scripts/question_batch.sh`). |
| 3 | Commit the answer artifact (for example `docs/research/<slug>.md`) and any resulting process updates. |
| 4 | When the answer changes operating guidance, update `AGENTS.md` and `.agentic/skills.yml` in the same PR. |
| 5 | Open a Documentation PR with `Closes #N` in the body. |

**Audit**

Commit findings to `docs/audits/`. If drift is found, open a follow-up `Bug` or `Feature` issue per finding. Open a Documentation PR with `Closes #N` in the body.

**Migration**

Commit progress to `docs/migration/`. Update completion status in `docs/migration/completion-report.md`. Open a Documentation PR with `Closes #N` in the body.

## Issue Artifact Rules

Every issue must close with a traceable git artifact — either a code change in a PR or a documentation commit. Closing an issue without a corresponding PR is not permitted.

| Issue Type | Required Git Artifact | Typical PR Type Label |
|---|---|---|
| `Feature` | Code change + `CURRENT.md` update | `Feature` |
| `Bug` | Bug fix + regression test | `Bug` |
| `Research` | Findings committed to `docs/research/<slug>.md` or `SPEC.md` update | `Documentation` |
| `Design` | Artifact committed to `docs/design/<slug>.md` or `docs/wiki/Features/<feature>.md` | `Documentation` |
| `Question` | Answer artifact committed to `docs/research/<slug>.md` and process updates when guidance changes (`AGENTS.md`, `.agentic/skills.yml`) | `Documentation` |
| `Audit` | Report committed to `docs/audits/<slug>.md` | `Documentation` |
| `Migration` | Update committed to `docs/migration/` | `Documentation` |
| `Epic` | Wiki summary in `docs/wiki/` or epic comment summarizing child outcomes | `Documentation` |
| `Spike` | Short findings note in `docs/research/<slug>.md` or inline issue comment | `Documentation` |

When GitHub's native closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) is present in the PR body and the PR merges to the default branch, GitHub automatically closes the linked issue. **Always include a closing keyword in the PR body, except for `Feedback Response` PRs which are exempt.** This is enforced by `.github/workflows/pr-issue-link-check.yml` (warning gate).

## PLATE Process Contract

This table documents the responsibilities and tooling for each core PLATE process element:

| Process Element | Responsibility | Tool/Script | Status | Evidence |
|---|---|---|---|---|
| Unit & Integration Tests | Developer + Copilot | Project-specific stack (Jest, pytest, cargo test, etc.) | Required for all PRs | `.github/workflows/ci.yml` runs project commands |
| E2E Specs | Developer + Copilot | Playwright (`npm run test:e2e`) | Required for UI features | `.github/workflows/test-e2e.yml`, `tests/e2e/specs/*.spec.ts` |
| Demo GIFs | Developer + Copilot | `npm run record:e2e` + GIF generation scripts | Required for user-visible features | `tests/e2e/fixtures/gifs/`, PR description/CURRENT.md |
| E2E CI Validation | Copilot + Actions | `.github/workflows/test-e2e.yml` | All PRs (videos retained on failure) | Test report, artifact links |
| GIF Processing (CI) | Actions + ffmpeg | `.github/workflows/test-e2e.yml` `process-gifs` job | Triggered by `demo` label | Artifacts with 90-day retention, PR comment with GIF links |
| Feature Documentation | Developer + Copilot | `CURRENT.md` update | Required for `Feature` PRs | CI gate: `.github/workflows/pr-documentation-check.yml` |
| Release Notes | Human + Copilot | `CHANGELOG.md` | Recommended for `Feature` PRs | Links and evidence in CHANGELOG entry |
| Issue Closure Traceability | Developer + Copilot | Closing keywords + linked PR | Required for all issues | GitHub auto-close on PR merge |
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
- Update `CURRENT.md` with evidence links to test files and demo GIFs

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

### need:refinement Semantics

The `need:refinement` label is applied to issue stubs created during interactive epic planning. It signals that the issue is intentionally incomplete and not yet ready for implementation.

**Gates deferred by `need:refinement`:**
- Acceptance criteria completeness check
- `CURRENT.md` update requirement (the stub has no implementation yet)

**Gates that are NEVER deferred, even for `need:refinement` stubs:**
- Exactly one PLATE issue type label must be present
- `Feature` stubs must carry exactly one `Epic: short-name` label
- Any PR that closes the issue must include a closing keyword (`Closes #N`)

Remove `need:refinement` from an issue when its AC and scope are sufficiently defined for implementation to begin. Agents may remove this label autonomously when adding full AC in a planning follow-up session.

Before closing any issue (manually or via linked PR), post a final comment that includes a structured usage block:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Feature` and `Question` issue closures are harvested by `.github/workflows/plates-on-issue-closed.yml` and appended to `.agentic/COSTS.md`.

## Risk Assessment and Labeling

The `risk:*` label family communicates review burden and operational caution to humans and agents. Every PR may carry at most one `risk:*` label, selected from: `risk:low`, `risk:medium`, `risk:high`, `risk:critical`.

**risk:low** - Minimal review burden and low operational impact:
- Addresses third-party feedback or applies reviewed suggestions (Feedback Response PRs are **automatically** labeled `risk:low`)
- Small, localized changes that do not affect API boundaries, data models, or authentication
- Pure documentation, comment, or test-only changes that do not affect production behavior
- Dependency version bumps that pass all CI gates
- Formatting, naming, or cleanup changes with no semantic impact
- Changes that provably reduce technical debt with no functional change

**risk:medium** - Moderate review burden or operational caution:
- New features behind feature flags or in non-production code paths
- Behavioral changes to non-critical subsystems (logging, monitoring, utilities)
- Database migrations with forward/backward compatibility; schema changes with no data loss
- Configuration or deployment changes with straightforward rollback paths
- Public API additions that are purely additive (no removal or breaking changes)

**risk:high** - High review burden, user impact, or migration risk:
- Behavioral changes to critical paths (auth, payment, data integrity)
- Public API breaking changes or removals
- Database migrations that lose data or cannot be rolled back
- Infrastructure or deployment changes with unknown rollback procedure
- Changes affecting multiple subsystems or cross-cutting concerns
- Changes that modify `SPEC.md`, `CURRENT.md`, or public product claims

**risk:critical** - Release, security, compliance, or data risk:
- Security vulnerabilities (auth bypass, data exposure, injection flaws)
- Compliance or legal changes (privacy, terms, licensing)
- Changes affecting billing, pricing, or subscription logic
- Customer data access, deletion, or transformation
- Changes to `.github/CODEOWNERS`, `AGENTS.md`, or branch protection rules
- Modifications to `.github/AUTONOMOUS_MODE` or autonomous mode eligibility criteria

**When to apply risk:low:**
- Always apply to `Feedback Response` PRs — the `.github/workflows/auto-label-feedback-responses.yml` workflow does this automatically
- Apply to `Documentation` and `Refactoring` PRs unless they update product specification or public claims
- Apply to test-only or CI-only PRs that do not affect deployed code
- Apply to pure chore PRs (dependency bumps, code cleanup) when no behavior changes

**When NOT to apply risk:low:**
- If `risk:medium`, `risk:high`, or `risk:critical` is more accurate — apply the higher label instead
- If unsure, apply `risk:medium` or ask a human reviewer to clarify
- If the PR carries `need:human-review`, `need:security-review`, or `need:decision`, re-assess after those needs are satisfied

## Autonomous Mode

Autonomous mode is an opt-in operating posture for unattended sessions (overnight runs, long-running autopilot, `/delegate` tasks) where no human reviewer is available interactively. It selectively lifts the self-merge prohibition for lightweight, low-risk PRs.

**Toggle:** Create `.github/AUTONOMOUS_MODE` on the default branch to enable. Delete it to return to normal human-in-the-loop operation. The file content is ignored; its presence is the signal.

**When autonomous mode is active:**

| Rule | Normal Mode | Autonomous Mode |
|---|---|---|
| Agent may merge own PRs | Never | Permitted for eligible `risk:low` PRs only |
| Must wait for human merge | Always | May call `gh pr merge --auto --squash` on eligible PRs |
| May add `auto-merge` label | No | Yes, for eligible PRs |

**Eligibility criteria — all must be true for a PR to qualify:**

- Labeled `risk:low` (see §Risk Assessment and Labeling above)
- Does not modify `AGENTS.md`, `SPEC.md`, `.github/CODEOWNERS`, or any workflow file
- Does not add, remove, or alter credential handling, payment logic, authentication, or security controls
- Does not carry `need:human-review` or `need:security-review`
- Does not change public-facing claims in `README.md` or marketing documentation

**How to auto-merge an eligible PR in autonomous mode:**

```bash
gh pr create --label "risk:low" --label "auto-merge" [other required labels] ...
gh pr merge --auto --squash <PR_NUMBER>
```

For `Feedback Response` PRs, the `.github/workflows/auto-label-feedback-responses.yml` workflow applies both `risk:low` and `auto-merge` labels automatically, so the above workflow call is sufficient.

The `.github/workflows/auto-merge.yml` workflow also triggers on the `auto-merge` label and verifies the marker file before proceeding — providing a second gate.

**GitHub settings required** (one-time per repository):

```bash
# Allow the repo to use auto-merge
gh api -X PATCH repos/OWNER/REPO -f allow_auto_merge=true

# Allow Actions to write PRs and contents (needed by the workflow)
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false
```

**Security posture:** Autonomous mode intentionally cannot self-escalate. An agent operating in autonomous mode may not create, modify, or delete `.github/AUTONOMOUS_MODE` itself, and may not relax branch protection rules or modify the eligibility criteria in this file.

## Third-Party Agent Feedback

When a third-party agent (Devin, OpenHands, etc.) leaves feedback on a PR that is **not** already labeled `Feedback Response`, the `.github/workflows/plates-address-pr-feedback.yml` workflow posts a structured `@copilot` trigger comment directly on that same PR. The automation uses `COPILOT_TRIGGER_PAT` (preferred) with fallback to `GITHUB_TOKEN`, applies a dedupe marker, and intentionally avoids creating a new issue or opening a separate PR. `Feedback Response` PRs are already in the dedicated response lane and are skipped by that workflow. The Copilot Coding Agent should:

1. Review all open inline comments and the overall review body from the named reviewer on the linked PR
2. For any comment that includes a GitHub code suggestion (` ```suggestion ` block): apply it directly as a commit **unless** the suggestion introduces a bug or relies on a false assumption — if you skip a suggestion, reply to that thread with a brief explanation
3. For all other actionable comments: push a code change or reply explaining why no change is needed
4. After addressing each comment (via code change, applied suggestion, or explanatory reply), resolve its review thread using the GitHub GraphQL `resolveReviewThread` mutation:
   ```graphql
   mutation { resolveReviewThread(input: { threadId: "THREAD_NODE_ID" }) { thread { isResolved } } }
   ```
   To find `THREAD_NODE_ID` for a given comment, query `repository.pullRequest.reviewThreads` and match on `comments.nodes.databaseId`.
5. **Push all changes to the existing PR branch** — do not open a new issue or a new PR for the feedback response
6. For items requiring human judgment (credentials, architectural decisions, security changes), add `need:human-review` to the PR and leave a comment identifying what is blocked

**Lifecycle contract for `Feedback Response` items:**

| Stage | Expected artifact |
|---|---|
| Workflow fires | Trigger comment posted on the existing PR (`<!-- plates-feedback-trigger:<agent> -->` + `@copilot` instructions) |
| Copilot addresses feedback | Commits pushed to the same PR branch; review threads resolved |
| Escalation | `need:human-review` label + blocking comment when human judgment is required |
| Completion | `feedback-resolution` check is green (no unresolved review threads, no `CHANGES_REQUESTED` decision), then original PR merges through normal checks |

`Feedback Response` labels remain available process metadata, but this workflow no longer creates feedback-task issues or follow-up response PRs. Feedback is addressed inline on the original PR branch.

**Deduplication:** The workflow posts a tracking comment containing the marker `<!-- plates-feedback-trigger:<agent> -->` on the PR after each trigger. A 10-minute cooldown prevents duplicate Copilot trigger comments when a single review fires multiple parallel events.

**Configuration:** Set the `PLATE_PR_FEEDBACK_AGENTS` repository variable to a comma-separated list of GitHub logins whose feedback should be auto-addressed (e.g., `devin-ai-integration[bot],openhands-agent`). Set `COPILOT_TRIGGER_PAT` (classic PAT with `repo` scope) for reliable `@copilot` routing from Actions. When the variable is absent, the workflow matches common agent login patterns automatically.

**Merge safety gate:** Require `.github/workflows/feedback-resolution-check.yml` (`feedback-resolution`) in branch protection for `main` so auto-merge waits until all active review threads are resolved.

<!-- PLATES-CORE:BEGIN interactive-epic-planning -->
## Interactive Epic Planning

When a user expresses intent to plan a new epic, offer a guided Q&A session that extracts requirements and creates the Epic issue and child stubs incrementally. This workflow applies in Copilot chat. MCP and CLI surfaces are reserved for Phase 2.

### Intent Detection

Evaluate incoming messages against a 3-tier signal system:

| Tier | Score | Action |
|---|---|---|
| HIGH | ≥ 5 pts | Ask the confirmation question immediately |
| MEDIUM | 3–4 pts | Watch for a follow-up trigger in the next turn; do not interrupt |
| LOW | ≤ 2 pts | Ignore; do not interrupt the conversation |

Signal weights (cumulative): "plan" or "epic" keyword (+2), explicit "feature" or "capability" keyword (+1), question phrasing or "what would it take" (+1), "breaking down" or "scoping" phrasing (+1), scope-size language ("big", "large", "multi-week") (+1), explicit request ("let's create an epic") (+2).

Confirmation question: *"It sounds like you want to plan a new epic. Should I start a structured planning session? I'll ask a few questions and create the Epic issue and child stubs on GitHub as we go."*

If the user declines, drop to MEDIUM watch state. Do not ask again in the same conversation unless the user re-initiates.

### Minimum Creation Threshold

Create the Epic GitHub issue as soon as you have:
- A name (title) for the epic
- A one-sentence problem statement

Do not wait for full AC or scope before creating. Use `need:refinement` on child stubs.

### Duplicate Detection

Before creating, search for open Epic issues with similar titles:

```bash
gh issue list --repo OWNER/REPO --label Epic --state open --json number,title
```

Compute Jaccard similarity on title tokens. If any result scores ≥ 0.5, warn the user and offer:
1. Add child issues to the existing Epic instead
2. Create a new Epic anyway (distinct scope)
3. Cancel and open the existing Epic for review

### Q&A Phase

Run at most 8 turns. Each turn = one agent question + one user answer.

**Acceptance criteria arc (turns 1–3):**
1. "What does success look like when this epic is done?"
2. Probe: "What's the most important part of that — what has to work for this to be useful?"
3. Anchor: "How would you know it's truly complete — what's the 'done' signal?"

**Scope arc (turns 4–6):**
4. "What's explicitly in scope for this epic?"
5. "What are you explicitly NOT trying to solve with this epic?"
6. "Are there any epics, issues, or external changes this depends on?"

**Fast path:** If the user says "that's enough" or "I'll fill in the rest," stop at 3 turns minimum.

### Incremental Issue Updates

After each Q&A turn, update the Epic issue body using `gh issue edit`:

```bash
gh issue edit <NUMBER> --body-file -
```

Store session state in an HTML comment at the end of the body:

```html
<!-- PLATE_SESSION_STATE: {"turn": 3, "ac": [...], "scope_in": [...], "scope_out": [...]} -->
```

Post a `📝 Updated #N` signal in the chat to confirm each update.

### Progressive Child-Issue Creation

Create child stubs in this order: Research → Design → Feature. Create each stub as soon as the need is clear — do not wait until the end of the session.

Required fields for every stub:
- Title
- Type label (`Research`, `Design`, or `Feature`)
- Epic label (`Epic: <slug>`)
- `need:refinement` label
- Body: one-line summary + `<!-- PLATES-EPIC: #<epic-number> -->`

### Session Resumption

Reconstruct state from the `PLATE_SESSION_STATE` HTML comment in the Epic body. Re-entry prompt: *"I found a planning session in progress for Epic #N. Would you like to continue from turn [X], or start over?"*

### Completion

When the session ends (turn budget exhausted or user signals done), post a planning summary comment on the Epic issue listing:
- Final AC items captured
- Scope in/out items
- All child issues created (with numbers)
- Suggested next steps (merge PRs for Research stubs first)
<!-- PLATES-CORE:END interactive-epic-planning -->

## Label Rules

Use labels as stable process metadata. Do not create ad hoc labels unless they change routing, enforcement, reporting, auditing, review burden, or agent behavior. Use GitHub Projects fields for frequently changing planning state such as priority, owner, rank, iteration, target date, or release target. The `status:blocked` and `status:ready-to-work` labels are the explicit exception used by PLATES native trigger workflows.

| Label Family | Usage |
|---|---|
| `Bug`, `Feature`, `Epic`, `Research`, `Design`, `Question`, `Audit`, `Migration`, `Feedback Response` | Exactly one required issue type label. |
| `Bug`, `Feature`, `Documentation`, `Feedback Response` | Exactly one required pull request type label. |
| `Feedback Response` | Combined issue + PR type for feedback-response process work when needed. Not auto-created by `plates-address-pr-feedback.yml` in the inline response flow. No `Epic:` label required. |
| `Epic: short-name` | Epic identity and feature grouping. Required on Epic and Feature issues. |
| `area:*` | Stable subsystem or ownership area. |
| `risk:*` | Review burden and release caution. |
| `need:*` | Missing input or required follow-up. |

## Documentation Rules

Every Feature pull request must modify `CURRENT.md`. Documentation pull requests must commit a file to the appropriate `docs/` subdirectory and should explain whether they update process artifacts, product documentation, wiki source material, or public-facing claims. If a change affects feature behavior, update both implementation evidence and documentation evidence.

See §Issue Artifact Rules for the full mapping of issue type to required artifact location.

When opening pull requests through GitHub CLI, prefer an atomic command such as `gh pr create --label "Feature"` or `gh pr create --label "Documentation"`. If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before any other work.

**Important:** The checkboxes in the PR template body do **not** apply GitHub labels. Labels must be set explicitly via the CLI or GitHub API.

For **every new pull request**, add exactly one required PR type label (`Bug`, `Feature`, `Documentation`, or `Feedback Response`) at creation time. Unlabeled or multiply-labeled PRs fail CI immediately, and a repair comment will be posted on the PR with the exact `gh pr edit` command to fix it.

## Upstream PLATE Template Synchronization

<!-- PLATES-CORE:BEGIN upstream-template-sync -->
Downstream PLATE repositories often customize baseline files such as `AGENTS.md`, `.agentic/skills.yml`, and workflow definitions. Sync from the canonical upstream template repository `akasper/plate_template`.

If needed, configure the upstream remote first:

```bash
git remote add upstream https://github.com/akasper/plate_template.git
```

Do not overwrite these files wholesale during upgrades.

Use **sectional synchronization** for core behavior updates:

1. Compare upstream and downstream files to identify changed `PLATES-CORE` blocks.
2. Copy only the relevant core blocks into downstream files, preserving local sections outside those markers.
3. Open an atomic PR labeled `Feature` (or `Documentation` for doc-only syncs) and include `Closes #N` when tied to an issue.
4. Update `CURRENT.md` with the imported behavior and evidence links.
5. Run the repository's required checks before requesting review.

Marker format for sync-safe blocks:

```md
<!-- PLATES-CORE:BEGIN block-id -->
... upstream-owned content ...
<!-- PLATES-CORE:END block-id -->
```

When introducing new reusable process guidance, wrap it in a `PLATES-CORE` block so downstream repositories can apply low-friction partial merges without losing local customizations.
<!-- PLATES-CORE:END upstream-template-sync -->

## Wiki Sync Rules

The **Sync to Wiki on Merge** workflow is opt-in. Agents should not enable broad wiki writes without human approval. Prefer scoped page updates, provenance comments, auditable commits, and reversible changes. If wiki synchronization is requested but not configured, add `need:wiki-sync` and escalate.

## Template Integrity Rules

- Keep `.github/copilot-instructions.md` present and aligned with the repository's real CI/runtime commands.
- Keep `.github/workflows/ci.yml` pointed at executable validation logic (`scripts/validate_plate_repo.sh`) rather than placeholder echo steps.
- For repositories that add runtime manifests, replace placeholder CI/docs claims in the same PR that introduces the runtime.
- Use repository-local temporary paths for scripts and validation helpers; avoid platform-specific assumptions such as `/tmp`.

## Escalation Rules

Escalate to a human when product intent is ambiguous, acceptance criteria conflict, a required label is missing and cannot be inferred, a workflow would need to be weakened, a secret or permission is required, a public claim might change, or the agent cannot produce the required evidence.

## Prohibited Actions

Agents must not merge their own pull requests **unless autonomous mode is active (`.github/AUTONOMOUS_MODE` present on the default branch) and the PR meets all eligibility criteria in §Autonomous Mode above**. Agents must not bypass required checks, remove documentation gates, weaken tests to pass CI, fabricate test results, silently rewrite product intent, expose secrets, enable write automation without approval, create or delete `.github/AUTONOMOUS_MODE` themselves, or treat chat history as more authoritative than repository artifacts. Agents must not close an issue without a corresponding PR that carries a `Closes #N` reference in its body, except for `Feedback Response` PRs. Agents must not open a PR that resolves a specific issue without including `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body, except for `Feedback Response` PRs.
