# Research: plate_core Stack Selection

- **Issue:** #5
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Complete — awaiting human stack decision

## Research Question

What implementation stack best fits `plate_core`, given that one shared codebase must support:

1. a `gh plate` GitHub CLI extension,
2. a `plate-mcp` MCP server, and
3. a Copilot CLI plugin that bundles `plate.agent.md`, skills, and `.mcp.json` wiring?

## Executive Summary

This issue should close with research, not an autonomous product decision. The human decision is still required.

That said, **TypeScript is the strongest default recommendation to evaluate first** if the project optimizes for:

- official MCP SDK support,
- strongest official GitHub SDK support,
- easiest code sharing between MCP tools and CLI logic, and
- best alignment with the Copilot plugin ecosystem.

**Go remains the strongest alternative** if the team decides that **single-binary, zero-runtime distribution** outweighs SDK alignment and packaging convenience.

**Python is the weakest fit** for this repository's three-surface requirement. It is productive for MCP work, but it is the least attractive option for a `gh` extension and the weakest option for single-binary distribution.

### Key findings

1. **The Copilot CLI plugin layer is mostly declarative.** `plugin.json`, `agents/*.agent.md`, `skills/`, and `.mcp.json` do not require a language runtime by themselves. The runtime-sensitive components are the `gh` surface and the MCP server.
2. **The original Go MCP concern is now outdated.** The MCP project now publishes an **official Tier 1 Go SDK**. `mark3labs/mcp-go` is still a credible alternative, but lack of an official Go SDK is no longer the main reason to avoid Go.
3. **TypeScript has the strongest official toolchain story.** It has the strongest GitHub SDK story (`octokit`) and a first-class official MCP SDK, which makes shared schemas and typed tool contracts straightforward.
4. **Go has the strongest packaging story.** If the team wants one release pipeline that emits native binaries for `gh plate` and `plate-mcp`, Go is simpler than TypeScript or Python.
5. **The `gh` extension repo naming constraint matters.** GitHub's extension docs require a published extension repository to be named `gh-<name>`. That means `gh extension install akasper/plate_core` is not the documented shape unless the repo is renamed or a thin `gh-plate` wrapper repo is introduced.
6. **`plate.agent.md` does not get special MCP wiring beyond normal tool rules.** Plugin MCP servers become available to chat when the plugin is installed. If an agent omits `tools`, it gets all available tools, including plugin MCP tools. If an agent specifies `tools`, it must explicitly include the MCP tools or `server/*`.

## Decision Criteria

The evaluation below uses the criteria from Issue #5:

1. `gh` CLI extension compatibility
2. MCP server implementation maturity
3. Copilot CLI plugin compatibility
4. Single-repo code sharing across all three surfaces
5. Distribution packaging
6. Official GitHub SDK support
7. Community maturity and long-term maintainability

## Comparison Table

| Criterion | Go | TypeScript | Python |
|---|---|---|---|
| `gh` extension support | **Best** for precompiled extensions; GitHub docs scaffold Go directly with `gh extension create --precompiled=go` | Supported, but either requires Node at runtime or extra binary packaging work | Supported only if Python is present, unless bundled separately |
| MCP SDK maturity | **Now strong**; official Tier 1 Go SDK exists, plus mature third-party options | **Strongest**; official SDK, rich examples, best ecosystem momentum | Strong; official Tier 1 SDK and excellent developer ergonomics |
| Copilot plugin / agent fit | Good; plugin itself is runtime-neutral, MCP binary fits `.mcp.json` well | **Best** fit with plugin ecosystem; plugin stays declarative while MCP runtime uses official TS SDK | Good for MCP, but less compelling for the `gh` surface |
| Single-repo multi-surface sharing | Good shared packages and subcommands; weaker schema ergonomics than TS | **Best** for shared types, schemas, validation, and JSON-shaped tool contracts | Acceptable, but weaker than TS for shared types and weaker than Go for distribution |
| Distribution | **Best** single-binary story | Good npm story, weaker binary story | Weakest; interpreter or large bundled binaries |
| Official GitHub SDK support | Mixed: `go-gh` is official for extensions, but REST/GraphQL clients are mostly community-maintained | **Strongest**; official `octokit` family is TypeScript-first and fully typed | Weakest official story; relies mostly on community libraries like PyGithub |
| TUI / CLI ecosystem | **Excellent**; Bubble Tea / Charm ecosystem is a major advantage | Good; Ink, oclif, commander, clack | Good; Rich/Textual, but runtime cost remains |
| Overall fit for `plate_core` | Strong candidate when binary UX is the top priority | **Leading candidate** for balanced multi-surface development | Least recommended |

