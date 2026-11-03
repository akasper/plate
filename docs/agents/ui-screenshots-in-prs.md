# UI Screenshots in PRs

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## UI screenshot evidence (#1050)

User-visible UI changes require inline visual proof on the pull request. Agents must not commit screenshot binaries to git.

### Required captures

For every PR that changes user-visible UI:

- **Desktop width** — capture at a typical desktop viewport.
- **Mobile width** — capture at **320px** viewport width.
- **Before and after** — when the change alters existing UI, include before and after shots where practical.

Embed images **inline** in the PR description or PR comments so reviewers see them without leaving GitHub.

### Upload with GitHub CLI only

Do **not** commit screenshots to the repository. Use GitHub CLI attachment support (**gh >= 2.99**):

1. Check the CLI version first: `gh --version` (must be **2.99** or newer for `--attach`).
2. Attach when creating, editing, or commenting on a PR:

```bash
gh pr create --attach ./desktop-after.png --attach ./mobile-after.png ...
gh pr edit <number> --attach ./shot.png
gh pr comment <number> --attach ./shot.png
```

### Forbidden patterns

- **Never** commit screenshot files to git history.
- **Never** embed images using relative repository paths (they render broken on GitHub).
- **Never** use `raw.githubusercontent.com` or `blob/...?raw=true` URLs for PR evidence.

### Token matrix (who can `--attach`)

| Agent context | PAT / host | Can use `gh --attach`? |
|---|---|---|
| Local CLI agents | `gho_`, `ghp_`, `github_pat_` | Yes |
| GitHub Copilot cloud coding agent | Copilot-hosted | Yes |
| Third-party cloud agents (Cursor, Amp, Devin, etc.) | No user PAT on hosted runners | **No** |

Third-party cloud agents do not receive a user PAT; they cannot upload PR attachments.

### Routing UI work to Copilot

- Assign UI-heavy issues to **GitHub Copilot's cloud coding agent** (assign the issue to Copilot on GitHub).
- An agent that cannot use `gh pr create|edit|comment --attach` must **hand off** UI screenshot work to Copilot (or a human with local `gh` and a PAT) rather than committing images or using broken URL embeds.
