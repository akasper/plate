# Pr Feedback And Babysit

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

Preferred flow is now **local babysitting** driven by `gh plate pr babysit <number>`. CI is intentionally narrowed to enforcement-only (`feedback-resolution` check). The `plate` agent persona (plugin/agents/plate.agent.md and mirror) no longer includes babysitting steps (deprecated in favor of the dedicated local CLI/MCP flow; see PR #120 and this PR's Q&A/Curiosity updates). For review-thread reply + resolve discipline, follow the **`address-pr-feedback` skill** (`.agentic/skills/address-pr-feedback/SKILL.md` after bootstrap; `plugin/skills/address-pr-feedback/SKILL.md` in the plate-core plugin tree).

Use this loop:

1. Before babysitting (or any PR-related work), run `gh plate release status` *proactively first* to confirm the track/base and pending fragments. Then start or join babysitting locally (`gh plate pr babysit <number> [--act] [--watch] [--branch-update-strategy <strategy>]`) using MCP tools `plate_pr_babysit` + `plate_resolve_review_thread`, and the **`address-pr-feedback` skill** for the per-thread reply/resolve loop (the `/agent plate` persona focuses on health/epic/features/delegation + native Q&A/curiosity per recent guidance). (Addresses #513.)

**Quiet Agents note:** For looped or long-running babysitting/monitoring, the supervising agent must follow the quiet_operations rules (see `plugin/agents/plate.agent.md` Behavior rules + Special modes, and `src/plate_core/agent_guidance.py` QUIET_OPERATIONS_GUIDANCE): only terse bullet-list one-sentence turn summaries in the terminal; post GitHub comments on the PR only for meaningful forward progress (not "checked, 0 actionable" no-ops). The persona and catalog constraints are the primary enforcement surface. Information Audits (#218) are now part of the core capability: agents should use `plate_perform_information_audit` (dry_run first) to discover gaps against the Goals page (#224) and generate Questions. Guidance in plugin/agents/plate.agent.md and agent_guidance.py (INFORMATION_AUDIT_GUIDANCE, plus the new quiet section). Catalog defaults (#222) and extensibility (#226) apply.
2. The babysitter automatically detects two types of issues:
   - **Unresolved review threads** from third-party agents (actionable feedback)
   - **Base branch out-of-sync** state (PR branch behind, conflicting, or dirty relative to base branch)
3. When the high-level goal is "get this PR green", "make mergeable", "address all feedback", or equivalent, treat it as an iterative loop the *agent owns* (the "Full PR Green / Make Mergeable Loop" — see quiet_operations guidance in agent_guidance.py and the pr-babysit skill). **Always start with "CI diagnosis first" (addresses #527):** before *any* broad/expensive local command (e.g. full pytest in worktree), do cheap GitHub inspection first:
   - `gh pr checks <N>` (or `gh plate pr babysit` / MCP) for current gates.
   - `gh run list --branch <head> --limit 5` + `gh run view <run-id> --job <job-id> --log-failed` (or --log) on the *specific* failing job to get the exact current error (e.g. labels? unresolved threads? specific test?). Note: `--log-failed` returns only the failing step output (much smaller/cheaper than full `--log`).
   - Only then decide minimal local scope (targeted -k, single file, or just metadata fix). Use/document one-liners for the gh run view flags.
   - For backgrounded/long-running tasks started during babysit (e.g. pytest): immediately record task_id and proactively schedule/polling with `get_command_or_subagent_output` or `monitor` at intervals (30s/2m/5m/10m); at each poll emit terse one-bullet status to user (e.g. 'still running after 2m, last output: ...'); surface partial output/status in terse responses. Do not wait for system reminders. Consider a lightweight "monitor" helper. (Addresses #525.)
   - For verification / local test runs in worktree: follow verification strategy — use check-work skill or targeted commands first (not full suites); warn before long runs (>5-10min). (Addresses #523.)
   - Comprehensively inspect *all* current failing gates at the start and after every push using the pr-babysit skill's get_pr_merge_gates helper (or equivalent) + gh commands. Common checklist (mental model for "make this PR mergeable"):
     - Labels (Bug/Feature + area:* + risk:* + Epic:* if applicable; check with gh issue view or edit)
     - Merge state / base sync (mergeStateStatus: BLOCKED, BEHIND, CONFLICTING, DIRTY, UNKNOWN -> use babysit with local-rebase or copilot-request)
     - Feedback-resolution: unresolved review threads (esp. third-party agents) -> follow the **`address-pr-feedback` skill**; use `plate_get_unresolved_review_threads` for fetch/done gate, `plate_get_actionable_review_threads` for scoped actionable work, and `plate_resolve_review_thread` per thread (encapsulated; addresses #516/#1155). Do not hand-roll GraphQL/jq/mktemp/sed except the exact documented fallback in the skill file above.
     - CI / test jobs, title check, issue-link check, feature-change-files (if Feature), audit, deploy, etc. (via gh pr checks)
     - **Pre-merge recheck (#1234)** — immediately before merge or auto-merge, fetch the PR again; do not merge when BEHIND, DIRTY, or CONFLICTING; if base commits landed after the last green run and touch this PR's files, sync the branch, push, and wait for green again; never use `--admin` or other bypass flags (especially on permissive bases like `release`).
     - **Review-loop scope (#1234)** — fix real bugs in the intended case; decline extra tests, rare edges, minor perf, or broad compat asks with an in-thread reason, resolve, and list follow-ups; prefer fixes that delete or narrow code (see **`address-pr-feedback` skill**).
     - Other: documentation gate, etc.
     Use plate_pr_babysit + gh pr checks + gh run view on specific failing jobs (see CI Diagnosis First) + gh issue view for labels. Fix what you can, push, re-inspect, repeat until only human items (e.g. owner CHANGES_REQUESTED, high-risk) remain. Report one-sentence summary only then. (Addresses #526.)
   - From a *single high-level prompt* ("get this PR green", "make mergeable", "address all feedback"), the agent should handle *all* agent-actionable categories (base sync/conflicts, labels, review threads, tests, etc.) in one or minimal comprehensive passes using the pr-babysit skill + get_pr_merge_gates + resolveReviewThread, without requiring category-by-category diagnosis or prompting from the user. Do not fix one category then wait for the user to diagnose the next. (Addresses #519, #528, #526.)
   - Address everything the agent can autonomously in the worktree (rebase/resolve conflicts per strategy, apply safe suggestions, fix labels/metadata within scope, resolve addressed threads via `plate_resolve_review_thread`, fix locally reproducible test failures preferring cheap targeted runs, etc.). **Verify isolation (git rev-parse --show-toplevel or pr-babysit verify_worktree_is_isolated) and cleanup locks (cleanup_git_locks or rm -f .git/index.lock) before every git op in worktree. (Addresses #514.)**
   - Push all changes to the *existing* PR branch (never open a new PR for feedback response).
   - Re-inspect all gates (always re-starting with CI diagnosis).
   - Repeat until no more agent-actionable items remain (only human judgment items like actual owner CHANGES_REQUESTED, credentials, high-risk decisions, or security changes are left).
   - Only then report the one-sentence summary of what is left for the human + current state. Use quiet terse bullets for the loop.
4. Review all open inline comments and the overall review body from the named reviewer on the linked PR
5. For any comment that includes a GitHub code suggestion (` ```suggestion ` block): apply it directly as a commit **unless** the suggestion introduces a bug or relies on a false assumption — if you skip a suggestion, reply to that thread with a brief explanation
6. For all other actionable comments: push a code change or reply explaining why no change is needed
7. After addressing each comment (via code change, applied suggestion, or explanatory reply), follow step 3–4 of the **`address-pr-feedback` skill**: reply in-thread (commit SHA or reason), then resolve that thread via `plate_resolve_review_thread` (MCP) / `resolve_review_thread` (Python) / the skill's `resolveReviewThread` mutation — **one thread at a time, only after its reply**. Do not use `gh plate pr babysit --act` as a per-thread resolver (`--act` bulk-closes outdated threads without checking replies; #605 is separate from the reply loop). **"Address feedback" is done only when `plate_get_unresolved_review_threads` (or the skill GraphQL fallback) returns zero unresolved threads** (except threads escalated with `need:human-review` and an in-thread comment).
8. **PR review scope (#496):** Default is `all` (humans + bots, including Copilot). Configure via `.plate` `autonomy.pr_review_scope` (`all` | `bot-only` | `human-only`) or `gh plate pr babysit --scope …`. Prefer applying fenced ` ```suggestion` ` blocks when `prefer_apply_suggestion` is true; never auto-apply on high-risk paths (AGENTS.md, workflows, SPEC, secrets, `.plate`). Do **not** re-request Copilot review in a loop — work existing unresolved threads first.
   (Prefer encapsulated helpers; see `get_unresolved_review_threads` / `plate_get_unresolved_review_threads` for the done gate. When helpers are unavailable, use only the exact `gh api graphql` fallback in the address-pr-feedback skill — not ad-hoc jq/mktemp/sed. Addresses #516, #1155.)
8. **Push all changes to the existing PR branch** — do not open a new issue or a new PR for the feedback response
9. For items requiring human judgment (credentials, architectural decisions, security changes), add `need:human-review` to the PR and leave a comment identifying what is blocked

The **`address-pr-feedback` skill** (reply + resolve + zero-unresolved re-query gate) and `gh plate pr babysit` should be used by default for these flows and ideally support a " --until-green" / comprehensive make-mergeable mode that implements the loop above with appropriate quiet output and escalation. See the updated skill docstring and guidance for details (addresses #528, #1155, and the cluster of related PR-green / gates Bugs).

<!-- PLATES-CORE:BEGIN pre-merge-recheck-review-scope-1234 -->
**Pre-merge recheck (#1234).** Treat "green a moment ago" as stale the instant you merge. Immediately before any merge or `gh pr merge --auto`, fetch fresh PR state (`gh pr view`, `plate_get_pr_merge_gates`, or `gh plate pr babysit`). Do **not** merge when `mergeStateStatus` is BEHIND, DIRTY, or CONFLICTING. If the base branch gained commits after the last green CI run and those commits touch files this PR changes, update the branch (rebase or merge per babysit strategy), push, and wait for checks to pass again. Never use `gh pr merge --admin` or other flags that bypass branch protection or required checks. This matters most on permissive integration branches such as `release`. (Ideas adapted from [tstack](https://github.com/t3dotgg/tstack), MIT, Theo Browne; see #1232/#1234.)

**Keep review loops small (#1234).** During the PR-green and feedback loops, fix review comments that identify real bugs in the intended use case. Decline the rest—extra tests outside the change, rare edge cases, small speedups, or broad compatibility requests not required for this PR—with a written in-thread reason, then resolve the thread and list each declined item as a follow-up (issue stub or PR comment backlog). When several fixes are possible, prefer the one that deletes or narrows code instead of adding layers. (Same tstack credit as above.)
<!-- PLATES-CORE:END pre-merge-recheck-review-scope-1234 -->

<!-- PLATES-CORE:BEGIN modernize-pr-skill-1235 -->
**Modernize stale PRs (#1235).** For old pull requests, follow the **`modernize-pr` skill** (`plugin/skills/modernize-pr/SKILL.md`; `.agentic/skills/modernize-pr/SKILL.md` after bootstrap). Decide first (one verdict: **MODERNIZE**, **REWORK**, or **CLOSE** with evidence); a successful rebase does not by itself justify keeping the PR. The skill **never closes and never merges** on its own — **CLOSE** is only a recommendation requiring owner approval. It never retargets the base or widens scope, uses an isolated worktree for git work, and does not treat trigger phrases as overrides for merge/close gates. After **MODERNIZE**, compare pre- and post-rebase commits with `git range-diff` and push with `--force-with-lease` pinned to the pre-rebase head SHA. (Ideas adapted from [tstack](https://github.com/t3dotgg/tstack) `modernize`, MIT, Theo Browne; see #1232/#1235.)
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

**Base Branch Sync Handling:**

The babysitter detects when a PR branch is out of sync with its base branch (via `mergeStateStatus`: BEHIND, CONFLICTING, or DIRTY). The default behavior is controlled by `--branch-update-strategy`:

- **local-rebase** (default): Local worktree rebase and push (implemented using isolated git worktree via pr-babysit helpers; reports success/conflict/error via BabysitReport fields; raises only on non-git env or fatal error). **Before any worktree/rebase/push: call cleanup_git_locks() + verify_worktree_is_isolated() (or raw `git rev-parse --show-toplevel` + rm -f .git/index.lock). Use isolated worktree for *all* PR changes during babysit/fixes (never main checkout). Cleanup: git worktree remove --force + rm -rf the temp dir. Subagent and main agent must not collide on same repo dir. (Addresses #514.)**
- **copilot-request** (opt-in): Post a `@copilot` trigger comment requesting native GitHub/Copilot branch update assistance. Use only when a human explicitly wants paid Copilot merge assistance.
- **none**: Detect and report only, take no action

When `--act` is specified and the PR is out of sync, the babysitter resolves base drift with the chosen strategy (local rebase by default, or a Copilot merge trigger when `copilot-request` is set). This keeps the babysitting loop moving without silent `@copilot` spend.

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

**Merge safety gate:** Require `.github/workflows/feedback-resolution-check.yml` (`feedback-resolution`) in branch protection for `main` (and integration branches) so merge/auto-merge waits until all active *agent* (third-party) review threads are resolved. The gate now author-filters to PLATE_PR_FEEDBACK_AGENTS + default patterns (devin, openhands, etc.); human review comments do not block unless CHANGES_REQUESTED or explicit need:human-review. This gate is *not* a substitute for the separate human review/approval requirement for Bug/Feature/Hardening/Documentation PRs (see above and authority table). Human approval (Approved review or explicit human merge) is required in addition. (Addresses #569 gate filter.)
