# Troubleshooting

Symptom notes for PLATE operators. The fuller guide is tracked by #1063.

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
