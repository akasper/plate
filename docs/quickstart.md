# PLATE quickstart

Install PLATE, adopt it into a repository, confirm health, and run the first Feature pull request through release integration. This page is for **human operators and coding agents** adopting PLATE. It is grounded in `SPEC.md`, the root `README.md`, and the shipped `gh plate` CLI (`src/plate_core/cli.py`).

For agent operating rules and ceremonies in depth, see `AGENTS.md` and the linked pages under `docs/agents/`. You do not need those files to complete adoption and the first Feature PR.

## What you are installing

PLATE (Product Lifecycle Automation Toolkit and Engine) connects GitHub Issues, labels, workflows, and local `.plate` / `.agentic/` state so humans keep judgment while agents execute process loops (`SPEC.md` — Purpose and Vision).

Three install surfaces share one Python library (`plate_core`, PyPI name **`plate-core`**):

| Surface | Install | Typical use |
|---|---|---|
| `gh plate` | `gh extension install akasper/gh-plate` | Terminal commands in any repo |
| `plate-mcp` | `pip install 'plate-core==…'` then `plate-mcp` | MCP tool calls from agents |
| CLI agent plugin | `pip install` + marketplace install from `akasper/plate` | Conversational `/agent plate` sessions |

This quickstart focuses on **`gh plate`** plus **`plate-core`** on `PATH`. MCP and plugin steps are optional extensions after health is green.

## Prerequisites

- **Git** and **GitHub CLI** (`gh`) authenticated to the target repository (`gh auth status`).
- **Python ≥ 3.10** with `pip`.
- A **GitHub repository** you can push to (empty greenfield repo, or an existing product codebase).

Do **not** create adopters from `akasper/plate_template` or copy files manually from `src/plate_core/template_payload/`. Use `gh plate bootstrap` and `gh plate import-payload` only (`docs/bootstrap/starting-a-new-repository.md`).

## 1. Pin install versions

Align **PyPI `plate-core`** with the **`gh-plate` extension** pin (`PLATE_CORE_VERSION` beside the extension). As of this repository’s `pyproject.toml`, the public pin is **0.12.0** (see root `README.md` → Quick Start → Install versions).

```bash
pip install -U 'plate-core==0.12.0'
python3 -c "import plate_core; print(plate_core.__version__)"   # expect 0.12.0

gh extension install akasper/gh-plate    # first install
# gh extension upgrade plate             # later upgrades
```

**Pin mismatch symptom:** `gh plate` reports a version lock for an older `plate-core` (for example `0.7.2`) while you installed `0.12.0`. Reinstall the extension and re-run `pip install -U 'plate-core==0.12.0'`. Details: root `README.md`.

**Verify locally (monorepo dev checkout):**

```bash
PYTHONPATH=src python3 -c "import plate_core; print(plate_core.__version__)"
```

## 2. Choose a path: greenfield or existing codebase

### Greenfield (empty GitHub repository)

1. Create an empty repo (no template):

   ```bash
   gh repo create OWNER/NAME --private
   git clone https://github.com/OWNER/NAME.git && cd NAME
   ```

2. Plan bootstrap (dry-run — no `--apply`):

   ```bash
   gh plate bootstrap --repo OWNER/NAME --greenfield
   ```

3. Apply when the plan looks right:

   ```bash
   gh plate bootstrap --repo OWNER/NAME --greenfield --apply
   ```

`--apply` materializes scaffold, labels, starter issues, and baseline GitHub settings. Dry-run is the default without `--apply`.

Follow `docs/bootstrap/new-repository-checklist.md` for human decisions after bootstrap.

### Existing codebase (adoption)

Work from your local checkout root (`cd` into the repo).

#### Optional: adoption session timer

For under-30-minute adoption proofs (`gh plate adopt --help`), start a session before you begin:

```bash
gh plate adopt --start-session --json
```

Session timing is recorded under `.agentic/adoption/session.json`. Finish with `gh plate adopt --complete-session --json` when core readiness is reached.

#### Step A — Local payload (reviewable diffs)

`gh plate import-payload` defaults to **dry-run** (`--dry-run` is default; pass `--apply` to write files). Strategy choices: `safe` (skip existing), `conservative` (report conflicts), `force` (overwrite — use only with explicit human approval).

```bash
gh plate import-payload --dry-run --strategy conservative --json
# When the plan is acceptable:
gh plate import-payload --apply --strategy conservative
```

If `conservative` reports conflicts, review output or use `--escape-hatch-on-conflict` per `import-payload --help`; do not auto-force.

Commit the scaffolding before GitHub-side bootstrap when your process requires it.

#### Step B — GitHub-side adoption baseline

```bash
gh plate bootstrap --repo OWNER/REPO --adopt --apply
```

`--adopt` (alias `--existing-repo`) forces adoption mode for mature repos. Omit `--apply` to plan only. `--repo` defaults to `git remote origin` when omitted.

#### Step C — Readiness check

```bash
gh plate adopt --json
gh plate health --json
```

`gh plate health` accepts `--repo`, `--repo-root`, `--no-spec-audit`, and `--json` (`gh plate health --help`). Fix gaps the report names (for example missing `.plate` via `gh plate config init`, or label sync via `gh plate bootstrap --apply`).

When adoption looks complete, end the session if you started one:

```bash
gh plate adopt --complete-session --require-core-ready --json
```

Deeper sequence: `docs/migration/adoption-guide.md`.

## 3. Confirm health and next step

```bash
gh plate health
gh plate what-next --json
```