## Surface-by-Surface Assessment

### `gh plate` GitHub CLI extension

GitHub CLI extensions can be implemented either as:

- an executable script at the repository root, or
- precompiled binaries attached to releases.

GitHub's own documentation is notably Go-first for precompiled extensions: `gh extension create --precompiled=go` generates Go scaffolding directly, while non-Go compiled stacks use the more generic `--precompiled=other` path.

#### Go

- Best fit for a native-feeling `gh` extension.
- Simplest path to cross-platform binaries.
- `go-gh` is an official helper library that follows `gh` conventions for auth, repo detection, terminal behavior, and API access.
- Excellent option if `gh plate` should feel like a first-class CLI product.

#### TypeScript

- Works, but there are two packaging modes and both have tradeoffs:
  - **interpreted**: thin shell wrapper that calls Node/`npx` (simpler, but needs Node), or
  - **precompiled**: bundle to native executables (better UX, but more release complexity).
- This is a reasonable choice if MCP + plugin alignment is more important than zero-runtime install.

#### Python

- Technically possible, but least attractive.
- A Python-based extension either requires Python in PATH or a packaged binary.
- That makes the install story worse for the human-facing `gh` surface.

### `plate-mcp` MCP server

#### Go

Go is no longer blocked by the absence of an official SDK. The MCP project now lists Go as a **Tier 1 official SDK**. This meaningfully improves Go's viability for `plate-mcp`.

Go still has two caveats versus TypeScript:

1. most Copilot/MCP examples in the broader ecosystem still skew TypeScript-first, and
2. schema-heavy tool design is a little more ergonomic in TypeScript.

Historical note: the original issue text called out `mark3labs/mcp-go` because there was not yet an official Go SDK. That concern is now stale, though `mark3labs/mcp-go` remains a credible alternative.

#### TypeScript

TypeScript remains the easiest MCP stack to justify:

- official SDK,
- strong examples,
- direct schema definitions,
- straightforward JSON-shaped input/output types,
- easy sharing with Octokit-based GitHub integrations.

This is the smoothest path if `plate-mcp` is expected to be the technical center of gravity for the project.

#### Python

Python is also strong for MCP specifically:

- official SDK,
- fast iteration,
- good ergonomics,
- easy local development with `uv`.

The problem is not MCP itself; the problem is that the **other two surfaces** make Python less compelling as the repository-wide default.

### Copilot CLI plugin (`plugin/`)

The plugin layer itself does **not** force the language decision. It is mostly metadata and prompt assets:

- `plugin.json`
- `agents/*.agent.md`
- `skills/*/SKILL.md`
- `.mcp.json`

The only runtime-dependent part is whatever `.mcp.json` launches.

#### Important answer to the open question: MCP tool access from `plate.agent.md`

Current GitHub/Copilot docs imply the following model:

- Plugin MCP servers are loaded into Copilot CLI when the plugin is installed.
- Custom agents can use MCP tools through the normal `tools` filtering rules.
- If the agent **omits** `tools`, it gets **all available tools**, which includes MCP tools.
- If the agent **defines** `tools`, it must include either explicit MCP tools (`server/tool`) or a wildcard (`server/*`).

