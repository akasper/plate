# Pre-push hook (local format, lint, typecheck)

PLATE can install a **pre-push** git hook that runs your repo's format, lint, and typecheck commands against **only the files in commits you are pushing**, so agents and humans catch problems in seconds instead of after a CI round trip. The pattern is inspired by Owen Gretzinger's [October 2026 post on X about Boardy's CI work](https://x.com/owengretzinger/status/2116292908303393032); the commands and tooling here are entirely adopter-defined.

<!-- PLATES-CORE:BEGIN pre-push-hook-template-1281 -->
## Configure commands in `.plate`

Add non-empty command templates under `hooks.pre_push`. Use `{files}` where the changed paths should be inserted (each path is passed as a separate argument; templates are split with POSIX shell rules, not run through `cmd.exe` or `/bin/sh -c`). When a key is empty or omitted, that step is skipped. When **all three** are empty, the hook exits successfully without running anything.

Example:

```json
{
  "hooks": {
    "pre_push": {
      "format": "black {files}",
      "lint": "ruff check {files}",
      "typecheck": "mypy {files}"
    }
  }
}
```

Pick commands that match your stack. Keep them fast (target under ~10 seconds on typical agent edits).

Use the same shape under `hooks.pre_commit` when you prefer checks at **commit** time (staged files only) instead of at push time.

## Install the hook

From the repository root:

```bash
gh plate hooks install
```

For the pre-commit variant:

```bash
gh plate hooks install --hook pre-commit
```

This writes `.git/hooks/pre-push` or `.git/hooks/pre-commit` from the PLATE template (`scripts/plate/pre-push-hook.sh` or `scripts/plate/pre-commit-hook.sh` after bootstrap, or the bundled template in `plate-core`). Re-run after upgrading `plate-core` when the template changes. Use `--force` to replace a non-PLATE hook.

Check status:

```bash
gh plate hooks status --json
```

Agents can use MCP `plate_hooks_install` and `plate_hooks_status` instead of shelling out to the CLI.

## Bootstrap

Greenfield and adoption bootstrap plans mention this hook as an **optional** local step after you configure commands. It never blocks pushes when no commands are configured.

## Agent guidance

Prefer an installed hook (or another non-skippable automation) over a prose rule in `AGENTS.md` for checks that must **always** run before code leaves a machine. Hooks complement CI; they do not replace required GitHub checks.
<!-- PLATES-CORE:END pre-push-hook-template-1281 -->
