# Documentation Rules

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Documentation Rules

Every Feature pull request that changes PLATE process, templates, or agent surfaces must author a fragment under `.agentic/releases/unreleased/<slug>.json`. Documentation pull requests must commit a file to the appropriate `docs/` subdirectory and should explain whether they update process artifacts, product documentation, wiki source material, or public-facing claims. Changes that alter PLATE behavior or process should also add or update a fragment. If a change affects feature behavior, update both implementation evidence and documentation evidence.

**Fragment-first authoring:** The canonical documentation path for PLATE changes is `.agentic/releases/unreleased/<slug>.json`. These fragments accumulate across the Epic and are aggregated at release-cut time into `.agentic/releases/vX.Y.Z/`.

See §Issue Artifact Rules for the full mapping of issue type to required artifact location.

When opening pull requests through GitHub CLI, first run `gh plate release status` to discover the correct integration base branch (`release` for legacy; the matching `release-*` track otherwise). Prefer an atomic command such as `gh pr create --base <base> --label "Feature"` (or the Documentation equivalent, where <base> is from `gh plate release status`). If the PR is already open (e.g., created via the GitHub web UI or REST API), run `gh pr edit <number> --add-label "Feature"` as the very next step before any other work. Never rely on the repository's default branch implicitly; always pass `--base` explicitly (sometimes that will be `main`, e.g. for Release PRs).

**Important:** The checkboxes in the PR template body do **not** apply GitHub labels. Labels must be set explicitly via the CLI or GitHub API.

For **every new pull request**, add exactly one required PR type label (`Bug`, `Feature`, `Documentation`, or `Feedback Response`) at creation time. Unlabeled or multiply-labeled PRs fail CI immediately, and a repair comment will be posted on the PR with the exact `gh pr edit` command to fix it.

For `Feature`, `Bug`, and issue-driven `Documentation` PRs, add the relevant milestone as well. Current rollout is warning-first: the PR issue-link workflow warns when the milestone is missing rather than failing immediately.
