# PLATE

**PLATE** (Process Lifecycle Agentic Task Engine) is a GitHub-native methodology and tooling monorepo for agent-driven software delivery. Humans keep judgment; agents do the toil; GitHub preserves truth.

This repository (`akasper/plate`) is the **implementation monorepo**. The installable Python package on PyPI is still named **`plate-core`** (import path `plate_core`); the product name is PLATE.

| Surface | Target User | How to Install |
|---|---|---|
| `gh plate` extension | Humans and scripts — terminal PLATE operations | `gh extension install akasper/gh-plate` (pins `plate-core` via extension `PLATE_CORE_VERSION`) |
| `plate-mcp` MCP server | AI agents — first-class tool calls via MCP | `pip install 'plate-core==0.8.0'` then `plate-mcp` (or `python -m plate_core.mcp_server`) |
| CLI agent plugin (Copilot CLI, Grok Build, …) | Interactive sessions — plate persona + MCP wiring | same runtime pin, then marketplace install from this repo (see below) |

All surfaces share the same library code under `src/plate_core/`, so CLI, MCP, and plugins stay in parity.

**Current public pin (v0.8.0):** prefer an explicit pip pin and a current `gh-plate` extension so agents do not mix 0.7.x runtime with 0.8.x docs.

**Licensing**

This project is licensed under a source-available model (MIT base + Commons Clause License Condition v1.0). Free for non-commercial/personal/internal use and modification. Commercial use, resale, or SaaS offerings require a separate license. See the [LICENSE](LICENSE) file for the full text.

## What It Does

PLATE tooling reads GitHub + local `.plate` / `.agentic/` state and drives process loops:

- **Health & routing** — `gh plate health`, `gh plate what-next` / `plate_what_next` (priority ladder: budget, open PRs, adoption, self-migrate, ready work, PM, epics)
- **Autonomy** — budgeted AutonomyEngine (`.plate` `autonomy.risk_tolerance`), procedures, checkpoints, ledger, shadow/simulate for high-impact actions
- **Project Manager** — long-running orchestrator (`gh plate pm`, fleet handoffs, loop ticks); browser UI deferred
- **Endless feed + Q&A planning** — Questions/Tasks feed; product/feature/release planning sessions with approval
- **Adoption & self-migrate** — under-30m local path (`gh plate adopt`, import-payload, session timer); pin/payload self-migrate plan + offline verify
- **Release ceremony** — multi-track release status, fragments, cut/finalize helpers
- **PR green loop** — `gh plate pr babysit` with feedback resolution and base sync strategies
- **Epic / feature / bug loops** — status, stubs, feature/bug stage machines, media + design contracts
- **Baseline agents & skills** — catalog via `gh plate agents` / `gh plate skills`
- **E2E Playwright helpers** — scaffold/validate/record via MCP
- **CLI agent plugin** — default plate persona when PLATE signals are present (`AGENTS.md`, `.plate/`)

See `AGENTS.md`, `SPEC.md`, and `docs/wiki/V1-Autonomy-Surfaces-Epic-Closeouts.md` for operating rules and first-slice surface status. Release **#654** tracks v1.0.0 readiness (do not claim 1.0 without checklist E2E).

## Quick Start

### Install versions (pip + gh-plate pin)

After the **v0.8.0** cut, public surfaces are:

| Surface | Expected version | Verify |
|---|---|---|
| PyPI `plate-core` | **0.8.0** (latest) | `python -c "import plate_core; print(plate_core.__version__)"` |
| `gh` extension `akasper/gh-plate` | **v0.8.0** (ships `PLATE_CORE_VERSION=0.8.0`) | `gh extension list` · extension dir `PLATE_CORE_VERSION` |
| This monorepo (dev) | `pyproject.toml` / `plate_core.__version__` **0.8.0** | `PYTHONPATH=src python -c "import plate_core; print(plate_core.__version__)"` |

```bash
# Runtime (recommended pin for adopters and CI)
pip install -U 'plate-core==0.8.0'
python -c "import plate_core; print(plate_core.__version__)"   # expect 0.8.0

# gh extension: install or upgrade so the thin shim pin matches
gh extension install akasper/gh-plate        # first time
gh extension upgrade plate                   # later (or: gh extension upgrade gh-plate)
# If upgrade leaves an old pin, reinstall:
#   gh extension remove plate && gh extension install akasper/gh-plate

# Optional: confirm the extension pin file (path varies by gh install layout)
#   cat "$(dirname "$(which gh-plate 2>/dev/null || true)")/PLATE_CORE_VERSION"
```