So the answer is **effectively yes, but with an important caveat**: plugin MCP tools become available automatically at the plugin level, but agent-level tool filtering still applies.

## Official GitHub SDK Support

### TypeScript

This is the strongest option for GitHub API work:

- `octokit` is the official, comprehensive, typed GitHub SDK.
- It covers REST, GraphQL, authentication, apps, webhooks, and best-practice middleware.
- It is the cleanest match for a shared core package that needs GitHub reads/writes.

### Go

Go has a split story:

- `go-gh` is official and helpful for extension authoring.
- `go-github` is widely used for REST, but it is community-maintained rather than GitHub-maintained.
- GraphQL commonly relies on community libraries.

That is still workable, but it is not as strong or unified as TypeScript.

### Python

Python has the weakest official support story in this comparison:

- no Octokit-equivalent official SDK family,
- common usage depends on community libraries such as PyGithub,
- still workable, but not ideal for a platform-centric repository.

## Language-by-Language Evaluation

### Option A — Go

#### Strengths

- Best native binary distribution story
- Best `gh` extension UX
- Strong TUI ecosystem (Bubble Tea / Charm)
- Good fit if `gh plate` and `plate-mcp` should share one compiled codebase
- Official Tier 1 MCP Go SDK now exists

#### Weaknesses

- Official GitHub SDK story is weaker than TypeScript
- Fewer first-party ecosystem examples for Copilot/MCP integrations
- Shared schemas and JSON contracts are more manual than in TypeScript

#### Best case for choosing Go

Choose Go if the project decides that **installer simplicity and native binaries are the primary product requirement**, especially for `gh plate`.

### Option B — TypeScript / Node.js

#### Strengths

- Best official GitHub SDK support (`octokit`)
- Strongest official MCP SDK support and ecosystem examples
- Easiest schema reuse across CLI, MCP, and shared domain logic
- Best fit for a monorepo with shared types and validation
- Plugin layer stays declarative, so Node is only needed for runtime surfaces

#### Weaknesses

- Native-binary packaging is extra work
- Interpreted `gh` extension mode requires Node in the user's environment
- Terminal UI ecosystem is good, but not as polished for native-feeling tools as Go's ecosystem

#### Best case for choosing TypeScript

Choose TypeScript if the project decides that **shared business logic, shared schemas, official SDKs, and fastest path to the MCP/plugin surface** matter more than zero-runtime packaging.

### Option C — Python

#### Strengths

- Strong MCP developer ergonomics
- Great scripting speed and AI-adjacent ecosystem
- Good local tooling with `uv`, Rich, and Textual

#### Weaknesses

- Weakest `gh` extension story
- Weakest binary packaging story
- Weakest official GitHub SDK story
- Least attractive single-language answer for all three surfaces together

#### Best case for choosing Python

Choose Python only if the team already has a strong Python bias and is willing to accept a worse human CLI packaging story.

## Recommendation

### Recommended default candidate for human approval: TypeScript

If the team wants one stack that is the **best overall compromise** across all three surfaces, **TypeScript is the leading candidate**.

Why:

1. It has the strongest official SDK support across both GitHub and MCP.
2. It makes shared types, schemas, and tool contracts easiest.
3. It aligns naturally with the Copilot plugin surface, where the plugin itself is declarative and the runtime-heavy piece is the MCP server.
4. It keeps the path open to either:
   - a Node-based `gh` extension with a thin wrapper, or
   - a later binary-packaging step if zero-runtime UX becomes mandatory.

### Important non-decision language

This is still **not** an autonomous product decision. The human decision should explicitly confirm one of these priorities:

- **TypeScript** if the priority is SDK alignment and shared schemas
- **Go** if the priority is zero-runtime binary distribution

## Recommended Repository Layout if TypeScript Is Chosen

