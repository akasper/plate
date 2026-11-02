# Third Party Agent Feedback

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Third-Party Agent Feedback

Preferred feedback handling is local **`gh plate pr babysit`** / MCP (`plate_pr_babysit`, `plate_resolve_review_thread`) and the **`address-pr-feedback` skill** (`.agentic/skills/address-pr-feedback/SKILL.md`). The shipped `.github/workflows/plates-address-pr-feedback.yml` is **legacy manual-only** (`workflow_dispatch`); do not rely on it for normal operations. When run manually it uses `COPILOT_TRIGGER_PAT` (preferred) with fallback to `GITHUB_TOKEN`, applies a dedupe marker, and avoids creating a new issue or separate PR. `Feedback Response` PRs are skipped. The Copilot Coding Agent should follow the skill when addressing feedback:

1. Review all open inline comments and the overall review body from the named reviewer on the linked PR
2. For any comment that includes a GitHub code suggestion (` ```suggestion ` block): apply it directly as a commit **unless** the suggestion introduces a bug or relies on a false assumption — if you skip a suggestion, reply to that thread with a brief explanation
3. For all other actionable comments: push a code change or reply explaining why no change is needed
4. After addressing each comment (via code change, applied suggestion, or explanatory reply), **reply in-thread** (commit SHA or reason), then resolve that thread with `plate_resolve_review_thread` (or the skill's `resolveReviewThread` mutation) **only after its reply** — not via `gh plate pr babysit --act` (bulk outdated auto-resolve). When plate helpers are unavailable, use only the exact `gh api graphql` fallback in `.agentic/skills/address-pr-feedback/SKILL.md` (`reviewThreads` with `isResolved: false` including outdated, pagination, `addPullRequestReviewThreadReply`, `resolveReviewThread`). **"Address feedback" is done only when the skill's re-query returns zero unresolved threads** (except threads escalated with `need:human-review` and an in-thread comment).
5. **Push all changes to the existing PR branch** — do not open a new issue or a new PR for the feedback response
6. For items requiring human judgment (credentials, architectural decisions, security changes), add `need:human-review` to the PR and leave a comment identifying what is blocked
<!-- PLATES-CORE:BEGIN pre-merge-recheck-review-scope-1234 -->
7. **Keep review loops small (#1234)** — fix real bugs in the intended case; decline extra tests, rare edges, minor perf, or broad compat asks with an in-thread reason, resolve, and list follow-ups; prefer fixes that delete or narrow code (full detail in the **`address-pr-feedback` skill**)

**Pre-merge recheck (#1234).** Before merging, fetch the PR again. Do not merge when it is BEHIND, DIRTY, or CONFLICTING. If base commits landed after the last green run and touch this PR's files, sync the branch, push, and wait for green again. Never use merge bypass flags such as `--admin`. Especially important on integration branches like `release`. (Ideas adapted from [tstack](https://github.com/t3dotgg/tstack), MIT, Theo Browne; see #1232/#1234.)
<!-- PLATES-CORE:END pre-merge-recheck-review-scope-1234 -->

<!-- PLATES-CORE:BEGIN modernize-pr-skill-1235 -->
**Modernize stale PRs (#1235).** For old pull requests, follow the **`modernize-pr` skill** (`.agentic/skills/modernize-pr/SKILL.md` after bootstrap). Decide first (one verdict: **MODERNIZE**, **REWORK**, or **CLOSE** with evidence); a successful rebase does not by itself justify keeping the PR. The skill **never closes and never merges** on its own — **CLOSE** is only a recommendation requiring owner approval. It never retargets the base or widens scope, uses an isolated worktree for git work, and does not treat trigger phrases as overrides for merge/close gates. After **MODERNIZE**, compare pre- and post-rebase commits with `git range-diff` and push with `--force-with-lease` pinned to the pre-rebase head SHA. (Ideas adapted from [tstack](https://github.com/t3dotgg/tstack) `modernize`, MIT, Theo Browne; see #1232/#1235.)
<!-- PLATES-CORE:END modernize-pr-skill-1235 -->

<!-- PLATES-CORE:BEGIN pr-handoff-comment-attribution-1236 -->
**Credit when finishing someone else's PR (#1236).** When an agent continues work another agent or a human started, stay on the **same PR and branch**. Preserve existing commit authorship; add follow-up commits without rewriting prior authors. Use `Co-authored-by` only with **verified** GitHub identities (from `gh api user`, known owner noreply addresses, or other confirmed metadata)—never guessed emails. On squash merge, retain legitimate human co-author credit in the squash message when appropriate. Link the PR being continued in the first handoff comment. (Ideas adapted from [tstack](https://github.com/t3dotgg/tstack) `takeover`, MIT, Theo Browne; see #1232/#1236.)

**Agent comment attribution (#1236).** Comments an agent posts under a person's account should **name the agent** (on by default). Add one short first line, for example `🤖 Grok Bot on behalf of Andrew`. Configure in `.plate` under `autonomy.comment_attribution`: `enabled` (boolean, default `true`) and `format` (string with `{agent}` and `{on_behalf_of}` placeholders; default `🤖 {agent} on behalf of {on_behalf_of}`). Use the real harness or agent name from the session, not an inferred model label. Applies to PR comments, review replies, and decline reasons—not PR descriptions or commit messages. PLATE code: `plate_core.comment_attribution.apply_comment_attribution`. (Ideas adapted from tstack `leaving-pr-comments`, MIT, Theo Browne; see #1232/#1236.)
<!-- PLATES-CORE:END pr-handoff-comment-attribution-1236 -->

<!-- PLATES-CORE:BEGIN import-payload-conservative-taxonomy-1250 -->
**Conservative import-payload (#1250).** With `--strategy conservative`, differing existing payload paths are **conflicts** and are never written — including `.github/labels.yml`, `.github/ISSUE_TEMPLATE/*`, and `.github/PULL_REQUEST_TEMPLATE.md`. Identical files remain unchanged. Manifest `on_conflict: overwrite` applies only to `--strategy safe` (refresh taxonomy/templates on adopt) and `--strategy force`; do not expect conservative mode to refresh those files.
<!-- PLATES-CORE:END import-payload-conservative-taxonomy-1250 -->

<!-- PLATES-CORE:BEGIN pre-push-hook-template-1281 -->
**Pre-push hook (#1281).** For checks that must run before every push (format, lint, typecheck on changed files), prefer `gh plate hooks install` plus `hooks.pre_push` commands in `.plate` over prose rules agents can skip. The hook passes silently when no commands are configured. See `docs/bootstrap/pre-push-hook.md`.
<!-- PLATES-CORE:END pre-push-hook-template-1281 -->

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

**Merge safety gate:** Require the `pr-gates` check from `.github/workflows/plate-pr-gates.yml` in branch protection for `main` so merge and auto-merge wait until agent feedback threads are resolved (this workflow supersedes the older standalone feedback-resolution workflow, which the payload no longer ships).
