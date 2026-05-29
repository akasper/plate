# PLATE Agent Operating Rules

This repository follows the **Process Lifecycle Agentic Task Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, `CURRENT.md`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **plate_core runtime implementation** — the shared library, `gh plate` extension, and `plate-mcp` MCP server that implement PLATE platform tooling. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the implementation artifact, and any migration note required for downstream users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update `CURRENT.md`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |
| Stack selection | Prototype and benchmark candidate stacks per the Research issue. | Final language/runtime choice and distribution format. |

## Autopilot Doctrine

PLATE defaults to an **autopilot posture**: agents should proceed autonomously through a task queue and pause only at defined human checkpoints, rather than asking permission at each step. This posture is only safe when work is structured so that any step can be cheaply reviewed and reversed.

**Atomic PR discipline.** Structure every session as a sequence of small, independently revertable PRs. A PR should have a single clear purpose. Soft limit: ≤ 10 changed files for implementation work. Prefer many small PRs over one large one. If a branch grows beyond the soft limit, split it before opening the PR.

**Easy revert as the norm.** Prefer squash merges (keeps history clean). Never push directly to `main`. Name branches `type/short-description`. Each squash commit on `main` should read as a complete, stand-alone unit of work.

**Resource consciousness.** Prefer targeted tool calls over exhaustive scans. Batch parallel reads. Stop investigating after sufficient evidence — do not read every file if you already know the answer. Avoid repeatedly regenerating content that has not changed.

**Human checkpoints.** Post a summary comment on the Epic issue when all child issues are resolved. At that point, stop and let the human review before starting the next epic. Do not start a new epic autonomously without instruction.

**Pacing.** Do not create more than five open PRs simultaneously unless they are all marked `auto-merge` and eligible. Sequence work to minimize merge conflicts; prefer additive-first ordering.

**Autonomous mode** (see §Autonomous Mode below) is the formal toggle for the self-merge aspect of this doctrine. The pacing and PR-discipline rules apply in both modes.

## Required Work Loop

Follow the loop that matches the issue type.

**Feature**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Feature` and assigned to the correct Epic milestone. |
| 2 | Identify acceptance criteria, expected tests, documentation impact, and risk. |
| 3 | Add or update tests before or alongside implementation. |
| 4 | Implement the smallest coherent change that satisfies the issue. |
| 5 | Update `CURRENT.md` to describe the implemented behavior and verification evidence. |
| 6 | Open a PR labeled `Feature` with `Closes #N` in the body. Complete the PR template. When using GitHub CLI, apply the type label in the `gh pr create` command itself rather than relying on a later edit step. |
| 7 | Leave wiki-sync, release-note, and audit evidence for the human reviewer and post-merge workflows. |

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
| `Epic` | Milestone-backed wiki summary in `docs/wiki/` or epic comment/design artifact summarizing child outcomes | `Documentation` |

GitHub Milestones are the canonical Epic container. Assign the matching milestone to every issue and pull request that belongs to an Epic. Do not create new `Epic: short-name` labels; existing `Epic:` labels are legacy metadata only.

When GitHub's native closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) is present in the PR body and the PR merges to the default branch, GitHub automatically closes the linked issue. Use a closing keyword whenever the PR should close the issue on merge. If the work should stay open after the PR lands, link the issue from the PR's Development sidebar instead. `.github/workflows/pr-issue-link-check.yml` enforces that `Feature`, `Bug`, and issue-driven `Documentation` PRs link at least one issue.

