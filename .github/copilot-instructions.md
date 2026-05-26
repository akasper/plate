# Copilot Instructions

## Build, test, and lint

This template does not define a local build, lint, or test toolchain yet. `tests\README.md` is a placeholder, and `.github\workflows\ci.yml` currently contains a scaffold step that only echoes `"Tests would run here"`.

When a downstream project adds a runtime or package manager, prefer the real project commands over inventing new ones, and update this file with:

- the full test command
- the single-test command for that stack
- any build and lint commands that CI actually uses

## High-level architecture

This repository is a **PLATE template**, not an application codebase. The important architecture is the process wiring between durable project artifacts, machine-readable rules, and GitHub enforcement:

- `SPEC.md` defines the intended goal state.
- `CURRENT.md` records the implemented state and verification evidence.
- `AGENTS.md` defines local agent operating rules and escalation boundaries.
- `.agentic\process.yml` mirrors the same process in machine-readable form for automation and audits.
- `.github\labels.yml`, `.github\ISSUE_TEMPLATE\`, and `.github\PULL_REQUEST_TEMPLATE.md` define the work intake and review metadata.
- `.github\workflows\label-check.yml` enforces required issue and PR type labels.
- `.github\workflows\pr-documentation-check.yml` enforces that `Feature` PRs update `CURRENT.md`.
- `.github\workflows\pr-issue-link-check.yml` warns (and fails for `Feature`/`Bug` PRs) if the PR body contains no closing keyword (`Closes #N`).
- `.github\workflows\question-handling.yml` supports the `/question-batch` issue-comment slash command for triaging open Question issues.
- `.github\workflows\auto-merge.yml` enables autonomous PR merging when `.github/AUTONOMOUS_MODE` is present and the PR carries the `auto-merge` label.
- `.github\workflows\plates-address-pr-feedback.yml` monitors `pull_request_review` and `pull_request_review_comment` events. When a known third-party agent (Devin, OpenHands, etc.) leaves feedback on a PR, it creates a `[PLATES]` issue and assigns it to `copilot` via the Issues API — no PAT required, fully `GITHUB_TOKEN`-native. The Copilot Coding Agent picks up the issue and should apply suggestions, push fixes to the existing PR branch, resolve threads, and close the issue. Configure the agent list via the `PLATE_PR_FEEDBACK_AGENTS` repository variable (comma-separated logins); the workflow falls back to built-in pattern matching when the variable is absent.
- `.github\workflows\sync-wiki-on-merge.yml` runs only for merged `Feature` PRs on `main`, then copies scoped documentation sources into the GitHub wiki.
- `.github\agents\` contains custom Copilot agent definitions (`.agent.md` files) that appear in the agent picker for all collaborators. See `docs\research\custom-agent-packaging.md` for the packaging pattern.
- `docs\research\` stores committed artifacts for closed Research issues (see `docs\research\README.md`).
- `docs\design\` stores committed artifacts for closed Design issues (see `docs\design\README.md`).

Read those pieces together when making process changes. A change in one of them usually implies matching updates in the others.

## Key conventions

- Treat repository artifacts as the source of durable truth. If behavior, process, or evidence changes, update the relevant artifact instead of relying on chat history.
- If `AGENTS.md`, `.agentic\process.yml`, and the template files disagree, preserve the PLATE intent and keep them aligned.
- Labels are stable process metadata, not casual tags. Use type labels (`Bug`, `Feature`, `Epic`, `Documentation`, `Research`, `Design`, `Question`, `Audit`, `Migration`) and prefixed labels (`Epic:`, `area:`, `risk:`, `need:`) according to the existing taxonomy. Do not introduce `priority:` or `status:` labels; those belong in GitHub Projects fields.
- `Feature` issues must carry both the `Feature` label and a matching `Epic: short-name` label. Their issue template expects acceptance criteria, test expectations, and documentation impact.
- `Bug` work should include a reproduction path or explicitly signal the gap with `need:reproduction`, plus a regression test plan.
- `Research` issues must close with a committed artifact in `docs/research/` or a `SPEC.md` update — not just an issue comment. See `docs/research/README.md`.
- `Design` issues must close with a committed artifact in `docs/design/` or `docs/wiki/Features/`. See `docs/design/README.md`.
- `Question` issues are information goals. Batch triage with `/question-batch` or `scripts/question_batch.sh`, and when an answer changes agent guidance, update both `AGENTS.md` and `.agentic/skills.yml` in the closing PR.
- Every PR must carry a type label (`Bug`, `Feature`, or `Documentation`). **Critical:** The checkboxes in the PR template body do **not** apply GitHub labels — labels must be set explicitly via the CLI or GitHub API. Preferred approach: include `--label "<type>"` in `gh pr create` so the label is applied atomically at PR creation. If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before doing anything else. `Feature` PRs must update `CURRENT.md`; documentation-only changes should use the `Documentation` label.
- When a PR is opened without a type label, the `label-check.yml` CI workflow fails immediately **and posts a repair comment on the PR** with the exact `gh pr edit` command to fix it. Look for the ⚠️ bot comment on the PR — it contains the precise repair command for that PR number.
- **Every PR that resolves a specific issue must include `Closes #N` (or `Fixes #N` / `Resolves #N`) in the PR body.** GitHub will then automatically close the linked issue on merge. The `pr-issue-link-check.yml` workflow warns (and fails for `Feature`/`Bug` PRs) if the closing keyword is absent.
- PRs that do not resolve a tracked issue (chores, dependency bumps) should be labeled `no-issue` to silence the closing-keyword check.
- **Autopilot doctrine:** Prefer many small PRs (≤ 10 files each) over one large PR. Each PR should have a single clear purpose and be independently revertable. Prefer squash merges. Post an epic summary comment when all child issues are resolved, then pause for human review before starting the next epic.
- **Autonomous mode** is enabled when `.github/AUTONOMOUS_MODE` exists on the default branch. When active, agents may label eligible `risk:low` PRs `auto-merge` and call `gh pr merge --auto --squash` after `gh pr create`. Full eligibility rules in `AGENTS.md §Autonomous Mode`. Never use `auto-merge` on PRs touching `AGENTS.md`, `SPEC.md`, workflows, credentials, auth, payments, or public claims. Agents may never create or delete the `AUTONOMOUS_MODE` marker file themselves.
- `.github\workflows\auto-merge.yml` enforces the marker file check as a second gate.
- Prefer small, scoped documentation and wiki updates. The wiki sync workflow is intentionally conservative and currently treats `CURRENT.md`, `docs\wiki`, and `docs\features` as the sync inputs.
- For newly generated repositories, start with `docs/bootstrap/new-repository-checklist.md` and run `scripts/bootstrap_github.sh` (macOS/Linux/WSL) or `scripts\BootstrapGitHub.ps1` (Windows) before making project-specific changes.
- Do not weaken tests, documentation gates, or workflow checks to make a change pass. Human review and merge authority remain outside agent authority except as defined in `AGENTS.md §Autonomous Mode`.
- **Before opening any Feature issue that depends on an external API**, verify that `SPEC.md §External Integrations` contains an entry for that API and confirm it is reachable. If API availability is uncertain, open a Research issue first.
