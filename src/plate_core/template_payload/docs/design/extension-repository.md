# PLATE Extension Repository Model — Design Spec

- **Issue:** #33
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Draft

## Problem

PLATE needs a portable way to package optional capabilities that are too opinionated to hard-code into the base template. Examples include market-research workflows, deployment infrastructure, observability, billing integrations, domain-specific agents, and repo-specific MCP tool wiring. Today, `.agentic/extensions.yml` only lists extensions that ship inside the template; it does not define how a project discovers, trusts, imports, upgrades, or removes extensions from outside the repository.

## Constraints

- PLATE extensions must remain inspectable in Git, not hidden behind opaque hosted configuration.
- The import path must work for both fully human-reviewed repositories and autopilot-friendly agent workflows.
- Extension metadata should be simple enough to author by hand, but structured enough for automation.
- Trust boundaries matter: imported capabilities may add workflows, MCP servers, custom agents, secrets requirements, or deployment logic.
- GitHub-native distribution is preferred because PLATE already treats GitHub as the durable system of record.
- Imported capabilities must surface clearly to agents so they know which tools and instructions are available.

## Design Decision

Adopt a **GitHub-native extension package model** with three layers:

1. **Extension package repository** — a GitHub repository (or subdirectory in a mono-repo) containing extension artifacts plus a machine-readable manifest.
2. **Project extension lock file** — a file committed into each PLATE project that records which extensions are enabled, where they came from, and what revision is trusted.
3. **Import tool** — a deterministic `gh plate extension add` command that fetches, verifies, copies, and wires the extension into the target repository.

This mirrors the strongest patterns from existing ecosystems:

| Ecosystem | Useful idea for PLATE |
|---|---|
| `pip` / `npm` | Package manifest + install command + lock/pin semantics |
| Docker / OCI registries | Registry-backed discovery and immutable digests |
| MCP servers | Capability exposure via tool definitions and scoped configuration |
| GitHub custom agents / skills | Capability surfacing through agent profiles and repo-owned instructions |

### 1. Extension package layout

Each extension ships as a Git-tracked package with a manifest at the package root:

```text
plate-observability/
  plate-extension.yml
  README.md
  .agentic/
    skills.yml
    observability.yml
  .github/
    agents/
      observability-agent.agent.md
    workflows/
      deploy-observability.yml
  docs/
    extensions/
      observability.md
  templates/
    grafana/
    alerts/
```

The package may be a standalone repo (`akasper/plate-extension-observability`) or a subdirectory inside a catalog repo (`akasper/plate-extensions//observability`).

### 2. Extension manifest format

Use YAML as the canonical authoring format, with JSON accepted as an equivalent machine representation. YAML is friendlier for humans and already fits PLATE's repo conventions.

Example `plate-extension.yml`:

```yaml
schema_version: 1
id: observability
name: Observability Baseline
version: 0.3.0
kind: capability-pack
summary: Adds incident-aware monitoring, alert routing, dashboards, and runbook scaffolding.
license: MIT
homepage: https://github.com/akasper/plate-extension-observability
owners:
  - github: akasper
compatibility:
  plate_process: ">=0.6 <0.8"
  github_features:
    - custom-agents
    - actions
surfaces:
  agents:
    - path: .github/agents/observability-agent.agent.md
  skills:
    - path: .agentic/skills.yml
      ids: [observability]
  mcp_servers:
    - id: grafana
      mode: repository-setting
      tools: [grafana/search-dashboards, grafana/get-alert]
artifacts:
  copy:
    - from: .github/agents/observability-agent.agent.md
      to: .github/agents/observability-agent.agent.md
    - from: docs/extensions/observability.md
      to: docs/extensions/observability.md
  merge:
    - path: .agentic/extensions.yml
      strategy: append-yaml-entry
    - path: .agentic/skills.yml
      strategy: append-yaml-entry
    - path: .github/copilot-instructions.md
      strategy: append-section
install:
  requires_review: true
  required_secrets:
    - COPILOT_MCP_GRAFANA_TOKEN
  post_install_steps:
    - "Add Grafana MCP configuration in repository Copilot settings."
trust:
  default_pin: commit
  allowed_update_channels: [commit, signed-tag, release]
``` 

Manifest fields should answer five questions:

| Field group | Purpose |
|---|---|
| Identity (`id`, `name`, `version`, `owners`) | What this extension is and who maintains it |
| Compatibility | Which PLATE versions and GitHub capabilities it expects |
| Surfaces | How agents will see the capability |
| Artifacts / merge strategies | Which files are copied, merged, or patched |
| Trust / install metadata | How the importer should pin, review, and update it |

### 3. Discovery mechanism

Use a **hybrid discovery model** rather than a single marketplace dependency.

#### Primary discovery: GitHub topic + manifest convention

An extension repo should carry topics such as:

- `plate-extension`
- `plate-process-0-6`
- `plate-capability-observability`
- `plate-surface-agent` / `plate-surface-mcp`

A search experience can then use GitHub's native APIs:

```bash
gh search repos --topic plate-extension --json name,owner,description,url
```

This keeps publishing lightweight and avoids requiring a central service on day one.

#### Secondary discovery: signed registry file

PLATE should also maintain an optional curated registry file, for example:

```text
https://raw.githubusercontent.com/akasper/plate_template/main/.agentic/extension-registry.yml
```

That registry would list vetted extensions, default trust policies, and compatibility notes. It behaves like Homebrew taps or a package index mirror: helpful, but not the only way to install.

#### Future discovery: marketplace UI

If the catalog grows, a GitHub Pages site or repo wiki page can render registry entries into a browsable marketplace. That should be generated from the registry file instead of becoming a separate source of truth.

### 4. Import command

The default UX should be deterministic and GitHub-native:

