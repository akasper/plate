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
- **Feature detection** — optional PLATE capability detection via `gh plate features`
- **MCP tools** — `plate_health` and `plate_epic_status` return structured payloads via MCP content
- **Copilot plugin** — installable agent surface (`/agent plate`) with bundled MCP server configuration

## Quick Start

### As a `gh` extension (v1 baseline)

```sh
gh extension install akasper/plate_core
gh plate health                   # PLATE health check for the current repo
gh plate health --repo akasper/plate_core --json
gh plate epic status --repo akasper/plate_core --json
gh plate features --repo akasper/plate_core --json
```

### As an MCP server in Copilot CLI (v1 baseline)

```sh
# In your Copilot CLI session:
/mcp connect /absolute/path/to/plate_core/plate-mcp
# Then call tools: plate_health, plate_epic_status
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

## Runtime layout (v1 baseline)

```text
plate_core/
├── .plugin/               # root plugin discovery manifest + agent + MCP config
├── plugin/                # plugin source surface (mirrors .plugin metadata)
├── src/plate_core/
│   ├── github_client.py   # gh api wrapper
│   ├── health.py          # shared health logic
│   ├── cli.py             # shared CLI command handlers
│   └── mcp_server.py      # MCP stdio server (plate_health)
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