`what-next` ranks the next safe process step (open PRs, adoption, ready work, epics, and related signals per `SPEC.md` Target Workflows).

Optional agent surface after health is acceptable:

```bash
pip install -U 'plate-core==0.12.0'
plate-mcp   # stdio MCP server
```

## 4. First Feature: branch → implement → PR

PLATE expects **test-first** delivery and **atomic pull requests** tied to typed GitHub Issues (`SPEC.md` Goals; `CONTRIBUTING.md`).

### 4.1 Discover the integration base

Always run release status **before** choosing a PR base branch (`SPEC.md` Target Workflows; `docs/agents/documentation-rules.md`):

```bash
gh plate release status --json
```

Use the integration base branch the status report expects for your repository’s release mode (legacy single `release` branch or track-specific `release-major` / `release-minor` / `release-patch`). Pass that branch explicitly as `--base` when opening a PR — do not assume the repository default branch.

If standing release branches or the “Next Release” issue are missing, plan repair (dry-run by default):

```bash
gh plate release repair
gh plate release init          # alias for repair
# gh plate release repair --apply   # when you intend to create missing artifacts
```

### 4.2 Open a tracked Feature issue

Create a GitHub Issue with the `Feature` label and an Epic milestone when your repository uses Epics (`CONTRIBUTING.md` — Issue Rules). Agents may use host tooling; humans use GitHub UI or `gh issue create`.

### 4.3 Implement on a feature branch

```bash
git checkout -b feature/short-slug
# implement + tests (project test command; PLATE monorepo example:
#   PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

Feature pull requests that change product behavior typically add a release fragment:

```text
.agentic/releases/unreleased/<slug>.json
```

Fragments accumulate until release cut (`docs/agents/documentation-rules.md`).

### 4.4 Preflight and open the PR

`gh plate pr preflight` runs local plate-pr-gates and label checks. `gh plate pr create` runs the same checks, then invokes `gh pr create` with your remaining arguments (`src/plate_core/pr_preflight.py`).

```bash
gh plate pr preflight \
  --base <integration-base-from-release-status> \
  --labels Feature \
  --body-file /path/to/pr-body.md

gh plate pr create \
  --base <integration-base-from-release-status> \
  --title "Short human-readable title" \
  --label Feature \
  --body-file /path/to/pr-body.md
```

Include a closing keyword in the PR body when the PR should close the issue (`Closes #N`). Set exactly one PR type label at create time (`Feature`, `Bug`, `Documentation`, `Feedback Response`, or `Hardening`).

### 4.5 PR green loop

After the PR exists:

```bash
gh plate pr health <PR_NUMBER> --json
gh plate pr verify <PR_NUMBER> --run-tests    # optional local unittest gate
gh plate pr babysit <PR_NUMBER> --json        # monitor actionable review feedback
# gh plate pr babysit <PR_NUMBER> --act       # post babysit trigger when feedback exists
```

`pr babysit` defaults `--branch-update-strategy` to `local-rebase` (`gh plate pr babysit --help`). Merge still requires human approval unless your repository’s autonomous-mode policy allows otherwise (`SPEC.md` — PR green loop).

## 5. Release integration (operator overview)

Day-to-day Feature work lands on the integration base from `gh plate release status`. Release packaging is a separate ceremony:

1. **Status** — pending fragments, linked Epics, on-hold work:

   ```bash
   gh plate release status
   gh plate release notes --json
   ```

2. **Cut** — aggregate unreleased fragments into a versioned directory (dry-run first):

   ```bash
   gh plate release cut --dry-run
   # gh plate release cut vX.Y.Z
   ```

3. **Release PR** — typically from the versioned release branch toward `main`, with `Release` and `Documentation` labels and a standing Release issue (full ceremony: `docs/design/release-ceremony-refinement.md` and `AGENTS.md` via `docs/agents/branch-model-and-ceremonies.md`).

4. **Finalize** — after the Release PR merges and tagging workflows run:

   ```bash
   gh plate release finalize vX.Y.Z --dry-run
   # gh plate release finalize vX.Y.Z --apply
   ```

Use `gh plate release finalize --help` for side effects (`--apply`, `--force-hard-reset`).

## 6. Where to go next

| Goal | Doc / command |
|---|---|
| Full adoption checklist | `docs/migration/adoption-guide.md` |
| New empty repo | `docs/bootstrap/starting-a-new-repository.md` |
| Upgrade pins / payload | `gh plate self-migrate --plan` · root `README.md` |
| Operator rules (when you need them) | `AGENTS.md` |
| Product intent | `SPEC.md` |

## Command index (verified against `plate_core` CLI)

All subcommands below are registered in `src/plate_core/cli.py`. Run `PYTHONPATH=src python3 -m plate_core.cli <command> --help` in a dev checkout, or `gh plate <command> --help` when the extension is installed.

| Step | Command |
|---|---|
| Install verify | `python3 -c "import plate_core; print(plate_core.__version__)"` |
| Adoption session | `gh plate adopt --start-session` · `--complete-session` |
| Local payload | `gh plate import-payload --dry-run --strategy conservative` · `--apply` |
| GitHub bootstrap | `gh plate bootstrap --adopt --apply` · `--greenfield --apply` |
| Health | `gh plate health` · `gh plate health --json` |
| Next step | `gh plate what-next --json` |
| Release base | `gh plate release status` |
| PR gates | `gh plate pr preflight` · `gh plate pr create` |
| PR monitor | `gh plate pr babysit` |
| Release cut/finalize | `gh plate release cut` · `gh plate release finalize` |