# PR visual evidence attach (`gh plate evidence`)

Part of the PLATE agent operating rules. Parent epic: Pretty PRs (#1048). See also [github-actions-and-copilot.md](github-actions-and-copilot.md) and AGENTS.md UI screenshot rules (#1050).

## Purpose

`gh plate evidence` wraps `gh pr edit <N> --body-file … --attach …` so agents upload PR screenshots in one step: it checks **gh ≥ 2.99**, prepares markdown image references with **non-empty alt text**, runs `--attach`, and confirms the PR body contains `https://github.com/user-attachments/assets/` links.

## CLI

```bash
gh plate evidence <PR_NUMBER> --body-file ./body.md ./desktop-after.png ./mobile-320-after.png
gh plate evidence 1051 --body-file body.md shot.png --json
```

Implementation is POSIX shell (`scripts/plate_evidence.sh`) with a thin `gh plate evidence` entry in `plate_core.cli`; the script invokes `python3 -m plate_core.plate_evidence`.

## MCP

Prefer **`plate_pr_evidence`** with `pr_number`, `body_file`, and `images` (array of paths). Behavior matches the CLI.

## When upload is refused

Third-party cloud agents without a user PAT cannot use `gh --attach`. The command prints the **route UI work to Copilot** guidance (assign the issue to GitHub Copilot's cloud coding agent). There is **no PAT workaround** in this wrapper—do not commit images or use raw/blob URLs.

## Requirements

- Local or Copilot-hosted agents with a supported token and **gh ≥ 2.99**.
- Body file on disk; image paths must exist.
- Each image should appear as `![meaningful alt](./file.png)` (the tool adds or fixes references when missing or empty).