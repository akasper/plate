# plate_core

**plate_core** is the shared library powering the [PLATE](https://github.com/akasper/plate_template) platform tooling. It is designed to be deployed in three forms:

| Surface | Target User | How to Install |
|---|---|---|
| `gh plate` extension | Humans and scripts — terminal PLATE health checks | `gh extension install akasper/plate` |
| `plate-mcp` MCP server | AI agents — first-class tool calls via `/mcp` in supported CLIs | `pip install plate-core` then `plate-mcp` (or `python -m plate_core.mcp_server`) |
| CLI agent plugin (e.g. Copilot CLI, Grok Build, other standards-compliant CLIs) | Interactive sessions — `/agent plate` + MCP wiring (see grok-build epic for CLI-agnostic details) | `pip install plate-core` then `copilot plugin marketplace add akasper/plate` and `copilot plugin install plate-core@plate-marketplace` |

All surfaces are backed by the same `plate_core` library, ensuring consistent behavior regardless of how you access PLATE platform features.

**Licensing**

This project is licensed under a source-available model (MIT base + Commons Clause License Condition v1.0). Free for non-commercial/personal/internal use and modification. Commercial use, resale, or SaaS offerings require a separate license. See the [LICENSE](LICENSE) file for the full text.

## What It Does

`plate_core` surfaces the live state of a PLATE project by querying the GitHub API and applying PLATE methodology rules:

- **Health check** — label coverage, branch protection status, open Epic count
- **Epic status** — per-epic child issue summary via `gh plate epic status`
- **Feature detection** — optional PLATE capability detection (Playwright E2E, plugin setup, etc.) via `gh plate features`
- **Bootstrap planning** — new-project setup planning/apply baseline via `gh plate bootstrap`
- **Baseline agents and skills** — discoverable catalog via `gh plate agents` and `gh plate skills`
- **PR feedback babysitting** — local monitoring/trigger flow via `gh plate pr babysit <number>`
- **E2E Playwright tooling** — scaffolding, recording, and validation tools via MCP
- **MCP tools** — `plate_health`, `plate_epic_status`, `plate_features`, `plate_bootstrap`, `plate_plan_epic`, `plate_pr_babysit`, `plate_resolve_review_thread`, `plate_agents`, `plate_agent`, `plate_skills`, `plate_skill`, `init_playwright`, `record_e2e_gif`, `validate_e2e_tests` return structured payloads
- **CLI agent plugin** — installable agent surface (`/agent plate` or equivalent) with bundled MCP server configuration (CLI-agnostic per grok-build epic)

## Quick Start

### As a Python package (for `plate-mcp` + library use)

```bash
pip install plate-core
plate-mcp   # stdio MCP server for agents
python -c "import plate_core; print(plate_core.__version__)"
```

### As a `gh` extension (v1 baseline)

```sh
gh extension install akasper/plate
gh plate health                   # PLATE health check for the current repo
gh plate health --repo akasper/plate --json
gh plate epic status --repo akasper/plate --json
gh plate features --repo akasper/plate --json
gh plate agents list --json
gh plate agents show research-agent --json
gh plate skills list --json
gh plate skills show crud-projects --json
gh plate bootstrap --repo akasper/plate --json     # dry-run plan
gh plate bootstrap --repo akasper/plate --apply    # apply supported steps
gh plate pr babysit 112 --repo akasper/plate --json
```

### As an MCP server (v1 baseline; works in Copilot CLI, Grok Build, and other compatible agents)

```sh
# In a supported CLI agent session (e.g. Copilot CLI):
/mcp connect /absolute/path/to/plate/plate-mcp
# Then call tools: plate_health, plate_epic_status, plate_features, plate_bootstrap, plate_plan_epic, plate_pr_babysit, plate_resolve_review_thread, plate_agents, plate_agent, plate_skills, plate_skill
```

### As a CLI agent plugin (Copilot CLI, Grok Build, and other standards-compliant CLIs)

```sh
# Install the runtime prerequisite first so the plugin's MCP command is available.
pip install plate-core

# Register this repository as a marketplace, then install the plugin from it.
copilot plugin marketplace add akasper/plate
copilot plugin install plate-core@plate-marketplace

# Grok Build (TUI / CLI):
grok plugin marketplace add akasper/plate
grok plugin install plate-core@plate-marketplace
# Then (after enable/trust + reload): grok inspect, Ctrl+L → Agents / Marketplace, or /agent plate

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

Before cutting the release that includes this marketplace path:

1. Confirm `.github/plugin/marketplace.json` (Copilot) and `.grok-plugin/marketplace.json` (Grok) still point at the intended plugin source (`.plugin/` for the committed payload used by generator + e2e).
2. Re-run `python3 scripts/generate-grok-plugin-index.py` (and commit) if `plugin/agents/` or `.mcp.json` or manifest keys changed; then `python3 scripts/generate-grok-plugin-index.py --check`.
3. Verify the runtime prerequisite is available with `pip install plate-core`.
4. Smoke-test the pre-launch install flows (Copilot + generator for Grok):
   ```sh
   copilot plugin marketplace add akasper/plate
   copilot plugin install plate-core@plate-marketplace
   python3 scripts/generate-grok-plugin-index.py --check
   ```
5. Complete the human-owned publication tasks tracked in #380 and #381.
6. Fold the finished Epic into the active release issue (#376) and cut the release through the normal PLATE release ceremony.

See the grok-build epic for full CLI-agnostic details and verification that no vendor-specific language remains in the plugin files. (This release also closes the Grok marketplace discovery gap reported in #570.)


## Playwright E2E Testing

`plate_core` includes tools for scaffolding, validating, and managing Playwright E2E tests:

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
plate/
├── .plugin/               # root plugin discovery manifest + agent + MCP config
├── .github/plugin/        # Copilot CLI marketplace manifest
├── plugin/                # plugin source surface (mirrors .plugin metadata)
├── src/plate_core/
│   ├── github_client.py   # gh api wrapper
│   ├── health.py          # shared health logic
│   ├── cli.py             # shared CLI command handlers
│   ├── features.py        # feature detection (local and remote)
│   ├── agent_guidance.py  # agent prompting strategies
│   ├── baseline_catalog.py  # baseline agent/skill catalog loader
│   ├── mcp/tools.py       # Playwright E2E MCP tools
│   ├── mcp_server.py      # MCP stdio server (health, epic, catalog, e2e tools)
│   └── data/
│       └── baseline_catalog.yml
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
