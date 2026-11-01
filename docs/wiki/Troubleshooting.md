# Troubleshooting

Symptom notes for PLATE operators. The fuller guide is tracked by #1063.

## `gh extension upgrade plate` does not change behavior

The GitHub CLI extension only wraps the pinned `plate-core` version bundled with that extension build. If upgrade appears to do nothing, compare what is installed:

```text
gh extension list
gh plate self-migrate --plan
```

The `self-migrate --plan` output includes an `Installed:` line with the `plate-core` version importable from the same `python3` the `gh-plate` launcher uses (`#!/usr/bin/env python3`). There is no root `gh plate --version` flag—the CLI requires a subcommand. To query the version directly with that interpreter:

```text
python3 -c "import plate_core; print(plate_core.__version__)"
```

When the installed version is still older than you expect, reinstall or upgrade the extension from the current release (`gh extension install akasper/gh-plate` or `gh extension upgrade plate`), then run `gh plate self-migrate --plan` again. If versions still disagree, check which `python3` your shell resolves (`type python3` or `which python3`) while running `gh plate`; the launcher does not read a separate interpreter environment variable.

## `gh extension upgrade plate` fails after a gh-plate history rewrite

On **2026-10-23**, upstream `akasper/gh-plate` rewrote `main` (scrubbed email from history). The old extension clone head was `2e0b9b6`; current `main` is `cf0630c`. GitHub CLI keeps a local clone of the extension repo, so `gh extension upgrade plate` may fail with a non-fast-forward error when your clone still points at the pre-rewrite history.

Reinstall the extension (same fix as a stuck pin):

```bash
gh extension remove plate && gh extension install akasper/gh-plate
```

Then confirm with `gh extension list` and `gh plate self-migrate --plan`. Full upgrade sequencing for adopters lives in [adoption-guide.md](../migration/adoption-guide.md) (stub upgrade guide: #1069).

## Pip install fails on “externally managed environment” (PEP 668)

On many Linux distributions, system Python is marked **externally managed**, so `pip install plate-core` (including when invoked by the `gh-plate` launcher via `python3 -m pip install --user`) may refuse to write into the system site-packages. The `plate-core` wheel exposes only the `plate-mcp` console script, not a standalone `plate` CLI—`gh plate` always goes through the extension launcher.

Use a dedicated venv and put its `python3` first on `PATH` so the launcher’s `env python3` shebang and pip installs target that environment:

```text
python3 -m venv ~/.local/plate-venv
~/.local/plate-venv/bin/pip install 'plate-core==X.Y.Z'
export PATH="$HOME/.local/plate-venv/bin:$PATH"
gh plate self-migrate --plan
```

Confirm the `Installed:` line matches the pin in the extension’s `PLATE_CORE_VERSION` / `VERSION` file after upgrading the extension.

## Windows console windows flash while babysitting a PR

On Windows, `gh` and `git` are console programs. A windowless parent that starts them without `CREATE_NO_WINDOW` allocates a console for each child. That console takes focus and then closes. A `gh plate pr babysit --watch` loop does this about once per poll interval (the default is 60 seconds).

`gh` can also spawn `tzutil` for telemetry and an update check. Those are extra flashes. PLATE sets `GH_NO_UPDATE_NOTIFIER=1` and `DO_NOT_TRACK=1` on the children it starts.

Plate-core 0.8.3 and later routes `gh` and `git` through one helper that passes `CREATE_NO_WINDOW` and hides the window. Upgrade `plate-core` and the `gh-plate` extension together. The pin is `PLATE_CORE_VERSION` next to the `gh-plate` launcher.

### The watcher keeps running after the agent exits

`--watch` records `.agentic/babysit/babysit-<owner>-<repo>-<pr>.pid`. `.plate` is the JSON config file, so the pid cannot live inside it. The loop stops when its parent process exits, on Ctrl+C, or when you stop it:

```text
gh plate pr babysit --stop
gh plate pr babysit 63 --stop
```

The first command stops every watcher recorded in this checkout. The second stops one PR. A second `--watch` for the same PR does not start another process while the recorded pid is still alive.

If the flashes continue after `--stop`, the leftover process is not a recorded PLATE watcher. From PowerShell:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'plate|babysit|plate-mcp|plate_core' } |
  Select-Object ProcessId, ParentProcessId, Name, CommandLine
taskkill /F /T /PID <python-pid>
```
