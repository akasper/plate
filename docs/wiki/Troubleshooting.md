# Troubleshooting

Symptom notes for PLATE operators. The fuller guide is tracked by #1063.

## `gh extension upgrade plate` does not change behavior

The GitHub CLI extension only wraps the pinned `plate-core` version bundled with that extension build. If upgrade appears to do nothing, compare what is installed:

```text
gh plate --version
gh extension list
```

When the reported `plate-core` version is still older than you expect, reinstall or upgrade the extension from the current release (`gh extension install akasper/gh-plate` or `gh extension upgrade plate`), then run `gh plate --version` again. If versions still disagree, check which `gh plate` executable your shell resolves (`type gh plate` or `where gh plate`) and that you are not mixing a pip-installed `plate_core.cli` entry point with the extension shim.

## Pip install fails on “externally managed environment” (PEP 668)

On many Linux distributions, system Python is marked **externally managed**, so `pip install plate-core` (including when invoked by the `gh-plate` launcher) may refuse to write into the system site-packages.

Use an isolated install instead:

- **venv:** `python3 -m venv ~/.local/plate-venv && ~/.local/plate-venv/bin/pip install 'plate-core==…'`
- **pipx:** `pipx install 'plate-core==…'`

Then ensure `gh plate` uses that environment, or run the CLI via the venv/pipx `plate` / `python -m plate_core.cli` entry point. Confirm with `gh plate --version` after changing install layout.

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
