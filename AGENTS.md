# PLATE Agent Operating Rules

This repository follows the **Process Lifecycle Agentic Task Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, per-feature change files in `.agentic/releases/`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **plate_core runtime implementation** — the shared library, `gh plate` extension, and `plate-mcp` MCP server that implement PLATE platform tooling. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the implementation artifact, and any migration note required for downstream users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update per-feature change files under `.agentic/releases/`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |
| Stack selection | Prototype and benchmark candidate stacks per the Research issue. | Final language/runtime choice and distribution format. |

## Autopilot Doctrine

PLATE defaults to an **autopilot posture**: agents should proceed autonomously through a task queue and pause only at defined human checkpoints, rather than asking permission at each step. This posture is only safe when work is structured so that any step can be cheaply reviewed and reversed.

**Atomic PR discipline.** Structure every session as a sequence of small, independently revertable PRs. A PR should have a single clear purpose. Soft limit: ≤ 10 changed files for implementation work. Prefer many small PRs over one large one. If a branch grows beyond the soft limit, split it before opening the PR.

**Easy revert as the norm.** Prefer squash merges (keeps history clean). Never push directly to `main`. Name branches `type/short-description`. Each squash commit on `main` should read as a complete, stand-alone unit of work.

**PR titles are for humans.** Pull request titles must be clean, concise, and written exclusively for human readers. Do not include any bracketed label-style prefixes (for example `[Feature]`, `[Bug]`, `[Documentation]`, `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or any similar convention). Do not include issue references, closing keywords, or other metadata such as `(Closes #N)`, `Fixes #123`, or equivalent in the title.

All metadata belongs in GitHub's native fields instead:
- PR type via labels (`Bug`, `Feature`, `Documentation`, or `Feedback Response`)

- Linked issues via the Development sidebar or a closing keyword placed only in the PR *body*
- Work-in-progress state via the native Draft PR status
- Epic grouping via milestones

**Agent-specific naming guardrail (Copilot + Grok Build).** GitHub Copilot and Grok Build must both follow the same PR-title rule above. When opening PRs via CLI/API, set a clean human title and put closing keywords only in the PR body. The `PLATE PR Title Check` workflow enforces this.

This keeps titles short, scannable, and focused on the actual change. See #135 (and the follow-up generalization) plus Epic #100.

**Resource consciousness.** Prefer targeted tool calls over exhaustive scans. Batch parallel reads. Stop investigating after sufficient evidence — do not read every file if you already know the answer. Avoid repeatedly regenerating content that has not changed.

**Human checkpoints.** Post a summary comment on the Epic issue when all child issues are resolved. At that point, stop and let the human review before starting the next epic. Do not start a new epic autonomously without instruction.

**Pacing.** Do not create more than five open PRs simultaneously unless they are all marked `auto-merge` and eligible. Sequence work to minimize merge conflicts; prefer additive-first ordering.

**Autonomous mode** (see §Autonomous Mode below) is the formal toggle for the self-merge aspect of this doctrine. The pacing and PR-discipline rules apply in both modes.

**PR Title Conventions.** Use clean, descriptive titles that summarize the change without legacy status prefixes. Do not use `[WIP]`, `WIP:`, `[DRAFT]`, `DRAFT:`, or similar prefixes in PR titles. GitHub provides native first-class Draft PR status for work-in-progress signaling. Create PRs with `gh pr create --draft` or toggle Draft status in the GitHub UI. Draft status is reversible, keeps the title clean, and integrates properly with search, notifications, and commit history. Prefix-based conventions pollute PR lists and weaken readability at a glance.

## Required Work Loop

Follow the loop that matches the issue type.

**Feature**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Feature` and is assigned to the GitHub milestone representing its Epic (enforced by label-check workflow). |
| 2 | Identify acceptance criteria, expected tests, documentation impact, and risk. |
| 3 | Add or update tests before or alongside implementation. |
| 4 | Implement the smallest coherent change that satisfies the issue. |
| 5 | Update per-feature change files in `.agentic/releases/` to describe implemented behavior and verification evidence. |
| 6 | Add or update `.agentic/releases/` when the change affects PLATE process or templates. |
| 7 | Open a PR labeled `Feature` with `Closes #N` in the body. Complete the PR template. When using GitHub CLI, apply the type label in the `gh pr create` command itself rather than relying on a later edit step. |
| 8 | Leave wiki-sync, release-note, and audit evidence for the human reviewer and post-merge workflows. |

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

**Release**

| Step | Required Behavior |
|---|---|
| 1 | Confirm a standing "Next Release" issue exists (titled "Next Release" by default; created at the end of the prior release's finalization or explicitly). Epics and other work declare Major/Minor/Patch track via label and link to it via Development sidebar for negotiation / targeting. |
| 2 | During active development, work lands on the permissive track-specific next- branch (`release-major` / `release-minor` / `release-patch`) matching its label (Epic-close PRs funnel through the track). Run `gh plate release status` regularly to see pending fragments, extension release_checks, linked/targeted Epics, and on-hold work (Epics with a semver label but no link to an active Next Release). |
| 3 | When ready to commit to a release (packaging phase): freeze non-bug merges (ceremony + status + human gates), determine/lock the final semver (cut_release inference from fragments + track labels + Release issue signals), create the concrete versioned branch (`release-vX.Y.Z`, combining tracks as needed for minor/major), rename the standing issue title from "Next Release" to the specific version (e.g. "v0.1.1"), and *immediately create a fresh "Next Release" issue*. |
| 4 | Commit any release notes directory (via `gh plate release cut` or equivalent), then open the Release PR from the versioned branch → `main` (labeled Documentation, body contains `Closes #N` for the now-versioned Release issue). This is a "Release PR" and receives differentiated heavy CI (e2e, security, architecture review, full packaging, etc. after fast-fail gates). |
| 5 | After human approval and merge of the Release PR, enter finalization: PLATE (via `gh plate release finalize` or equivalent) performs the git tag (`git tag vX.Y.Z && git push --tags`), kicks configurable downstream triggers (declared under `.plate/` with common ones in core + others via extensions/release_checks), and ensures the next "Next Release" issue exists. |
| 6 | Create the GitHub Release from the tag (populated from `.agentic/releases/vX.Y.Z/release.json`). |
| 7 | Hard-reset the appropriate branch (the versioned one or the originating next- track) to the tag as needed for the next cycle: e.g. `git checkout release-vX.Y.Z && git reset --hard vX.Y.Z && git push --force-with-lease` (or the legacy single `release` equivalent). |

See `docs/design/release-ceremony-refinement.md` for the full model, branch table, packaging vs. finalization distinction, negotiation/on-hold visibility, and migration notes. The legacy single-`release` + always-versioned-upfront ceremony remains supported during transition.

## Issue Artifact Rules

Every issue must close with a traceable git artifact — either a code change in a PR or a documentation commit. Closing an issue without a corresponding PR is not permitted.

| Issue Type | Required Git Artifact | Typical PR Type Label |
|---|---|---|
| `Feature` | Code change + per-feature change file update in `.agentic/releases/` | `Feature` |
| `Bug` | Bug fix + regression test | `Bug` |
| `Research` | Findings committed to `docs/research/<slug>.md` or `SPEC.md` update | `Documentation` |
| `Design` | Artifact committed to `docs/design/<slug>.md` or `docs/wiki/Features/<feature>.md` | `Documentation` |
| `Question` | Answer artifact committed to `docs/research/<slug>.md` and process updates when guidance changes (`AGENTS.md`, `.agentic/skills.yml`) | `Documentation` |
| `Audit` | Report committed to `docs/audits/<slug>.md` | `Documentation` |
| `Migration` | Update committed to `docs/migration/` | `Documentation` |
| `Epic` | Wiki summary in `docs/wiki/` or epic comment summarizing child outcomes | `Documentation` |
| `Release` | Aggregated `.agentic/releases/vX.Y.Z/` directory + tag + GitHub Release | `Documentation` |

When GitHub's native closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) is present in the PR body and the PR merges to the default branch, GitHub automatically closes the linked issue. **Always include a closing keyword in the PR body.** This is enforced by `.github/workflows/pr-issue-link-check.yml` (warning gate).

Before closing any issue (manually or via linked PR), post a final comment that includes a structured usage block:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Feature` and `Question` issue closures are harvested by `.github/workflows/plates-on-issue-closed.yml` and appended to `.agentic/COSTS.md`.

## Stub Issues

In PLATE, a **Stub** is an issue that still needs a lot of detail. It serves the purposes of:

1. Adding structure while working through uncertainty.
2. Serving as a memory placeholder for humans who want to make a sidenote while they are focused on another task.
3. Providing a surface for pre-planning.

Any kind of Issue — Epic, Feature, Documentation, Bug, Research, Design, Question, Audit, Migration, Release, etc. — can be a Stub. Being a stub just means that it still needs to be defined via the process.

Stubs are a normal and encouraged part of the workflow. They let the project maintain forward structure and memory even when individual items are not yet fully specified. Agents and humans should treat stubs as legitimate, first-class artifacts rather than "incomplete" in a pejorative sense.

### Marking and Working with Stubs
- An issue becomes (or remains) a stub when its description, acceptance criteria, scope, or other key details are still to be worked out.
- Existing `need:*` labels (especially `need:decision`, `need:docs`, `need:tests`, `need:design`) can indicate specific dimensions that still need work.
- The `status:stub` label (see `.github/labels.yml`) can be used to explicitly signal that an issue is intentionally in stub state. (The `status:blocked` and `status:ready-to-work` labels serve related but distinct planning-state purposes.)
- During interactive planning flows (e.g. `plate_plan_epic`), child issues are often created as stubs carrying the `need:refinement` label. The `need:refinement` semantics (deferred gates for full AC and fragments) remain valid for these planning-time stubs.

### Agent and Human Guidance
- When a user asks to "create a stub for X", "stub this out", or "make a placeholder issue", create the issue with the appropriate type label(s), link it to the relevant Epic/milestone where applicable, and leave the body with only the detail that is currently known. Do not over-specify.
- Stubs can (and should) be referenced from other issues, Epics, design docs, or agent sessions.
- Refinement of a stub happens through normal PLATE processes: comments, linked children, dedicated Research/Design work, or follow-up Q&A/contemplation.
- Agents must not treat a stub as ready for implementation work unless the stub status has been removed or the required detail has been supplied.
- When closing a stub, ensure it has a proper traceable git artifact per the Issue Artifact Rules (even if the artifact is simply "this stub was superseded by #N" or a design doc).

Stubs are one of the primary tools PLATE provides for operating effectively in the presence of uncertainty while still preserving GitHub as the single source of truth.

See Feature #351 for the discussion that produced this definition. The two Epic issues #349 and #350 were created as stubs under this understanding.

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

## Branch Model and Ceremonies

PLATE uses a **multi-track release-oriented branch model** (refined in the Release Ceremony Refinement design, see `docs/design/release-ceremony-refinement.md`) to keep parallel epic work isolated while providing always-available "Next" targets for scope negotiation and explicit Major/Minor/Patch release tracks.

### Branch tiers (current refined model)

| Branch | Purpose | Who merges into it |
|---|---|---|
| `epic/<short-name>` | Owned by one Epic. Feature/Bug PRs for that Epic typically target a track-specific next- branch (see below) after receiving a Major/Minor/Patch label. | Feature/Bug PRs (squash), funneled by track label |
| `release-major`, `release-minor`, `release-patch` | Permissive "next" integration branches associated with the standing "Next Release" issue. Work labeled with the matching semver track targets the corresponding branch during active development / scope negotiation. These act as the "dumping ground" until packaging. | Work carrying the matching Major/Minor/Patch label (plus epic-close PRs for that track) |
| `release-vX.Y.Z` (or equivalent versioned) | Concrete, tighter integration branch created during the packaging phase for a specific release. Receives the final stabilization work and is the source of the Release PR to main. | Final stabilization changes for that versioned release |
| `main` | Stable, tagged history. Every commit on `main` is a semver release. | Release PRs only (squash) from a versioned release branch |

**Legacy single `release` branch** remains supported during transition for repos not yet adopting the multi-track model. See the design doc and migration guidance in the release-ceremony-refinement fragment for adoption steps. The persistent `release` (when present) continues to point at the tip that will become (or most recently became) a tag.

### Epic-close ceremony

When all child issues for an Epic are resolved:
1. Confirm all Feature/Bug PRs for the Epic are merged into `epic/<name>`.
2. Post a summary comment on the Epic issue with outcomes and any migration notes.
3. Open a PR from `epic/<name>` → `release`. Label it `Feature` or `Documentation` as appropriate.
4. Human reviews and squash-merges. The Epic issue closes via `Closes #N` in the PR body.

### Release ceremony (refined multi-track model)

See the detailed steps in the **Release** work loop table above and the full model in `docs/design/release-ceremony-refinement.md`. High-level flow:

1. Standing "Next Release" issue exists and is the target for Epics (via sidebar links) and track-labeled work (Major/Minor/Patch labels drive landing on the matching `release-major` / `release-minor` / `release-patch` permissive next- branches).
2. Packaging (the decision + freeze + version lock point): determine semver, create versioned `release-vX.Y.Z` branch (combining tracks for minor/major as appropriate), rename the issue to the concrete version, immediately spawn a fresh "Next Release" issue.
3. Release PR from the versioned branch → `main` (this PR carries the `Release` label/context and receives heavy CI).
4. Human merge.
5. Finalization: tag, configurable downstream triggers (`.plate/` + extensions), ensure next Next Release exists, hard-reset the relevant branch.
6. GitHub Release created from the aggregated notes.

Legacy single-`release` + upfront versioned Release issue flow remains valid for transition (see migration guidance in the release-ceremony-refinement fragment).

### Standing release-track state

- `gh plate bootstrap --apply` is the canonical owner for initial standing release-track branches (`release-major`, `release-minor`, `release-patch`, and legacy `release`) and related bootstrap-time release metadata.
- PLATE should maintain exactly one open `Release` issue titled `Next Release` as the standing target for release negotiation. Do not create separate default Major/Minor/Patch release issues; track intent belongs on work items via labels and the matching branches.
- Treat a repository as never initialized only when release-track branches, Release issue history, and versioned release history are all absent. Partial standing state or missing artifacts after prior release activity is drift and should be repaired, not re-bootstrapped blindly.
- Until dedicated init/repair automation exists, repair missing standing state by running bootstrap for branches/labels, creating exactly one `Next Release` issue manually, and verifying the result with `gh plate release status`.

### Release branch protection guidance

The next-* (permissive integration) and versioned `release-vX.Y.Z` branches (and the legacy single `release` during transition) should be protected with:
- PRs required (no direct push).
- Appropriate source restrictions (e.g. epic/* or track-consistent branches for next-*; limited stabilization changes for versioned branches).
- Status checks: same as `main` (plus the differentiated heavy CI jobs for Release contexts).

See the design doc and bootstrap output for current recommended protection details. The "only epic-close" restriction is relaxed for the multi-track model in favor of track labels + the final Release PR gate.

### Fragment authoring

Every Feature (or process-changing) PR that changes PLATE process, templates, or agent surfaces must include a fragment under `.agentic/releases/unreleased/<slug>.json`. See `.agentic/releases/unreleased/README.md` for the schema and field guide. This includes all changes in a Release ceremony refinement Epic (new labels, branch model updates, CI conditions, tooling enhancements, milestone rules, .plate config, etc.). Fragments accumulate across the Epic's lifetime and are swept into the versioned directory at release-cut time.

The canonical design artifact for Release ceremony changes lives in `docs/design/release-ceremony-refinement.md`.



Preferred flow is now **local babysitting** driven by `gh plate pr babysit <number>`. CI is intentionally narrowed to enforcement-only (`feedback-resolution` check). The `plate` agent persona (plugin/agents/plate.agent.md and mirror) no longer includes babysitting steps (deprecated in favor of the dedicated local CLI/MCP flow; see PR #120 and this PR's Q&A/Curiosity updates).

Use this loop:

1. Start or join babysitting locally (`gh plate pr babysit <number> [--act] [--watch] [--branch-update-strategy <strategy>]`) using MCP tools `plate_pr_babysit` + `plate_resolve_review_thread` (the `/agent plate` persona focuses on health/epic/features/delegation + native Q&A/curiosity per recent guidance).

Information Audits (#218) are now part of the core capability: agents should use `plate_perform_information_audit` (dry_run first) to discover gaps against the Goals page (#224) and generate Questions. Guidance in plugin/agents/plate.agent.md and agent_guidance.py (INFORMATION_AUDIT_GUIDANCE). Catalog defaults (#222) and extensibility (#226) apply.
2. The babysitter automatically detects two types of issues:
   - **Unresolved review threads** from third-party agents (actionable feedback)
   - **Base branch out-of-sync** state (PR branch behind, conflicting, or dirty relative to base branch)
3. Review all open inline comments and the overall review body from the named reviewer on the linked PR
4. For any comment that includes a GitHub code suggestion (` ```suggestion ` block): apply it directly as a commit **unless** the suggestion introduces a bug or relies on a false assumption — if you skip a suggestion, reply to that thread with a brief explanation
5. For all other actionable comments: push a code change or reply explaining why no change is needed
6. After addressing each comment (via code change, applied suggestion, or explanatory reply), resolve its review thread using the GitHub GraphQL `resolveReviewThread` mutation:
   ```graphql
   mutation { resolveReviewThread(input: { threadId: "THREAD_NODE_ID" }) { thread { isResolved } } }
   ```
   To find `THREAD_NODE_ID` for a given comment, query `repository.pullRequest.reviewThreads` and match on `comments.nodes.databaseId`.
7. **Push all changes to the existing PR branch** — do not open a new issue or a new PR for the feedback response
8. For items requiring human judgment (credentials, architectural decisions, security changes), add `need:human-review` to the PR and leave a comment identifying what is blocked

**Base Branch Sync Handling:**

The babysitter detects when a PR branch is out of sync with its base branch (via `mergeStateStatus`: BEHIND, CONFLICTING, or DIRTY). The default behavior is controlled by `--branch-update-strategy`:

- **copilot-request** (default): Post a `@copilot` trigger comment requesting native GitHub/Copilot branch update assistance. This is safe, auditable, and reversible.
- **local-rebase**: Local worktree rebase and push (implemented using isolated git worktree; reports success/conflict/error via BabysitReport fields; raises only on non-git env or fatal error).
- **none**: Detect and report only, take no action

When `--act` is specified and the PR is out of sync, the babysitter posts a merge trigger comment (deduplicated by marker) to prompt resolution. This ensures the babysitting loop can continue without manual branch update intervention.

**Lifecycle contract:**

| Stage | Expected artifact |
|---|---|
| Babysitter cycle runs | Local `gh plate pr babysit` (or MCP `plate_pr_babysit`) detects actionable third-party feedback and can post a babysit trigger comment |
| Copilot addresses feedback | Commits pushed to the same PR branch; review threads resolved |
| Escalation | `need:human-review` label + blocking comment when human judgment is required |
| Completion | `feedback-resolution` check is green (no unresolved review threads, no `CHANGES_REQUESTED` decision), then original PR merges through normal checks |

`Feedback Response` labels remain available process metadata. Feedback is addressed inline on the original PR branch.

**Legacy workflow:** `.github/workflows/plates-address-pr-feedback.yml` is deprecated and manual-only (`workflow_dispatch`) for fallback troubleshooting. Do not rely on it for normal operations.

**Configuration:** Set the `PLATE_PR_FEEDBACK_AGENTS` repository variable to a comma-separated list of GitHub logins whose feedback should be babysat by default (e.g., `devin-ai-integration[bot],openhands-agent`).

**Merge safety gate:** Require `.github/workflows/feedback-resolution-check.yml` (`feedback-resolution`) in branch protection for `main` so merge/auto-merge waits until all active review threads are resolved.

## Label Rules

Use labels as stable process metadata. Do not create ad hoc labels unless they change routing, enforcement, reporting, auditing, review burden, or agent behavior. Use GitHub Projects fields for frequently changing planning state such as priority, owner, rank, iteration, target date, or release target. The `status:blocked` and `status:ready-to-work` labels are the explicit exception used by PLATES native trigger workflows.

| Label Family | Usage |
|---|---|
| `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Audit`, `Migration`, `Feedback Response` | Exactly one required issue type label. |
| `Bug`, `Feature`, `Documentation`, `Feedback Response` | Exactly one required pull request type label. |
| `Feedback Response` | Combined issue + PR type for feedback-response process work when needed. Not auto-created by the deprecated legacy workflow; no Epic milestone required. |
| `Epic: short-name` | Legacy/supplemental Epic identity label (optional). GitHub Milestones are the canonical Epic container (see Epic #100 / native GitHub PR integration). Feature, Epic, and Release issues require milestone assignment instead. |
| `area:*` | Stable subsystem or ownership area. |
| `risk:*` | Review burden and release caution. |
| `need:*` | Missing input or required follow-up. |

## Documentation Rules

Every Feature pull request that changes PLATE process, templates, or agent surfaces must author a fragment under `.agentic/releases/unreleased/<slug>.json`. Documentation pull requests must commit a file to the appropriate `docs/` subdirectory and should explain whether they update process artifacts, product documentation, wiki source material, or public-facing claims. Changes that alter PLATE behavior or process should also add or update a fragment. If a change affects feature behavior, update both implementation evidence and documentation evidence.

**Fragment-first authoring:** The canonical documentation path for PLATE changes is `.agentic/releases/unreleased/<slug>.json`. These fragments accumulate across the Epic and are aggregated at release-cut time into `.agentic/releases/vX.Y.Z/`. Use `scripts/render_release_notes.py .agentic/releases/` to preview the rendered notes at any time.

See §Issue Artifact Rules for the full mapping of issue type to required artifact location.

When opening pull requests through GitHub CLI, prefer an atomic command such as `gh pr create --label "Feature"` or `gh pr create --label "Documentation"`. If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before any other work.

**Important:** The checkboxes in the PR template body do **not** apply GitHub labels. Labels must be set explicitly via the CLI or GitHub API.

For **every new pull request**, add exactly one required PR type label (`Bug`, `Feature`, `Documentation`, or `Feedback Response`) at creation time. Unlabeled or multiply-labeled PRs fail CI immediately.

For `Feature`, `Bug`, and issue-driven `Documentation` PRs, add the relevant milestone as well. Current rollout is warning-first: the PR issue-link workflow warns when the milestone is missing rather than failing immediately.

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
4. Update per-feature change files in `.agentic/releases/` with imported behavior and evidence links.
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

The `docs/wiki/Goals.md` page (PLATE convention from #224/#229/#266) is a recommended default-scoped file for wiki sync when present. Bootstrap seeds it (with flag/interactive support) when wiki is enabled and the page is absent. Health surfaces report `goals_page_present` as a nudge for adoption. Agents should read it as primary signal for Information Audits (#218).

## Escalation Rules

Escalate to a human when product intent is ambiguous, acceptance criteria conflict, a required label is missing and cannot be inferred, a workflow would need to be weakened, a secret or permission is required, a public claim might change, or the agent cannot produce the required evidence.

## Prohibited Actions

Agents must not merge their own pull requests **unless autonomous mode is active (`.github/AUTONOMOUS_MODE` present on the default branch) and the PR meets all eligibility criteria in §Autonomous Mode above**. Agents must not bypass required checks, remove documentation gates, weaken tests to pass CI, fabricate test results, silently rewrite product intent, expose secrets, enable write automation without approval, create or delete `.github/AUTONOMOUS_MODE` themselves, or treat chat history as more authoritative than repository artifacts. Agents must not close an issue without a corresponding PR that carries a `Closes #N` reference in its body. Agents must not open a PR that resolves a specific issue without including `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body.