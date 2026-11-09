# PLATE Agent Operating Rules

This repository follows the **Product Lifecycle Automation Toolkit and Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, per-feature change files in `.agentic/releases/`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## On-demand agent rules

These pages hold the full rule text moved out of the always-loaded core. Open by name when the task needs ceremony detail, babysit loops, autonomy, scripts, or similar.

| Page | When to load |
|---|---|
| [real-world-tasks.md](agents/real-world-tasks.md) | Epic planning with human-only external Tasks (#625-style blockers). |
| [default-plate-persona.md](agents/default-plate-persona.md) | Default `plate` persona, opt-out, and host auto-discovery. |
| [autopilot-doctrine.md](agents/autopilot-doctrine.md) | Atomic PR discipline, PR titles, pacing, and human checkpoints. |
| [task-management.md](agents/task-management.md) | `todo_write` requirements for multi-step agent work (#515). |
| [stub-issues.md](agents/stub-issues.md) | Stub issues, `status:stub`, and `need:refinement`. |
| [pm-orchestration.md](agents/pm-orchestration.md) | Project Manager / `plate_pm_*` orchestration (#660 / #662). |
| [autonomous-mode.md](agents/autonomous-mode.md) | AutonomyEngine, `.plate` autonomy config, and auto-merge eligibility. |
| [branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md) | Release branches, epic-close, release ceremony, and `gh plate release status` (#513). |
| [pr-feedback-and-babysit.md](agents/pr-feedback-and-babysit.md) | PR-green loop, `gh plate pr babysit`, address-pr-feedback skill, and merge gates. |
| [github-actions-and-copilot.md](agents/github-actions-and-copilot.md) | Actions cost controls and Copilot review / autostart policy. |
| [documentation-rules.md](agents/documentation-rules.md) | Fragments, PR labels, milestones, and release-status targeting for docs PRs. |
| [script-policy.md](agents/script-policy.md) | POSIX vs PowerShell script policy and `.plate` `platform`. |
| [database-migration-naming.md](agents/database-migration-naming.md) | UTC timestamp + slug filenames for new DB migrations (#1451). |
| [cli-body-patterns.md](agents/cli-body-patterns.md) | Safe multiline `gh pr create` / issue bodies (#62). |
| [upstream-template-sync.md](agents/upstream-template-sync.md) | `import-payload`, `self-migrate`, and PLATES-CORE marker sync. |
| [wiki-sync.md](agents/wiki-sync.md) | Opt-in wiki sync and Goals page convention. |

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **plate_core runtime implementation** — the shared library, `gh plate` extension, and `plate-mcp` MCP server that implement PLATE platform tooling. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the implementation artifact, and any migration note required for downstream users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update per-feature change files under `.agentic/releases/`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |
| Stack selection | Prototype and benchmark candidate stacks per the Research issue. | Final language/runtime choice and distribution format. |


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
| 7 | Determine the correct base branch using `gh plate release status` (or by inspecting any Major/Minor/Patch label on the issue — see [branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md)). For repositories on the legacy single-`release` model (the current state of this repo), target `release`. For multi-track, target the matching `release-major` / `release-minor` / `release-patch`. Open a PR labeled `Feature` **targeting that base branch** (`--base <base>` or equivalent in `gh pr create`, where <base> comes from the status command) with `Closes #N` in the body. Complete the PR template. When using GitHub CLI, apply the type label in the `gh pr create` command itself rather than relying on a later edit step. Prefer `gh plate pr create …` or run `gh plate pr preflight` before `gh pr create` so plate-pr-gates and labels checks fail locally first (#1418). |
| 8 | After the PR is green (including feedback-resolution for agent threads), wait for human review/approval (at minimum one `Approved` review or explicit human merge). Do not self-merge. Use `need:human-review` for escalation. See authority table, [autopilot-doctrine.md](agents/autopilot-doctrine.md), and [autonomous-mode.md](agents/autonomous-mode.md). |
| 9 | Leave wiki-sync, release-note, and audit evidence for the human reviewer and post-merge workflows. |

**Bug**

Reproduce the failure or document why reproduction is not yet possible. Add a regression test. Include `Closes #N` in the PR body. Label missing information with `need:reproduction`, `need:tests`, or `need:human-review`.

After making the PR green (including feedback-resolution for any agent threads), **do not self-merge**. Wait for human review/approval (at minimum one `Approved` review from a human, or explicit human `gh pr merge`). Epics and Releases require at least one review as well. Use `need:human-review` for escalation. See [autopilot-doctrine.md](agents/autopilot-doctrine.md) human checkpoints and [autonomous-mode.md](agents/autonomous-mode.md).

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

For PLATE Q&A: consistently default to native TUI (ask_user_question arrow-key forms) and enforce full follow-through on answers (artifacts per ACs) without reminder. Open with native TUI first—never plain-text options that only “upgrade” after the user asks (#509). Offer only options whose full execution+artifacts complete in-turn before further Q&A/progress. If option promises review/babysit/address feedback, *must* fully execute via pr-babysit skill + worktree + push same branch + resolve threads before next question or progress/done. Never merge unaddressed. Prefer `plate_resolve_review_thread` / babysit `--act` so feedback-resolution does not stay red after you addressed comments (#511). Named checklists: Q&A Follow-Through (#508) + Merge Gates one-pass (#510); parent doc gap #512 closed by that package — see `docs/research/508-510-qa-and-pr-green-follow-through.md`. (Addresses #503, #518, #517, #521 and closes the post-0.6.1 Q&A/babysit stub cluster under #580/#569 polish.)

**Task**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Task` and represents a human-only blocker or an explicitly requested human action item. |
| 2 | Ensure the issue includes: human action required, why the agent cannot safely proceed, context and affected artifacts, best-effort instructions, done signal, and related links. |
| 3 | Link the relevant artifacts in the body and inherit the Epic milestone when the Task is clearly Epic-related. Do not require an `Epic: <slug>` label. |
| 4 | Redact and summarize sensitive provenance when the blocker involves credentials, infrastructure, or other secret-bearing systems. |
| 5 | When the work is complete, add a short completion comment containing `<!-- PLATE-TASK-CLOSED -->` and then close the issue directly. |
| 6 | If completing the Task changes repository truth, open a follow-up PR or documentation change as appropriate instead of relying on the Task issue alone. |

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
| 4 | Commit any release notes directory (via `gh plate release cut` or equivalent), then open the Release PR from the versioned branch → `main` (labeled `Documentation` and `Release`, body contains `Closes #N` for the now-versioned Release issue). The `Release` label (in addition to the Documentation PR type) ensures the differentiated heavy CI jobs (`validate-release-pr`, `heavy-release`) execute rather than skipping (see #532). This is a "Release PR" and receives differentiated heavy CI (e2e, security, architecture review, full packaging, etc. after fast-fail gates). |
| 5 | After human approval and merge of the Release PR, GitHub Actions creates and pushes `vX.Y.Z` from the merged Release PR commit. Finalization (`gh plate release finalize` or equivalent) then handles downstream triggers (declared under `.plate/` with common ones in core + others via extensions/release_checks), rollover/repair, and ensuring the next "Next Release" issue exists. |
| 6 | Create the GitHub Release from the tag (populated from `.agentic/releases/vX.Y.Z/release.json`). |
| 7 | Hard-reset the appropriate branch (the versioned one or the originating next- track) to the tag as needed for the next cycle: e.g. `git checkout release-vX.Y.Z && git reset --hard vX.Y.Z && git push --force-with-lease` (or the legacy single `release` equivalent). |

See `docs/design/release-ceremony-refinement.md` for the full model, branch table, packaging vs. finalization distinction, negotiation/on-hold visibility, and migration notes. The legacy single-`release` + always-versioned-upfront ceremony remains supported during transition.

## Issue Artifact Rules

Every issue must close with a traceable artifact. For most issue types this is a code change in a PR or a documentation commit. `Task` issues instead close with a completion comment containing `<!-- PLATE-TASK-CLOSED -->`, unless repository truth also changed and needs a PR-backed artifact.

| Issue Type | Required Git Artifact | Typical PR Type Label |
|---|---|---|
| `Feature` | Code change + per-feature change file update in `.agentic/releases/` | `Feature` |
| `Bug` | Bug fix + regression test | `Bug` |
| `Research` | Findings committed to `docs/research/<slug>.md` or `SPEC.md` update | `Documentation` |
| `Design` | Artifact committed to `docs/design/<slug>.md` or `docs/wiki/Features/<feature>.md` | `Documentation` |
| `Question` | Answer artifact committed to `docs/research/<slug>.md` and process updates when guidance changes (`AGENTS.md`, `.agentic/skills.yml`) | `Documentation` |
| `Task` | Completion comment on the GitHub issue containing `<!-- PLATE-TASK-CLOSED -->`; add a PR or documentation artifact only when repository truth changes | `Documentation` when follow-up docs are needed, otherwise none |
| `Audit` | Report committed to `docs/audits/<slug>.md` | `Documentation` |
| `Migration` | Update committed to `docs/migration/` | `Documentation` |
| `Epic` | Wiki summary in `docs/wiki/` or epic comment summarizing child outcomes | `Documentation` |
| `Release` | Aggregated `.agentic/releases/vX.Y.Z/` directory + tag + GitHub Release | `Documentation` |

When GitHub's native closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) is present in the PR body and the PR merges to the default branch, GitHub automatically closes the linked issue. **Always include a closing keyword in the PR body** when a PR is the intended closure path. This is enforced by `.github/workflows/pr-issue-link-check.yml` (warning gate). `Task` issues are exempt when they close via the Task completion comment instead.

Before closing any issue through an agent-run implementation or answer flow, post a final comment that includes a structured usage block:

```text
=== USAGE REPORT ===
tokens: <integer>
cost: <$0.00>
duration: <hh:mm:ss>
=== END USAGE REPORT ===
```

`Feature` and `Question` issue closures are harvested by `.github/workflows/plates-on-issue-closed.yml` and appended to `.agentic/COSTS.md`.
`Task` issues are exempt from the usage-report requirement and instead require the lightweight Task completion comment.

## Merge and feedback gates

- After a Bug, Feature, or Documentation PR is green (including agent-thread **feedback-resolution**), **do not self-merge** — wait for human review/approval (minimum one `Approved` review or explicit human merge). Epics and Releases require at least one review as well. Use `need:human-review` to escalate.
- The **feedback-resolution** check (third-party agent review threads) is separate from the human approval requirement; both apply where relevant. Full loop, babysit tooling, and pre-merge recheck: [pr-feedback-and-babysit.md](agents/pr-feedback-and-babysit.md).

## UI screenshots in pull requests (#1050)

User-visible UI changes require inline visual proof on the pull request.

**Required captures:** desktop viewport width, **320px** mobile viewport width, embedded **inline** in the PR description or PR comments; include **before and after** images when the change alters existing UI.

**Upload (never commit binaries):** Run `gh --version` first (**gh >= 2.99** required for `--attach`). Attach when creating, editing, or commenting:

```bash
gh pr create --attach ./desktop-after.png --attach ./mobile-320-after.png ...
gh pr edit <number> --attach ./shot.png
gh pr comment <number> --attach ./shot.png
```

**Forbidden:** committing screenshot files to git; relative repository paths in markdown image embeds; `raw.githubusercontent.com` or `blob/...?raw=true` URLs for PR evidence.

**Token matrix (who can `--attach`):**

| Agent context | PAT / host | Can use `gh --attach`? |
|---|---|---|
| Local CLI agents | `gho_`, `ghp_`, `github_pat_` | Yes |
| GitHub Copilot cloud coding agent | Copilot-hosted | Yes |
| Third-party cloud agents (Cursor, Amp, Devin, etc.) | No user PAT on hosted runners | No |

Third-party cloud agents do not receive a user PAT; they cannot upload PR attachments.

**Routing UI work to Copilot:** Assign UI-heavy issues to **GitHub Copilot's cloud coding agent** (assign the issue to Copilot on GitHub). An agent that cannot use `gh pr create|edit|comment --attach` must hand off UI screenshot work to Copilot (or a human with local `gh` and a PAT) rather than committing images or using broken URL embeds.

## Label Rules

Use labels as stable process metadata. Do not create ad hoc labels unless they change routing, enforcement, reporting, auditing, review burden, or agent behavior. Use GitHub Projects fields for frequently changing planning state such as priority, owner, rank, iteration, target date, or release target. The `status:blocked`, `status:ready-to-work`, and `status:implemented` (auto-set on release-branch merge per #556; means landed in RC but not yet shipped to main+tag) labels are the explicit exception used by PLATES native trigger workflows.

**Issue `status:*` lifecycle (#1385):** At most one of `status:stub`, `status:blocked`, `status:ready-to-work`, or `status:implemented` may appear on an issue (enforced by `label-check`). The integration merge job in `plate-pr-gates` adds `status:implemented` only for issues that are not typed Epic, Task, or Release; those types keep the issue open when `Closes` lands on a release branch until their own ceremony. Push events to integration branches do not carry a merged PR body, so that job skips parsing `Closes` keywords (use the merge-closed pull_request event or link issues another way).

| Label Family | Usage |
|---|---|
| `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Task`, `Audit`, `Migration`, `Feedback Response` | Exactly one required issue type label. |
| `Bug`, `Feature`, `Documentation`, `Feedback Response` | Exactly one required pull request type label. |
| `Feedback Response` | Combined issue + PR type for feedback-response process work when needed. Not auto-created by the deprecated legacy workflow; no Epic milestone required. |
| `Epic: short-name` | Legacy/supplemental Epic identity label (optional). GitHub Milestones are the canonical Epic container (see Epic #100 / native GitHub PR integration). Feature, Epic, and Release issues require milestone assignment instead. |
| `area:*` | Stable subsystem or ownership area. |
| `risk:*` | Review burden and release caution. |
| `need:*` | Missing input or required follow-up. |

## Escalation Rules

Escalate to a human when product intent is ambiguous, acceptance criteria conflict, a required label is missing and cannot be inferred, a workflow would need to be weakened, a secret or permission is required, a public claim might change, or the agent cannot produce the required evidence.

## Prohibited Actions

Agents must not merge their own pull requests **unless autonomous mode is active and the PR meets all eligibility criteria in [autonomous-mode.md](agents/autonomous-mode.md)**. Agents must not bypass required checks, remove documentation gates, weaken tests to pass CI, fabricate test results, silently rewrite product intent, expose secrets, enable write automation without approval, create or delete `.github/AUTONOMOUS_MODE` themselves, or treat chat history as more authoritative than repository artifacts. Agents must not clone, fork, or `gh repo create --template` from `akasper/plate_template` (or any template repo), and must not hand-copy PLATE payload files—use `gh plate bootstrap` and `gh plate import-payload` only. Agents must not close an issue without the required closure artifact: for most issue types, a corresponding PR that carries a `Closes #N` reference in its body; for `Task` issues, a completion comment containing `<!-- PLATE-TASK-CLOSED -->`. Agents must not open a PR that resolves a specific issue without including `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body.