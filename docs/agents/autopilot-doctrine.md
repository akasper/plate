# Autopilot Doctrine

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Autopilot Doctrine

PLATE defaults to an **autopilot posture**: agents should proceed autonomously through a task queue and pause only at defined human checkpoints, rather than asking permission at each step. This posture is only safe when work is structured so that any step can be cheaply reviewed and reversed.

**Atomic PR discipline.** Structure every session as a sequence of small, independently revertable PRs. A PR should have a single clear purpose. Soft limit: ≤ 10 changed files for implementation work. Prefer many small PRs over one large one. If a branch grows beyond the soft limit, split it before opening the PR.

**Easy revert as the norm.** Prefer squash merges on integration branches (`release-*`, `epic/*`). Never push directly to `main`. **Exception:** Release PRs into `main` must use a merge commit or fast-forward, not squash/rebase, so post-tag release-branch fast-forward works (#1455). Name branches `type/short-description`.

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