```bash
gh plate extension search observability
gh plate extension add akasper/plate-extension-observability --ref <commit-sha>
gh plate extension list
gh plate extension update observability --to <signed-tag>
gh plate extension remove observability
```

`gh plate extension add` should perform these steps:

1. Resolve the source repo, subdirectory, and manifest.
2. Validate compatibility against `.agentic/process.yml`.
3. Show a dry-run plan: files to copy, merge, or require manual config.
4. Require explicit confirmation when the extension adds workflows, secrets, MCP servers, or deployment changes.
5. Materialize artifacts into the repository.
6. Write a project lock entry to `.agentic/extensions.lock.yml`.
7. Open or suggest a PR summarizing imported capabilities and follow-up manual steps.

### 5. Trust model

Default to **pinned commit SHAs** for unattended or agent-driven installs.

| Reference style | Allowed? | Best use | Risk |
|---|---|---|---|
| Commit SHA | **Default** | Production imports, reproducible CI, autopilot workflows | Lowest; immutable and reviewable |
| Signed tag | Yes | Human-reviewed upgrades, semver releases | Low if signatures are verified |
| Release tag (unsigned) | Yes, with warning | Trusted publishers with lightweight release process | Mutable tag risk |
| Branch / `latest` | Manual sandbox only | Prototyping or local experimentation | Highest; non-reproducible |

Rules:

- `gh plate extension add` should require `--ref` for unattended mode.
- `--latest` should only be allowed with an explicit `--allow-floating-ref` flag.
- The lock file should record both the human-readable version and the immutable source revision.
- Extensions that install MCP servers or workflows should default `requires_review: true` and open a PR instead of writing directly to `main`.

Example lock entry:

```yaml
extensions_lock_version: 1
installed:
  - id: observability
    source: github.com/akasper/plate-extension-observability
    ref:
      type: commit
      value: 7f3a9d5c3d1e0b4e...
    manifest_version: 0.3.0
    installed_at: 2026-05-26
    surfaces:
      agents: [observability-agent]
      mcp_servers: [grafana]
      skills: [observability]
```

### 6. How extensions surface to agents

PLATE should make installed capabilities visible through explicit, repo-owned artifacts instead of hidden runtime state.

| Surface | How extension contributes | Why it matters |
|---|---|---|
| `.github/agents/*.agent.md` | Adds custom agents or specialist personas | Shows up directly in Copilot agent picker |
| `.agentic/skills.yml` | Registers skill constraints and allowed artifacts | Keeps capabilities governed and auditable |
| Repository MCP settings | Enables external tools | Makes tools callable by cloud agents |
| `.github/copilot-instructions.md` | Adds high-level usage guidance | Teaches general-purpose agents when to use the extension |
| `docs/extensions/*.md` | Documents purpose, setup, rollback, and evidence | Gives humans and reviewers traceable context |

An extension may use one or more of these surfaces. The manifest should declare them explicitly so the importer can summarize the new capability to both humans and agents.

### 7. Safe merge strategies

Blind file overwrite is too risky for PLATE repositories. Extension imports should support a limited set of merge strategies:

- `copy-if-missing`
- `append-section`
- `append-yaml-entry`
- `replace-core-block` (for files with PLATES-CORE markers)
- `manual-step-required`

If an extension cannot be installed safely with these strategies, the importer should stop and generate a patch or PR for human review instead of guessing.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Single central marketplace with no GitHub-native install path | Adds operational overhead too early and creates a second control plane outside Git. |
| Floating `latest` imports as the default | Too risky for autonomous agents; breaks reproducibility and reviewability. |
| Copy-only extensions with no manifest | Easy to start, but impossible to validate compatibility, trust, or agent surfaces automatically. |
| Remote-only hosted extensions | Conflicts with PLATE's bias toward inspectable repository artifacts and low-friction forks. |

## Artifact

### Proposed PLATE-owned files

| File | Purpose |
|---|---|
| `.agentic/extensions.yml` | Declares extensions available in the template itself |
| `.agentic/extensions.lock.yml` | Records imported extension source + pinned ref for a specific project |
| `.agentic/extension-registry.yml` | Optional curated catalog of trusted extensions |
| `docs/extensions/<id>.md` | Human-readable install and rollback documentation |

### Example install summary

```text
$ gh plate extension add akasper/plate-extension-observability --ref 7f3a9d5

Resolved extension: observability@0.3.0
Compatibility: PLATE >=0.6 <0.8 ✅
Planned changes:
  + .github/agents/observability-agent.agent.md
  + docs/extensions/observability.md
  ~ .agentic/extensions.yml (append entry)
  ~ .agentic/skills.yml (append skill)
Manual follow-up:
  - Configure Grafana MCP secret COPILOT_MCP_GRAFANA_TOKEN
  - Add repository MCP configuration for grafana/* tools
Trust mode: pinned commit 7f3a9d5 ✅
Suggested next step: open PR with label Documentation
```

## Open Questions

1. Should PLATE itself own `gh-plate`, or should the extension importer be a standalone `gh` extension repository?
2. Do we want signature verification for manifests, or is GitHub repo trust + pinned commit sufficient for v1?
3. Should extension imports be able to modify repository Copilot MCP settings automatically, or only emit instructions for humans?
4. When two extensions want to patch the same file, should PLATE support patch priorities or force manual resolution?

## Acceptance Evidence

This design is correctly implemented when a downstream PLATE repository can:

1. Discover an extension through GitHub search or a curated registry.
2. Import it with an explicit `gh plate extension add ... --ref <sha>` command.
3. See a committed lock entry recording the trusted revision.
4. Review exactly how the extension surfaces to agents (MCP tools, skills, instructions, or custom agents).
5. Upgrade or remove the extension without losing traceability.

Closes #33
