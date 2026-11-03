# plate-mcp tool profiles

The `plate-mcp` stdio server exposes a large set of PLATE tools. **Tool profiles** limit what appears in `tools/list` (and what `tools/call` accepts after the server starts) so hosts pay a smaller schema cost by default.

CLI commands (`gh plate …`) are unchanged; only the MCP server process is affected.

## Default behavior

When no profile is configured, plate-mcp uses the **`default`** profile: a lean set (~20 tools) covering everyday agent work:

| Profile | Purpose |
|---|---|
| `issue` | Repository health, epic status, feature detection |
| `task` | Human-only Task issue helpers |
| `review` | PR babysit, merge gates, `plate_pr_verify`, review-thread helpers |
| `delegation` | Baseline agents, skills, context map, `plate_delegate_to_agent` |
| `process` | `plate_what_next`, `plate_feed` |

`default` is an alias for enabling all of the profiles above together.

## Opt-in profiles

Enable additional surfaces by name (comma-separated). Each tool belongs to one or more profiles; enabling a profile adds its tools to discovery and dispatch.

| Profile | Examples |
|---|---|
| `planning` | Epic planning, interactive planning, ER planning |
| `qanda` | Curiosity Q&A, contemplation, blocking questions |
| `release` | Release status, cut/repair/cleanup, release notes |
| `adoption` | Bootstrap, self-migrate, import-payload |
| `config` | `.plate` config and git hooks |
| `e2e` | Playwright init / validate / record GIF |
| `artifacts` | Design/research proposal workflow |
| `pm` | Project Manager orchestrator |
| `fleet` | Fleet handoffs and budget |
| `monitor` | Discussions / market monitoring |
| `stubs` | Stub authoring and refinement |
| `bug_loop` / `feature_loop` | Automated bug/feature loops |
| `design` | Design contract validation |
| `release_media` / `feature_media` | Release and feature media |
| `hybrid` | Non-code / hybrid project kinds |
| `packaging` | Marketplace packaging |
| `scheduled_ops` | Scheduled operations |
| `collab` | Driver / ownership collaboration |
| `ledger` | Decision ledger + spend intervals (#1352) |
| `autonomy` | Autonomy engine, checkpoints, procedures |
| `migrate` | Migration planner/apply, docs namespace |
| `audit` | SPEC audit, information audit |
| `discussions` | GitHub Discussions helpers |
| `costs` | Token/cost reporting + spend attribution (`spend_report`, `run_cost` on `plate_costs`) |
| `all` | Every registered MCP tool (explicit full catalog) |

## Configuration

**Environment variable** (recommended for `.mcp.json` / host config):

```bash
export PLATE_MCP_TOOL_PROFILES=default,release,qanda
plate-mcp
```

**Server argument** (overrides the environment when both are set):

```bash
plate-mcp --tool-profiles=default,pm,fleet
# alias:
plate-mcp --mcp-tool-profiles=all
```

Use `all` when you need the full historical tool list (for example parity with pre-#1331 behavior or exhaustive integration tests).

## Task specs and crews

Future task specs (Epic #1327) can reference profile names in an allow-list (for example `tool_allow_profiles: [review, delegation]`) instead of enumerating dozens of tool names. Profile membership is defined in `src/plate_core/mcp/tool_profiles.py` (`profiles_for_tool`).

## Wiring in the plugin

Example `.mcp.json` fragment with optional profiles:

```json
{
  "mcpServers": {
    "plate-core": {
      "command": "plate-mcp",
      "env": {
        "PLATE_MCP_TOOL_PROFILES": "default,release,qanda"
      }
    }
  }
}
```

Leave `env` unset to keep the lean default.

## PR verify (#1365)

`gh plate pr verify <N>` and MCP `plate_pr_verify` run read-only mechanical pre-merge checks: base branch `main`, PR type and Feature gates (area label, release fragment under `.agentic/releases/unreleased/` or `epic-<NNN>-<slug>/`), milestone, closing keyword, base sync (compare `behind_by == 0`), required CI (latest run per check name, legacy statuses paginated, both check+status must pass when names collide), and paginated unresolved review threads. Exit code 0 only when all checks pass; use `--json` for agents. Optional `--run-tests` / `run_tests=true` runs `PYTHONPATH=src python3 -m unittest discover -s tests` via `run_hidden` and warns when the count looks like a stale base (~1215). This command never merges.

## Spend ledger (#1352)

Record per-run spend with `plate_ledger_record_spend` (optional token fields, routing inputs, outcome). Attribute with `plate_costs` and `spend_report=true`, or compute one run via `run_cost=true` plus `run_id` or `cloud_agent_id`. Jev shadow scores (no routing): `plate_ledger_record_jev` or optional `jev_*` on `plate_ledger_record_spend`; CLI `gh plate ledger --record-jev-score …`. CLI: `gh plate ledger --record-spend …`, `gh plate costs --spend-report`, `gh plate costs --run-cost --run-id …`.

## PR evidence packet (#1364)

Use `plate_pr_packet` (or `gh plate pr-packet <N>`) once at the start of a feedback or babysit turn instead of re-reading every review thread and CI log. The JSON includes unresolved/outdated/addressed thread summaries, failing-check log excerpts (check-run output, with GitHub Actions job logs as fallback), PR facts (base, head SHA, behind-by, labels, milestone, `Closes` links), and probe metadata from the same ETag/`since` helpers as babysit watch. Packet checkpoints persist under a separate `.packet-probe.json` file so pr-packet does not advance babysit watch state. Review threads are paginated; when pagination stops early the packet may set `review_threads_complete: false`. Size limits apply to the same indented JSON the CLI and MCP emit (`byte_size` matches that UTF-8 length).

Agent flow:

1. Call `plate_pr_packet` with `pr_number` (and `repo` when not in a clone).
2. Act only on threads whose `state` is `unresolved`; treat `outdated`/`addressed` per address-pr-feedback done gate.
3. For failing checks, use the included `log_excerpt` before any broad local test run (CI diagnosis first).
4. During crew measurement, pass `turns` and set `record_ledger=true` so `handoff_packet_size` lands in the spend ledger for before/after comparisons.

## Related design

- Agent/skill discovery tools: `docs/design/mcp-agent-skill-tool-surface.md`
- Q&A MCP surfaces: `docs/design/qanda-mcp-cli-surfaces.md`
