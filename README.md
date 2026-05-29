# plate_core

**plate_core** is the shared library powering the [PLATE](https://github.com/akasper/plate_template) platform tooling. It is designed to be deployed in three forms:

| Surface | Target User | How to Install |
|---|---|---|
| `gh plate` extension | Humans and scripts — terminal PLATE health checks | `gh extension install akasper/plate_core` |
| `plate-mcp` MCP server | AI agents — first-class tool calls via `/mcp` in Copilot CLI | `./plate-mcp` (repo clone) |
| Copilot CLI plugin | Interactive Copilot CLI sessions — `/agent plate` + MCP wiring | `copilot plugin install akasper/plate_core` |

All surfaces are backed by the same `plate_core` library, ensuring consistent behavior regardless of how you access PLATE platform features.

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
- **Copilot plugin** — installable agent surface (`/agent plate`) with bundled MCP server configuration

## Quick Start

### As a `gh` extension (v1 baseline)

```sh
gh extension install akasper/plate_core
gh plate health                   # PLATE health check for the current repo
gh plate health --repo akasper/plate_core --json
gh plate epic status --repo akasper/plate_core --json
gh plate features --repo akasper/plate_core --json
gh plate agents list --json
gh plate agents show research-agent --json
gh plate skills list --json
gh plate skills show crud-projects --json
gh plate bootstrap --repo akasper/plate_core --json     # dry-run plan
gh plate bootstrap --repo akasper/plate_core --apply    # apply supported steps
gh plate pr babysit 112 --repo akasper/plate --json
```

### As an MCP server in Copilot CLI (v1 baseline)

```sh
# In your Copilot CLI session:
/mcp connect /absolute/path/to/plate_core/plate-mcp
# Then call tools: plate_health, plate_epic_status, plate_features, plate_bootstrap, plate_plan_epic, plate_pr_babysit, plate_resolve_review_thread, plate_agents, plate_agent, plate_skills, plate_skill
```

### As a Copilot CLI plugin

```sh
# Install plugin from this repository
copilot plugin install akasper/plate_core

# In a new Copilot CLI session, invoke the plate agent
/agent plate
```

If you specifically want the dedicated plugin surface directory, this equivalent command also works:

```sh
copilot plugin install akasper/plate_core:plugin
```

## Playwright E2E Testing

`plate_core` includes tools for scaffolding, validating, and managing Playwright E2E tests:

### MCP Tools

- **`init_playwright`** — Initialize Playwright E2E setup in a repository
  ```sh
  # Copy config, test specs, and recording scripts from plate_template
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
CURRENT.md......................... ✅ ENABLED
Baseline Agents Catalog........... ✅ ENABLED
Playwright E2E Testing............. ✅ ENABLED
```

## Runtime layout (v1 baseline)

```text
plate_core/
├── .plugin/               # root plugin discovery manifest + agent + MCP config
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

1. Fetch upstream template updates (`git fetch upstream`) and review diffs for `AGENTS.md`, `.agentic/skills.yml`, `CURRENT.md`, and workflows in `.github/workflows/` that contain `PLATES-CORE` markers.
2. Import only upstream-owned `PLATES-CORE` sections into your customized files.
3. Preserve local sections outside those markers.
4. Open an atomic PR with the correct PR type label and issue linkage (`Closes #N` when applicable).
5. Update your `CURRENT.md` entry with imported behavior and evidence.
6. Run required checks before merge.

This keeps downstream repos aligned with new core PLATE behavior without erasing project-specific policy.
<!-- PLATES-CORE:END keeping-your-fork-current -->
