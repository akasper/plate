# PLATE Agent Operating Rules

This repository follows the **Product Lifecycle Automation Toolkit and Engine (PLATE)** methodology. The local operating doctrine is simple: **humans keep judgment, agents do the toil, and GitHub preserves truth**.

Agents working here should treat repository artifacts as durable project memory, not as optional narrative. Issues, labels, tests, pull requests, per-feature change files in `.agentic/releases/`, wiki pages, release notes, audit outputs, and traceability records are the inspectable record of the project.

## On-demand agent rules

These pages hold the full rule text moved out of the always-loaded core. Open by name when the task needs ceremony detail, feedback handling, autonomy, scripts, E2E demos, or similar.

| Page | When to load |
|---|---|
| [autopilot-doctrine.md](agents/autopilot-doctrine.md) | Atomic PR discipline, PR titles, pacing, and human checkpoints. |
| [e2e-and-demo-gifs.md](agents/e2e-and-demo-gifs.md) | Playwright E2E expectations and demo GIF recording for UI features. |
| [plate-process-contract.md](agents/plate-process-contract.md) | Process contract table, Task/Spike/Stub semantics, and usage reports. |
| [risk-assessment-and-labeling.md](agents/risk-assessment-and-labeling.md) | `risk:*` label family definitions and when to apply each level. |
| [autonomous-mode.md](agents/autonomous-mode.md) | `.github/AUTONOMOUS_MODE` toggle and auto-merge eligibility. |
| [third-party-agent-feedback.md](agents/third-party-agent-feedback.md) | Inline feedback response, PLATES-CORE tstack blocks, and merge gates. |
| [interactive-epic-planning.md](agents/interactive-epic-planning.md) | Host-native epic planning Q&A and stub creation (#988). |
| [documentation-rules.md](agents/documentation-rules.md) | Fragments, PR labels, milestones, and release-status targeting. |
| [script-policy.md](agents/script-policy.md) | POSIX vs PowerShell script policy and `.plate` `platform`. |
| [upstream-template-sync.md](agents/upstream-template-sync.md) | `import-payload`, `self-migrate`, and PLATES-CORE marker sync. |
| [wiki-sync.md](agents/wiki-sync.md) | Opt-in wiki sync rules. |
| [template-integrity-rules.md](agents/template-integrity-rules.md) | copilot-instructions, CI placeholder guards, and local temp paths. |
| [real-world-tasks.md](agents/real-world-tasks.md) | Epic planning with human-only external Tasks (plate-core reference). |
| [branch-model-and-ceremonies.md](agents/branch-model-and-ceremonies.md) | Release branches and ceremonies (plate-core reference). |
| [pr-feedback-and-babysit.md](agents/pr-feedback-and-babysit.md) | Full PR-green babysit loop (plate-core reference). |

## Authority Model

The PLATE book explains doctrine and the reasons behind the method. This repository is the source of truth for the **installable template artifacts** because those files must evolve faster than a long-form book can safely absorb. When a repository artifact and book prose disagree, do not preserve both versions indefinitely. Open a corrective issue or pull request that reconciles the doctrine, the template artifact, and any migration note required for existing users.

| Area | Agent May Do | Human Must Decide |
|---|---|---|
| Product intent | Draft proposals, clarify ambiguities, identify conflicts, and map work to issues. | Final scope, priority, product tradeoffs, public commitments, and roadmap direction. |
| Implementation | Modify code, tests, docs, and configuration inside an approved task. | Acceptance of risk, merge approval, release approval, and irreversible operational changes. |
| Process | Follow PLATE rules, detect drift, and suggest process improvements. | Changing required gates, weakening checks, changing merge policy, or adopting new required automation. |
| Documentation | Update per-feature change files in `.agentic/releases/`, wiki source pages, release notes, audit notes, and traceability records. | Approving claims that affect customers, pricing, legal posture, security posture, or roadmap promises. |

## Required Work Loop

Follow the loop that matches the issue type.

**Feature**

| Step | Required Behavior |
|---|---|
| 1 | Confirm the issue is labeled `Feature` and assigned to the GitHub milestone representing its Epic. |
| 2 | Identify acceptance criteria, expected tests, documentation impact, and risk. |
| 3 | Add or update tests before or alongside implementation. |
| 4 | Implement the smallest coherent change that satisfies the issue. |
| 5 | Update per-feature change files in `.agentic/releases/` to describe the implemented behavior and verification evidence. |
| 6 | If the feature includes UI changes, record a demo GIF (see [e2e-and-demo-gifs.md](agents/e2e-and-demo-gifs.md)). |
| 7 | Determine the correct base branch using `gh plate release status` (legacy `release` for single-release repos; matching `release-*` track otherwise). Open a PR labeled `Feature` **targeting that base** (include `--base release` etc. in `gh pr create`) with `Closes #N` in the body. Complete the PR template. When using GitHub CLI, apply the type label in the `gh pr create` command itself rather than relying on a later edit step. |
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
| 2 | **Present the question using host-native look-and-feel** (Copilot CLI native TUI, Grok Build `ask_user_question` arrow-key forms, or equivalent). Fall back to `gh plate qanda` CLI / plain text only when native UI is unavailable. Do not wait for the user to say "use native UI." |
| 3 | Commit the answer artifact (for example `docs/research/<slug>.md`) and any resulting process updates. |
| 4 | When the answer changes operating guidance, update `AGENTS.md` and `.agentic/skills.yml` in the same PR. |
| 5 | Open a Documentation PR with `Closes #N` in the body. |

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
| 1 | Confirm a standing `Next Release` issue exists with linked epics and a completed pre-release checklist. |
| 2 | Use `gh plate release status` to confirm the expected fragments, targeted epics, and release-track state. |
| 3 | During packaging, lock the semver, create the versioned `release-vX.Y.Z` branch, and rename or replace the standing issue with the concrete release issue. |
| 4 | Run `gh plate release cut vX.Y.Z` (or the equivalent script) to aggregate fragments into `.agentic/releases/vX.Y.Z/`. |
| 5 | Open a Release PR from the versioned release branch to `main`, run the heavy release validation path, and include `Closes #N` in the PR body. |
| 6 | After human approval and merge, the release workflow tags the merged Release PR commit. Then publish the GitHub Release and create a fresh standing `Next Release` issue for subsequent work. |

## Issue Artifact Rules

Every issue must close with a traceable artifact. For most issue types this is a code change in a PR or a documentation commit. `Task` issues instead close with a completion comment containing `<!-- PLATE-TASK-CLOSED -->`, unless repository truth also changed and needs a PR-backed artifact.

| Issue Type | Required Git Artifact | Typical PR Type Label |
|---|---|---|
| `Feature` | Code change + per-feature change files in `.agentic/releases/` update | `Feature` |
| `Bug` | Bug fix + regression test | `Bug` |
| `Research` | Findings committed to `docs/research/<slug>.md` or `SPEC.md` update | `Documentation` |
| `Design` | Artifact committed to `docs/design/<slug>.md` or `docs/wiki/Features/<feature>.md` | `Documentation` |
| `Question` | Answer artifact committed to `docs/research/<slug>.md` and process updates when guidance changes (`AGENTS.md`, `.agentic/skills.yml`) | `Documentation` |
| `Task` | Completion comment on the GitHub issue containing `<!-- PLATE-TASK-CLOSED -->`; add a PR or documentation artifact only when repository truth changes | `Documentation` when follow-up docs are needed, otherwise none |
| `Audit` | Report committed to `docs/audits/<slug>.md` | `Documentation` |
| `Migration` | Update committed to `docs/migration/` | `Documentation` |
| `Epic` | Wiki summary in `docs/wiki/` or epic comment summarizing child outcomes | `Documentation` |
| `Release` | Aggregated `.agentic/releases/vX.Y.Z/` directory + tag + GitHub Release | `Documentation` |

When GitHub's native closing keyword (`Closes #N`, `Fixes #N`, `Resolves #N`) is present in the PR body and the PR merges to the default branch, GitHub automatically closes the linked issue. Use a closing keyword when the PR should close the issue on merge, and use the Development sidebar when the issue should remain open after the PR lands. `Feedback Response` PRs remain exempt from the issue-link gate. `Task` issues are exempt when they close via the Task completion comment instead.

## Merge and feedback gates

- Require the `pr-gates` check from `.github/workflows/plate-pr-gates.yml` on protected branches so merge waits until agent feedback threads are resolved where applicable.
- Full third-party feedback steps, pre-merge recheck, and human escalation: [third-party-agent-feedback.md](agents/third-party-agent-feedback.md).

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

Use labels as stable process metadata. Do not create ad hoc labels unless they change routing, enforcement, reporting, auditing, review burden, or agent behavior. Use GitHub Projects fields for frequently changing planning state such as priority, owner, rank, iteration, target date, or release target. The `status:blocked` and `status:ready-to-work` labels are the explicit exception used by PLATES native trigger workflows.

| Label Family | Usage |
|---|---|
| `Bug`, `Feature`, `Epic`, `Release`, `Research`, `Design`, `Question`, `Task`, `Audit`, `Migration`, `Feedback Response` | Exactly one required issue type label. |
| `Bug`, `Feature`, `Documentation`, `Feedback Response` | Exactly one required pull request type label. |
| `Feedback Response` | Combined issue + PR type for feedback-response process work when needed. Not auto-created by `plates-address-pr-feedback.yml` in the inline response flow. No Epic milestone required. |
| `Epic: short-name` | Legacy or supplemental Epic identity label. GitHub milestones are the canonical Epic container for Feature, Epic, and Release issues. |
| `area:*` | Stable subsystem or ownership area. |
| `risk:*` | Review burden and release caution. |
| `need:*` | Missing input or required follow-up. |

## Escalation Rules

Escalate to a human when product intent is ambiguous, acceptance criteria conflict, a required label is missing and cannot be inferred, a workflow would need to be weakened, a secret or permission is required, a public claim might change, or the agent cannot produce the required evidence.

## Prohibited Actions

Agents must not merge their own pull requests **unless autonomous mode is active and the PR meets all eligibility criteria in [autonomous-mode.md](agents/autonomous-mode.md)**. Agents must not bypass required checks, remove documentation gates, weaken tests to pass CI, fabricate test results, silently rewrite product intent, expose secrets, enable write automation without approval, create or delete `.github/AUTONOMOUS_MODE` themselves, or treat chat history as more authoritative than repository artifacts. Agents must not clone, fork, or `gh repo create --template` from `akasper/plate_template` (or any template repo), and must not hand-copy PLATE payload files—use `gh plate bootstrap` and `gh plate import-payload` only. Agents must not close an issue without the required closure artifact: for most issue types, a corresponding PR that carries a `Closes #N` reference in its body; for `Task` issues, a completion comment containing `<!-- PLATE-TASK-CLOSED -->`; `Feedback Response` PRs remain exempt from the issue-link rule. Agents must not open a PR that resolves a specific issue without including `Closes #N`, `Fixes #N`, or `Resolves #N` in the PR body, except for `Feedback Response` PRs.