Before closing any issue (manually or via linked PR), post a final comment that includes a structured usage block:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Feature` and `Question` issue closures are harvested by `.github/workflows/plates-on-issue-closed.yml` and appended to `.agentic/COSTS.md`.

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

- Labeled `risk:low`
- Does not modify `AGENTS.md`, `SPEC.md`, `.github/CODEOWNERS`, or any workflow file
- Does not add, remove, or alter credential handling, payment logic, authentication, or security controls
- Does not carry `need:human-review` or `need:security-review`
- Does not change public-facing claims in `README.md` or marketing documentation

**How to auto-merge an eligible PR in autonomous mode:**

```bash
gh pr create --label "risk:low" --label "auto-merge" [other required labels] ...
gh pr merge --auto --squash <PR_NUMBER>
```

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

## Label Rules

Use labels as stable process metadata. Do not create ad hoc labels unless they change routing, enforcement, reporting, auditing, review burden, or agent behavior. Use GitHub Projects fields for frequently changing planning state such as priority, owner, rank, iteration, target date, or release target. The `status:blocked` and `status:ready-to-work` labels are the explicit exception used by PLATES native trigger workflows.

| Label Family | Usage |
|---|---|
| `Bug`, `Feature`, `Epic`, `Research`, `Design`, `Question`, `Audit`, `Migration`, `Feedback Response` | Exactly one required issue type label. |
| `Bug`, `Feature`, `Documentation`, `Feedback Response` | Exactly one required pull request type label. |
| `Feedback Response` | Combined issue + PR type for feedback-response process work when needed. Not auto-created by `plates-address-pr-feedback.yml` in the inline response flow. No `Epic:` label required. |
| `area:*` | Stable subsystem or ownership area. |
| `risk:*` | Review burden and release caution. |
| `need:*` | Missing input or required follow-up. |
| `no-issue` | Explicit exemption for PRs that intentionally do not resolve tracked work. |

## Documentation Rules

Every Feature pull request must modify `CURRENT.md`. Documentation pull requests must commit a file to the appropriate `docs/` subdirectory and should explain whether they update process artifacts, product documentation, wiki source material, or public-facing claims. If a change affects feature behavior, update both implementation evidence and documentation evidence.

See §Issue Artifact Rules for the full mapping of issue type to required artifact location.

When opening pull requests through GitHub CLI, prefer an atomic command such as `gh pr create --label "Feature"` or `gh pr create --label "Documentation"`. If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before any other work.

**Important:** The checkboxes in the PR template body do **not** apply GitHub labels. Labels must be set explicitly via the CLI or GitHub API.

For **every new pull request**, add exactly one required PR type label (`Bug`, `Feature`, `Documentation`, or `Feedback Response`) at creation time. Unlabeled or multiply-labeled PRs fail CI immediately.

When the PR belongs to an Epic, set the pull request milestone to the matching Epic milestone. For `Feature`, `Bug`, `Design`, and `Research` work, link at least one issue using a closing keyword or the Development sidebar. Reserve `no-issue` for true chores, dependency bumps, or maintenance work that intentionally does not resolve a tracked issue.

## CLI Body Patterns (PowerShell safety)

When constructing `gh pr create` (or `gh issue create`) commands with multiline bodies, **never** embed literal `\n` sequences inside double-quoted strings from PowerShell. PowerShell does not interpret `\n` as a newline in this context; GitHub receives the literal backslash-n characters and the rendered description is broken (Bug #62).

**Recommended safe pattern (all environments):**

```bash
cat > /tmp/body.md << 'EOF'
## Summary
- First point
- Second point with details
EOF
gh pr create --body-file /tmp/body.md --label Documentation ...
```

**PowerShell here-string (avoids all escaping pitfalls):**

```powershell
$body = @"
## Summary
- First point
- Second point
"@
Set-Content -Path $env:TEMP\body.md -Value $body -Encoding UTF8
gh pr create --body-file $env:TEMP\body.md ...
```

Use `--body-file` (or the equivalent here-string + temp file) for every agent-authored multiline body. Update examples in this file and downstream docs when they are refreshed from upstream.

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

## Escalation Rules

Escalate to a human when product intent is ambiguous, acceptance criteria conflict, a required label is missing and cannot be inferred, a workflow would need to be weakened, a secret or permission is required, a public claim might change, or the agent cannot produce the required evidence.

## Prohibited Actions

Agents must not merge their own pull requests **unless autonomous mode is active (`.github/AUTONOMOUS_MODE` present on the default branch) and the PR meets all eligibility criteria in §Autonomous Mode above**. Agents must not bypass required checks, remove documentation gates, weaken tests to pass CI, fabricate test results, silently rewrite product intent, expose secrets, enable write automation without approval, create or delete `.github/AUTONOMOUS_MODE` themselves, or treat chat history as more authoritative than repository artifacts. Agents must not close an issue without a corresponding PR that carries a `Closes #N` reference in its body. Agents must not open a PR that should close a specific issue on merge without including `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body. When a PR contributes to but should not close an issue, a Development sidebar link satisfies the linking requirement.
