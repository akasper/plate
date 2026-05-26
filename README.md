# plate_core

**plate_core** is the shared library powering the [PLATE](https://github.com/akasper/plate_template) platform tooling. It is designed to be deployed in three forms:

| Surface | Target User | How to Install |
|---|---|---|
| `gh plate` extension | Humans and scripts — terminal PLATE health checks | `gh extension install akasper/plate_core` |
| `plate-mcp` MCP server | AI agents — first-class tool calls via `/mcp` in Copilot CLI | `./plate-mcp` (repo clone) |
| Copilot CLI plugin | Interactive Copilot CLI sessions — conversational `/agent plate` workflow | `copilot plugin install akasper/plate_core` |

All surfaces are backed by the same `plate_core` library, ensuring consistent behavior regardless of how you access PLATE platform features.

## What It Does

`plate_core` surfaces the live state of a PLATE project by querying the GitHub API and applying PLATE methodology rules:

- **Health check** — label coverage, branch protection status, open Epic count
- **MCP tool** — `plate_health` returns structured JSON-like payload via MCP content
- **Copilot plugin** — installable no-op plugin foundation with `/agent plate`

## Quick Start

### As a `gh` extension (v1 baseline)

```sh
gh extension install /path/to/plate_core
gh plate health                   # PLATE health check for the current repo
gh plate health --repo akasper/plate_core --json
```

### As an MCP server in Copilot CLI (v1 baseline)

```sh
# In your Copilot CLI session:
/mcp connect /absolute/path/to/plate_core/plate-mcp
# Then call tool: plate_health
```

### As a Copilot CLI plugin (Epic 1 scaffold)

```sh
# Install plugin from this repository
copilot plugin install akasper/plate_core

# In a new Copilot CLI session, invoke the no-op foundation agent
/agent plate
```

Expected Epic 1 behavior: the `plate` agent confirms plugin installation and returns a deterministic no-op baseline message.

If you specifically want the dedicated plugin surface directory, this equivalent command also works:

```sh
copilot plugin install akasper/plate_core:plugin
```

## Runtime layout (v1)

```text
plate_core/
├── src/plate_core/
│   ├── github_client.py   # gh api wrapper
│   ├── health.py          # shared health logic
│   ├── cli.py             # shared CLI command handlers
│   └── mcp_server.py      # minimal MCP stdio server
├── gh-plate               # gh extension entrypoint
└── plate-mcp              # MCP server entrypoint
```

## Architecture

```
plate_core/           ← shared library (business logic + GitHub API queries)
├── cmd/              ← gh extension entry point (gh plate)
│   └── plate/        ← TUI commands using gum/Charm
├── mcp/              ← MCP server entry point (plate-mcp)
│   └── server/       ← tool definitions exposed to AI agents
├── plugin/           ← Copilot CLI plugin surface (`/agent plate`, skills, .mcp.json wiring)
└── pkg/              ← core library packages
    ├── github/       ← GitHub API client wrappers
    ├── health/       ← health check logic
    ├── epic/         ← epic state queries
    └── features/     ← optional feature detection
```

> **Note:** The implementation stack is under active research. See the [Research issue](../../issues) for language/runtime selection.

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
