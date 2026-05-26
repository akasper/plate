---
spec_version: "0.1"
process_version: "PLATE 0.6"
owner: "akasper"
updated_at: "2026-05-26"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is human-owned and agent-assisted. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change.

## Vision

`gh-plate` is a GitHub CLI extension that provides tooling for PLATE (Process Lifecycle Agentic Task Engine) based project workflows. It extends the `gh` command with subcommands for managing PLATE artifacts, labels, issue types, and agentic workflows directly from the terminal.

The extension is invoked as `gh plate <subcommand>` and is distributed as a precompiled binary for Linux, macOS, and Windows (amd64 and arm64).

## Users and Personas

| Persona | Need | Success Signal |
|---|---|---|
| Developer / agent operator | Run PLATE workflow commands from the terminal without switching to the GitHub web UI | `gh plate` subcommands complete successfully and produce traceable artifacts |
| Repository maintainer | Bootstrap, audit, and maintain PLATE process metadata (labels, issues, CURRENT.md) programmatically | Repeatable, scriptable commands that can be wired into CI or agent sessions |

## Goals

| Goal | Rationale | Traceability |
|---|---|---|
| Provide a working `gh` extension skeleton | Establish the project foundation (binary entry point, cobra command tree, CI build, goreleaser distribution) | PR #1 |
| Expose PLATE workflow automation via subcommands | Reduce toil for agents and maintainers managing PLATE artifacts | Future Feature issues |

## Non-Goals

| Non-Goal | Reason |
|---|---|
| Replace the GitHub web UI | The extension augments the CLI experience; it does not replicate GitHub's full feature set. |
| Manage GitHub Actions workflows directly | Workflow authoring remains a human responsibility; the extension may inspect but not rewrite workflow files. |

## Target Workflows

| Workflow | Desired Behavior | Evidence Expected When Implemented |
|---|---|---|
| `gh plate` (root) | Print usage and list available subcommands | Binary builds, `go test ./...` passes, manual `gh extension install .` verification |
| Cross-platform distribution | Release binaries for Linux/macOS/Windows (amd64, arm64) via goreleaser | `.goreleaser.yml`, release workflow, uploaded release assets |

## Constraints

- The binary must be named `gh-plate` so that `gh extension install` recognizes it.
- The Go module path must match the GitHub repository (`github.com/akasper/gh_plate`).
- All subcommands must be implemented under the `cmd/` package using [cobra](https://github.com/spf13/cobra).
- CI must build and test the Go code on every PR.
- No credentials or tokens may be embedded in source or configuration files.

## Public Claims

| Claim | Status | Evidence |
|---|---|---|
| `gh plate` extension skeleton exists and builds | Implemented | `main.go`, `cmd/root.go`, `go.mod`, CI build step |

## Open Questions

| Question | Owner | Needed By | Resolution Path |
|---|---|---|---|
| Which PLATE subcommands should be prioritized? | akasper | After skeleton lands | Feature issues on the `gh-plate` Epic |

## External Integrations

When this project integrates with external APIs, third-party services, or data sources, each integration must be catalogued here **before implementation begins**. This prevents naming ambiguities, unrealistic capability assumptions, and blocked implementation work discovered mid-sprint.

| Integration | Provider | API Type | Required Credentials | Where to Get Access | Known Constraints / Blockers |
|---|---|---|---|---|---|
| GitHub REST / GraphQL API | GitHub | REST + GraphQL | `GITHUB_TOKEN` (standard `gh` auth) | Provided automatically by `gh` auth context | Rate limits apply; no PAT required for standard operations |

> **Agent instruction:** Before opening any Feature issue that depends on an external API, verify the integration entry above is complete and the API is reachable. If API availability is uncertain, open a Research issue first.
