# Self-hosted runners for PLATE adopters (private repos)

PLATE supports optional **ephemeral self-hosted runners** so private repositories can run CI on machines you already own when those machines are idle. This guide is general adopter documentation (Epic [#1210](https://github.com/akasper/plate/issues/1210)); project-specific install scripts belong in each adopting repository and are **reference implementations only**, not requirements of PLATE core.

Related operator docs:

- [Actions cost rollout](./actions-cost-rollout.md) — workflow guards and merged `pr-gates` before you add local compute.
- `gh plate runner` — CLI entry point; full subcommands (`add`, `status`, `remove`, `doctor`) land in [#1212](https://github.com/akasper/plate/issues/1212).

## Security warning

**Self-hosted runners execute arbitrary code from your repository and from pull requests that can reach those workflows.**

| Rule | Why |
|---|---|
| **Private repositories only** | Never register a self-hosted runner on a **public** repository. Public repos can receive drive-by PRs; any workflow that uses your runner labels can run untrusted code on your hardware. |
| **No fork or outside-contributor PRs on local machines** | Workflows triggered by forks or by contributors who are not trusted maintainers must **not** use self-hosted runner labels. Keep those jobs on GitHub-hosted runners (or disable them) until you have an explicit, reviewed trust model. |
| **Non-admin runner OS user** | The account that runs the runner service must not be an administrator and must not have access to personal files, SSH keys, browser profiles, or unrelated projects on the host. |
| **Secrets per repository** | Use repository (or environment) secrets scoped to the private repo that owns the runner. Do not reuse org-wide secrets across untrusted repos. |
| **Ephemeral runners** | Prefer one job per runner process, then exit. Long-lived runners retain disk state and increase blast radius if a job is compromised. |
| **Assume breach** | Treat the runner host as periodically untrusted. Patch the OS, rotate registration tokens, and avoid storing long-lived credentials on the runner user profile. |

GitHub [postponed](https://github.blog/changelog/) its planned per-minute charge for self-hosted runners but **did not cancel** it. Budget for possible future billing when comparing local vs hosted compute.

## GitHub account and runner registration limits

On a **personal GitHub account**, a self-hosted runner registration is tied to **one repository**. You cannot share a single registration across multiple repos.

Practical patterns:

1. **One runner registration per private repo** (several repos on the same physical host each get their own registration and token).
2. **Several runner processes on one host**, each registered to the same repo (ephemeral pool).
3. **A free GitHub organization** so org-level runner groups can serve multiple private repos with shared labels and policies (still follow the security rules above).

PLATE does not require a specific hosting vendor; adopters choose machines they control.

## Isolation and host setup

### Runner user and filesystem

- Create a dedicated OS user (for example `plate-runner`) with **no** admin rights.
- Run registration and job checkout only under that user’s home or a dedicated data directory.
- Deny read access to your personal home directory, password stores, and unrelated source trees.

### Ephemeral runners

- Register runners as **ephemeral** when GitHub’s registration API allows it, so the agent exits after one job.
- Use a small **idle watcher** on each machine (see [#1213](https://github.com/akasper/plate/issues/1213)) to start the next ephemeral runner only when the host is quiet. The watcher must **not** stop a job that is already running.

### Windows: WSL2 with resource caps

On Windows, run Linux jobs inside **WSL2**, not directly on the desktop session.

- Set CPU and memory limits in `.wslconfig` so CI cannot starve interactive work.
- Run the runner process at **low priority** inside WSL2.
- Keep the Windows-side runner user separate from your everyday account.

### Linux and containers

Linux runners may use a dedicated VM, a container, or WSL2 on Windows. Containers simplify teardown between jobs but still need a non-root runner user and no mount of sensitive host paths.

### macOS

A **macOS runner accepts only macOS `runs-on` labels** unless you add Docker or a VM that provides another OS. Workflows that must run on macOS should not rely on Linux-only steps in the same job. Plan separate jobs or use hosted runners for Linux-only gates.

## Shared label pool and idle-only policy

Design from [#1210](https://github.com/akasper/plate/issues/1210):

- Register every machine with a **shared label** (for example `plate-local`) plus an **OS label** (`linux`, `windows`, or `macos`).
- GitHub schedules each job onto any **online, idle** runner whose labels match. Machines that are off or busy are skipped.
- **Run only when idle:** the watcher starts a new ephemeral runner only when CPU load is below a threshold, the machine is on AC power (where applicable), and there has been no recent interactive use. Thresholds and quiet hours are per-machine settings.
- Open question for adopters: how to detect “in use” on each OS without being fooled by background apps (sleep state alone is unreliable on laptops).

No machine needs to be dedicated full-time; local runners are for **spare capacity**, not a replacement for hosted CI safety gates.

## Fallback to GitHub-hosted runners

When **no** local runner is free, GitHub **queues** the job rather than automatically moving it to hosted runners.

PLATE’s workflow integration ([#1214](https://github.com/akasper/plate/issues/1214)) adds a **`select-runs-on` job** in heavy workflows (`ci.yml`, `test-e2e.yml`) that probes for an online, idle runner with your label and passes `runs-on` to downstream jobs. The composite action calls GitHub’s **List self-hosted runners for a repository** API; that endpoint requires **repository administration read** on the token (for example `actions: read` alone is not enough). When the probe returns 403, 404, or a network error, the action logs a warning and falls back to `ubuntu-latest` instead of failing the workflow.

<!-- PLATES-CORE:BEGIN self-hosted-runner-probe-permissions -->
The idle-runner probe in `.github/actions/plate-select-runs-on/action.yml` needs permission to list repository self-hosted runners. Grant the workflow job enough scope (typically **Administration: read** on the repository for `GITHUB_TOKEN`, or use a PAT with equivalent access). Without it, PLATE treats the probe as unavailable and uses GitHub-hosted `ubuntu-latest` for heavy jobs.
<!-- PLATES-CORE:END self-hosted-runner-probe-permissions -->

Set a **job timeout** so a queued job eventually runs on GitHub-hosted runners instead of waiting up to GitHub’s default queue horizon (on the order of a day).

## Checklist before you register

1. Repository is **private** and will stay private while runners are registered.
2. Branch protection and `pr-gates` are configured ([actions-cost-rollout](./actions-cost-rollout.md)).
3. Fork/outside PR workflows use **hosted** `runs-on` only.
4. Dedicated non-admin runner user, ephemeral mode, per-repo secrets.
5. Windows jobs use WSL2 with `.wslconfig` caps; macOS jobs use macOS runners only.
6. Idle watcher and fallback behavior tested on a non-production repo first.

## PLATE artifacts (optional)

- Runner metadata may be recorded under `.agentic/` when `gh plate runner` commands ship ([#1212](https://github.com/akasper/plate/issues/1212)).
- Reference rollouts in adopting repos are tracked separately ([#1216](https://github.com/akasper/plate/issues/1216)).