```text
plate_core/
├── plugin/
│   ├── plugin.json
│   ├── agents/
│   │   └── plate.agent.md
│   ├── skills/
│   └── .mcp.json
├── packages/
│   ├── core/          # shared domain logic, config loading, GitHub adapters, schemas
│   ├── plate-mcp/     # MCP server entrypoint
│   └── gh-plate/      # gh-facing CLI/TUI entrypoint
├── scripts/
│   └── gh-plate       # thin local/dev launcher if interpreted extension mode is used
└── docs/
    └── research/
        └── stack-selection.md
```

Notes:

- `packages/core` should own business rules and GitHub API abstractions.
- `packages/plate-mcp` should expose the MCP tools and import from `core`.
- `packages/gh-plate` should import from `core` and call the same services as MCP tools where practical.
- If the repository keeps the name `plate_core`, the published `gh` extension may still need a separate `gh-plate` wrapper repository or a repo rename, because GitHub extension install/discovery expects a `gh-` repo name.

## Open Questions That Still Remain

1. **Repository topology for the `gh` surface**
   - Should the monorepo itself be renamed to `gh-plate`?
   - Or should `plate_core` stay the implementation repo while a tiny `gh-plate` repo wraps/releases the CLI surface?

2. **Binary requirement strictness**
   - Is “single native binary” a hard requirement for `gh plate`, or merely preferred?
   - The answer drives TypeScript vs Go more than the MCP SDK question now does.

3. **Plugin smoke-test behavior**
   - The docs answer the tool-wiring model, but an end-to-end local smoke test is still worthwhile to confirm Windows/macOS behavior for `.mcp.json` + `plate.agent.md` + `tools` filtering.

4. **Distribution split**
   - Should `plate-mcp` ship as an npm package / local command, while `gh plate` ships separately as release binaries?
   - Or should both surfaces be released together from one artifact pipeline?

## Recommended Next Steps

1. **Make the human decision explicitly between TypeScript and Go.**
   - Use TypeScript if the project optimizes for SDK alignment and shared schemas.
   - Use Go if it optimizes for single-binary UX.

2. **Open a follow-up Design issue for release topology.**
   - Decide whether `gh plate` lives in this repo name, a renamed repo, or a thin wrapper repo.

3. **Run one thin packaging spike before implementation begins.**
   - Validate the `gh` extension install path.
   - Validate plugin `.mcp.json` launch behavior.
   - Validate the intended packaging command on Windows and macOS.

4. **If TypeScript is selected, use a workspace/monorepo layout immediately.**
   - Put shared schemas in `packages/core` first to avoid duplication between CLI and MCP.

## Sources

- [Creating GitHub CLI extensions — GitHub Docs](https://docs.github.com/en/github-cli/github-cli/creating-github-cli-extensions)
- [Using GitHub CLI extensions — GitHub Docs](https://docs.github.com/en/github-cli/github-cli/using-github-cli-extensions)
- [SDKs — Model Context Protocol](https://modelcontextprotocol.io/docs/sdk)
- [MCP TypeScript SDK docs](https://ts.sdk.modelcontextprotocol.io)
- [MCP Python SDK docs](https://py.sdk.modelcontextprotocol.io)
- [MCP Go SDK docs](https://go.sdk.modelcontextprotocol.io)
- [MCP Go SDK package docs](https://pkg.go.dev/github.com/modelcontextprotocol/go-sdk)
- [go-gh — GitHub CLI helper library](https://github.com/cli/go-gh)
- [Octokit.js](https://github.com/octokit/octokit.js)
- [go-github](https://github.com/google/go-github)
- [PyGithub](https://github.com/PyGithub/PyGithub)
- [About plugins for GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins)
- [Creating a plugin for GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [GitHub Copilot CLI plugin reference — GitHub Docs](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
- [Custom agents configuration — GitHub Docs](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Creating custom agents for Copilot cloud agent — GitHub Docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents)
- [Custom agents in VS Code](https://code.visualstudio.com/docs/copilot/customization/custom-agents)
- [Agent plugins in VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-plugins)