**Pin mismatch symptom:** `gh plate` prints `plate-core version lock active ... ensuring plate-core==0.7.2` (or another older pin) while docs assume 0.8.0. Fix with extension upgrade/reinstall + `pip install -U 'plate-core==0.8.0'`. Self-migrate with an **explicit** target should not report false drift when pin already equals that target (`gh plate self-migrate --plan --json` / `--verify`).

### As a Python package (`plate-core` on PyPI + MCP)

```bash
pip install -U 'plate-core==0.8.0'
plate-mcp   # stdio MCP server for agents
python -c "import plate_core; print(plate_core.__version__)"  # 0.8.0
```

### As a `gh` extension

```sh
gh extension install akasper/gh-plate   # or: gh extension upgrade plate
gh plate health --json
gh plate what-next --json
gh plate autonomy --status
gh plate pm --status
gh plate feed --json
gh plate release status
gh plate adopt --json
gh plate self-migrate --verify --json
gh plate epic status --repo akasper/plate --json
gh plate bootstrap --repo OWNER/REPO --adopt --json
gh plate pr babysit 112 --repo akasper/plate --json
```

The `gh plate` extension is published from a dedicated thin repository (`akasper/gh-plate`) so the GitHub CLI name starts with `gh-`. Implementation, the `plate-core` package, MCP entrypoint, plugins, and source live in this monorepo (`akasper/plate`). The extension **version-locks** runtime via sibling `VERSION` / `PLATE_CORE_VERSION` (#614) — keep it on **v0.8.0** for post-cut work.

### As an MCP server (v1 baseline; works in Copilot CLI, Grok Build, and other compatible agents)

```sh
# In a supported CLI agent session (e.g. Copilot CLI):
/mcp connect /absolute/path/to/plate/plate-mcp
# Then call tools: plate_health, plate_epic_status, plate_features, plate_bootstrap, plate_plan_epic, plate_pr_babysit, plate_resolve_review_thread, plate_agents, plate_agent, plate_skills, plate_skill
```

### As a CLI agent plugin (Copilot CLI, Grok Build, and other standards-compliant CLIs)

```sh
# Install the runtime prerequisite first so the plugin's MCP command is available.
pip install -U 'plate-core==0.8.0'

# Register this repository as a marketplace, then install the plugin from it.
copilot plugin marketplace add akasper/plate
copilot plugin install plate-core@plate-marketplace

# Grok Build (TUI / CLI):
grok plugin marketplace add akasper/plate
grok plugin install plate-core@plate-marketplace --trust
# Then enable the plugin, reload the TUI (`r` in Plugins), and verify:
#   grok inspect   # expect plate-core skills, plate agent, and plate-core (stdio) MCP
# Or reinstall from a local checkout during development:
#   grok plugin install /absolute/path/to/plate/.plugin --trust

# In a new session with your CLI agent, invoke the plate agent (see your agent's docs for the exact command, e.g. /agent plate)
```

For local development or direct-source installation, these equivalent commands also work (adjust for your CLI):

```sh
copilot plugin install /absolute/path/to/plate
# or
copilot plugin install akasper/plate:plugin
# Grok equivalent: grok plugin install /absolute/path/to/plate --trust
```

The marketplace flow is the supported public install path. The plugin still expects the `plate-mcp` command to be available on `PATH`, which is why `pip install plate-core` remains a prerequisite until publication/runtime provisioning is further automated. There is no separate GitHub-run submission process for Copilot CLI or Grok Build marketplaces: this repository itself becomes the marketplace once the manifest is merged to the default branch and you treat that path as the supported public install channel.

#### Marketplace release checklist

Full maintainer checklist (surfaces, smoke, human Tasks): [`docs/bootstrap/marketplace-install-checklist.md`](docs/bootstrap/marketplace-install-checklist.md) (#378 / #379).

Before cutting a release that ships marketplace install:

1. Confirm `.github/plugin/marketplace.json` (Copilot → `source: "plugin"`) and `.grok-plugin/marketplace.json` (Grok → `./.plugin`) still point at the intended plugin payloads; versions match `plate-core`.
2. If baseline catalog skills changed, run `python3 scripts/generate-plugin-skills.py` (and commit) so `plugin/SKILLS.md`, `plugin/skills/*/SKILL.md`, and the mirrored `.plugin/` copies stay in sync; then `python3 scripts/generate-plugin-skills.py --check`.
3. Re-run `python3 scripts/generate-grok-plugin-index.py` (and commit) if `plugin/agents/`, `plugin/skills/`, `.mcp.json`, or manifest keys changed; then `python3 scripts/generate-grok-plugin-index.py --check`.
4. Verify the runtime prerequisite is available with `pip install -U 'plate-core==0.8.0'` (`plate-mcp` on `PATH`; print `__version__`).
5. Smoke-test the pre-launch install flows (Copilot + generator for Grok):
   ```sh
   copilot plugin marketplace add akasper/plate
   copilot plugin install plate-core@plate-marketplace
   python3 scripts/generate-plugin-skills.py --check
   python3 scripts/generate-grok-plugin-index.py --check
   pytest tests/test_copilot_cli_marketplace_packaging.py -q
   ```
6. Complete the human-owned publication tasks tracked in #380 and #381 (and #625/#626 when PyPI pins require them). Agents must not complete those Tasks.
7. Fold marketplace work into the active **Next Release** issue (#612) and cut through the normal PLATE release ceremony.

See the grok-build epic for full CLI-agnostic details and verification that no vendor-specific language remains in the plugin files. (This release also closes the Grok marketplace discovery gap reported in #570.)


## Playwright E2E Testing

PLATE includes tools for scaffolding, validating, and managing Playwright E2E tests:

### MCP Tools

- **`init_playwright`** — Initialize Playwright E2E setup in a repository
  ```sh
  # Copy config, test specs, and recording scripts from plate's template payload
  @copilot init-playwright repo_path="/path/to/repo"
  ```

- **`validate_e2e_tests`** — Verify Playwright setup and detect missing configuration
  ```sh
  @copilot validate-e2e-tests repo_path="/path/to/repo"
  ```

- **`record_e2e_gif`** — Record and generate demo GIF from a Playwright E2E test
  ```sh
  @copilot record-e2e-gif repo_path="/path/to/repo" test_name="feature-name" quality="medium"
  ```

### CLI Feature Detection

Check if a repo has Playwright E2E setup:

```sh
gh plate features --repo owner/repo
```

Output example:
```
Repo: akasper/plate_template

Autonomous Mode.................... ✅ ENABLED
Platform Monitor Workflow.......... ⏹️  NOT CONFIGURED
Copilot Plugin (.plugin)........... ✅ ENABLED
Copilot Plugin (plugin)............ ✅ ENABLED
MCP Manifest (.plugin)............. ✅ ENABLED
MCP Manifest (plugin).............. ✅ ENABLED
Per-feature change files........... ✅ ENABLED
Release notes..................... ✅ ENABLED
Baseline Agents Catalog........... ✅ ENABLED
Playwright E2E Testing............. ✅ ENABLED
```

## Runtime layout (v1 baseline)

```text
plate/                     # monorepo (product: PLATE)
├── AGENTS.md              # operating rules (source of truth with GitHub)
├── SPEC.md                # product intent
├── .plate                 # local autonomy/release config (JSON)
├── .agentic/              # fragments, procedures, costs, PM queue, …
├── .plugin/               # root plugin discovery + MCP config
├── .github/plugin/        # Copilot CLI marketplace manifest
├── plugin/                # plugin source (agents, skills)
├── src/plate_core/        # Python package (PyPI name: plate-core)
│   ├── health.py, what_next.py, autonomy.py, pm.py, feed.py, …
│   ├── adoption.py, self_migrate.py, release.py, pr_babysit.py, …
│   ├── cli.py, mcp_server.py
│   └── data/baseline_catalog.yml
├── docs/wiki/             # durable epic closeouts, Goals, …
├── gh-plate               # gh extension entrypoint
└── plate-mcp              # MCP server entrypoint
```

## Contributing

This repository follows the [PLATE methodology](https://github.com/akasper/plate_template). See `AGENTS.md` for agent operating rules and the full PLATE workflow.

---

## Keeping Your Fork Current

If your repository started from an older `plate_template` release and has local process customizations, avoid full-file replacement during upgrades.

<!-- PLATES-CORE:BEGIN keeping-your-fork-current -->
Use this sync flow:

1. Fetch upstream template updates (`git fetch upstream`) and review diffs for `AGENTS.md`, `.agentic/skills.yml`, `.agentic/releases/`, and workflows in `.github/workflows/` that contain `PLATES-CORE` markers.
2. Import only upstream-owned `PLATES-CORE` sections into your customized files.
3. Preserve local sections outside those markers.
4. Open an atomic PR with the correct PR type label and issue linkage (`Closes #N` when applicable).
5. Update per-feature change files in `.agentic/releases/` with imported behavior and evidence.
6. Run required checks before merge.

This keeps downstream repos aligned with new core PLATE behavior without erasing project-specific policy.
<!-- PLATES-CORE:END keeping-your-fork-current -->
