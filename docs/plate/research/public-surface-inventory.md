# Public surface inventory (PLATE 1.0)

- **Issue:** [#1056](https://github.com/akasper/plate/issues/1056)
- **Inventory date:** 2026-11-28 (UTC)
- **Code pin:** `plate_core.__version__` = **0.12.0** (`src/plate_core/__init__.py`)
- **Scope:** `akasper/plate` monorepo on branch `release-minor` at authoring time.
- **Read-only sources:** `src/plate_core/cli.py`, MCP modules, `src/plate_core/data/template_payload_inventory.json` (reference only; not edited for this artifact).

This document refines stub issue #1056 (`status:stub`, `need:refinement`). It enumerates six PLATE surface classes, classifies each entry, cites source files, and lists gaps for maintainers before a 1.0 public-surface freeze.

## Classification criteria

| Class | Meaning | How applied in this inventory |
|---|---|---|
| **stable** | Supported for adopters and agents under semver; covered by default MCP profile and/or README install examples; enforced by CI or `.agentic/process.yml`. | Default MCP profile (22 tools), adoption/release/config/issue tooling, canonical labels, `.plate` validated keys, release fragment contract. |
| **experimental** | Shipped in `plate-core` but still evolving (loops, fleet, media, planning TUIs, release-window overrides). Behavior may change across minors. | Opt-in MCP profiles, non-README CLI command families, `status:*` workflow labels, ceremony override labels. |
| **internal** | Callable from CI/tests or listed in MCP catalog without full dispatch; not part of the 1.0 adopter contract. | `pr_*_gate.py` CLIs, MCP tools in `tools/list` without `tools/call` handler, handlers not exported in `tools/list`. |

## Regeneration

Re-run these commands from the repository root after any CLI/MCP/label change:

```bash
PYTHONPATH=src python3 -c "from plate_core.cli import build_parser; print(build_parser().format_help())"
PYTHONPATH=src python3 -c "from plate_core.mcp.tool_profiles import list_mcp_tool_names; print(len(list_mcp_tool_names()))"
gh plate <command> --help   # per-command flags
```

- **CLI tree / flags:** `argparse` in `src/plate_core/cli.py` (`build_parser()`, ~L4984+). Leaf invocations: 73.
- **MCP tools:** names parsed from `src/plate_core/mcp_server.py` via `list_mcp_tool_names()` in `src/plate_core/mcp/tool_profiles.py`; schemas live inline in the `tools/list` handler (~L2218+).
- **MCP profile filter:** env `PLATE_MCP_TOOL_PROFILES` (default expands to `issue, task, review, delegation, process`).
- **Labels:** `.github/labels.yml` (synced by bootstrap/import-payload).
- **`.plate` defaults/schema:** `DEFAULT_CONFIG`, `validate_plate_config()` in `src/plate_core/plate_config.py`.
- **Release fragments:** `.agentic/releases/unreleased/README.md`.
- **`.agentic/` layout:** `.agentic/process.yml` → `artifacts:` map plus on-disk tree under `.agentic/`.

---

## 1. CLI commands and flags

**Entry:** `gh-plate` → `plate_core.cli:main` (`plate-mcp` sibling package). **Source:** `src/plate_core/cli.py`.

### 1.1 Top-level commands (46)

| Command | Class | Source |
|---|---|---|
| `adopt` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `agents` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `artifact` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `autonomy` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `bootstrap` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `bug-loop` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `checkpoint` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `ci` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `collab` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `config` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `context` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `costs` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `design-contract` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `epic` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `er-plan` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `feature-loop` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `feature-media` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `features` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `feed` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `fleet` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `health` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `hooks` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `hybrid` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `import-payload` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `ledger` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `migrate` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `migrate-docs-namespace` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `monitor` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `packaging` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `payload` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `plan` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `pm` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `pr` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `pr-packet` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `qanda` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `release` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `release-media` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `runner` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `scheduled-ops` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `self-migrate` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `skills` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `spec-audit` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `stub` | experimental | `src/plate_core/cli.py` (`build_parser`) |
| `task` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `tasks` | stable | `src/plate_core/cli.py` (`build_parser`) |
| `what-next` | stable | `src/plate_core/cli.py` (`build_parser`) |

### 1.2 Subcommand invocations (73 leaves)

| Invocation | Class | Flag prefix examples | Source |
|---|---|---|---|
| `gh plate adopt` | stable | `--apply-first-qa`, `--complete-session`, `--first-qa-plan`, `--force`, `--json`, `--no-optional`, … | `src/plate_core/cli.py` |
| `gh plate agents delegate` | stable | `--json`, `--task`, `-h` | `src/plate_core/cli.py` |
| `gh plate agents list` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate agents show` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate artifact` | experimental | `--actionable`, `--authoritative`, `--budget-remaining`, `--by`, `--content-path`, `--decide`, … | `src/plate_core/cli.py` |
| `gh plate autonomy` | stable | `--budget`, `--budget-reset`, `--budget-reset-reason`, `--dry-run`, `--estimate-tokens`, `--json`, … | `src/plate_core/cli.py` |
| `gh plate bootstrap` | stable | `--adopt`, `--apply`, `--existing-repo`, `--greenfield`, `--json`, `--local-root`, … | `src/plate_core/cli.py` |
| `gh plate bug-loop` | experimental | `--advance`, `--apply`, `--branch`, `--budget-remaining`, `--bug`, `--cancel`, … | `src/plate_core/cli.py` |
| `gh plate checkpoint` | experimental | `--action-kind`, `--by`, `--create`, `--decide`, `--decision`, `--get`, … | `src/plate_core/cli.py` |
| `gh plate ci audit` | stable | `--json`, `--limit`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate collab` | experimental | `--action`, `--author`, `--branch`, `--claim`, `--concurrent`, `--etiquette`, … | `src/plate_core/cli.py` |
| `gh plate config init` | stable | `--apply`, `--force`, `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate config show` | stable | `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate config upgrade` | stable | `--apply`, `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate config validate` | stable | `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate context list` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate context show` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate costs` | experimental | `--cloud-agent-id`, `--dashboard`, `--epic-label`, `--json`, `--ledger-base-dir`, `--limit`, … | `src/plate_core/cli.py` |
| `gh plate design-contract` | experimental | `--budget-remaining`, `--decide`, `--decided-by`, `--decision`, `--draft`, `--feature`, … | `src/plate_core/cli.py` |
| `gh plate epic status` | stable | `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate er-plan` | experimental | `--answers-file`, `--budget-remaining`, `--by`, `--decide`, `--decision`, `--feed`, … | `src/plate_core/cli.py` |
| `gh plate feature-loop` | experimental | `--advance`, `--apply`, `--branch`, `--budget-remaining`, `--cancel`, `--design`, … | `src/plate_core/cli.py` |
| `gh plate feature-media` | experimental | `--attach`, `--budget-remaining`, `--caption`, `--decide`, `--decided-by`, `--decision`, … | `src/plate_core/cli.py` |
| `gh plate features` | stable | `--json`, `--local`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate feed` | stable | `--json`, `--limit`, `--no-autonomy`, `--no-process`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate fleet` | experimental | `--active-roles`, `--allocate`, `--apply`, `--approved`, `--budget-remaining`, `--budget-tokens`, … | `src/plate_core/cli.py` |
| `gh plate health` | stable | `--json`, `--no-spec-audit`, `--repo`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate hooks install` | stable | `--force`, `--hook`, `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate hooks run` | stable | `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate hooks status` | stable | `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate hybrid` | experimental | `--base-dir`, `--contract`, `--detect`, `--feed`, `--json`, `--kind`, … | `src/plate_core/cli.py` |
| `gh plate import-payload` | stable | `--apply`, `--dry-run`, `--escape-hatch`, `--escape-hatch-on-conflict`, `--json`, `--namespace-docs`, … | `src/plate_core/cli.py` |
| `gh plate ledger` | experimental | `--action-kind`, `--by`, `--cache-write-tokens`, `--cached-read-tokens`, `--checkpoint-id`, `--cloud-agent-id`, … | `src/plate_core/cli.py` |
| `gh plate migrate apply` | stable | `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate migrate plan` | stable | `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate migrate-docs-namespace` | experimental | `--apply`, `--json`, `--target-dir`, `-h` | `src/plate_core/cli.py` |
| `gh plate monitor` | experimental | `--apply`, `--budget-remaining`, `--created-issue`, `--decide`, `--decision`, `--detail`, … | `src/plate_core/cli.py` |
| `gh plate packaging` | experimental | `--base-dir`, `--budget-remaining`, `--decide`, `--decided-by`, `--decision`, `--feed`, … | `src/plate_core/cli.py` |
| `gh plate payload classify` | stable | `--json`, `--template-repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate payload list` | stable | `--include-excluded`, `--json`, `--template-repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate payload manifest` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate payload root` | stable | `--json`, `--template-repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate plan` | experimental | `--actionable`, `--answers-file`, `--budget-remaining`, `--build-file`, `--by`, `--decide`, … | `src/plate_core/cli.py` |
| `gh plate pm` | stable | `--apply`, `--complete`, `--complete-status`, `--fetch-loop-gates`, `--json`, `--limit`, … | `src/plate_core/cli.py` |
| `gh plate pr babysit` | stable | `--act`, `--agents`, `--branch-update-strategy`, `--cap-hours`, `--full-every`, `--json`, … | `src/plate_core/cli.py` |
| `gh plate pr create` | stable | `--json`, `--repo`, `--repo-root` | `src/plate_core/cli.py` |
| `gh plate pr health` | stable | `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate pr preflight` | stable | `--base`, `--body-file`, `--json`, `--labels`, `--repo`, `--repo-root`, … | `src/plate_core/cli.py` |
| `gh plate pr verify` | stable | `--json`, `--repo`, `--repo-root`, `--run-tests`, `-h` | `src/plate_core/cli.py` |
| `gh plate pr-packet` | experimental | `--cloud-agent-id`, `--ledger-base-dir`, `--max-bytes`, `--record-ledger`, `--repo`, `--run-id`, … | `src/plate_core/cli.py` |
| `gh plate qanda` | stable | `--answer`, `--by`, `--json`, `--limit`, `--list`, `--question`, … | `src/plate_core/cli.py` |
| `gh plate release cleanup-branches` | stable | `--apply`, `--base`, `--json`, `--limit`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate release cut` | stable | `--dry-run`, `--json`, `--releases-dir`, `--version-type`, `-h` | `src/plate_core/cli.py` |
| `gh plate release finalize` | stable | `--apply`, `--dry-run`, `--force-hard-reset`, `--json`, `--releases-dir`, `-h` | `src/plate_core/cli.py` |
| `gh plate release init` | stable | `--apply`, `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate release notes` | stable | `--from`, `--json`, `--releases-dir`, `--to`, `-h` | `src/plate_core/cli.py` |
| `gh plate release repair` | stable | `--apply`, `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate release status` | stable | `--json`, `--releases-dir`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate release target-epic` | stable | `--json`, `--repo`, `-h` | `src/plate_core/cli.py` |
| `gh plate release-media` | experimental | `--approved-only`, `--decide`, `--decision`, `--feed`, `--index`, `--json`, … | `src/plate_core/cli.py` |
| `gh plate runner add` | stable | `--apply`, `--json`, `--os`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate runner doctor` | stable | `--json`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate runner remove` | stable | `--apply`, `--json`, `--repo`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate runner status` | stable | `--json`, `--repo`, `--repo-root`, `-h` | `src/plate_core/cli.py` |
| `gh plate scheduled-ops` | experimental | `--apply`, `--approved`, `--budget-remaining`, `--checkpoint-id`, `--complete`, `--complete-status`, … | `src/plate_core/cli.py` |
| `gh plate self-migrate` | stable | `--allow-high-risk`, `--allow-network`, `--apply-markers`, `--apply-pr`, `--base`, `--closes`, … | `src/plate_core/cli.py` |
| `gh plate skills list` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate skills show` | stable | `--json`, `-h` | `src/plate_core/cli.py` |
| `gh plate spec-audit` | stable | `--apply-followups`, `--followups`, `--json`, `--max-followups`, `--releases-dir`, `--repo`, … | `src/plate_core/cli.py` |
| `gh plate stub` | experimental | `--add-acceptance`, `--apply`, `--budget-remaining`, `--create`, `--dry-create`, `--feed`, … | `src/plate_core/cli.py` |
| `gh plate task` | stable | `--apply`, `--close`, `--comment`, `--context`, `--create`, `--detect`, … | `src/plate_core/cli.py` |
| `gh plate tasks validate` | stable | `--json`, `--path`, `--repo-root`, `--tasks-dir`, `-h` | `src/plate_core/cli.py` |
| `gh plate what-next` | stable | `--agent-type`, `--json`, `--no-budget`, `--no-fragments`, `--no-prs`, `--repo`, … | `src/plate_core/cli.py` |

**Flag authority:** every flag is declared on its argparse subparser in `build_parser()`. Use `gh plate <invocation> --help` for the authoritative flag list (including `pr create` / `pr preflight` `REMAINDER` forwarding to `gh pr create`).

### 1.3 Internal CLI entrypoints (not `gh plate`)

| Module | Class | Source |
|---|---|---|
| `src/plate_core/pr_gates_payload.py` | internal | CI / pr-gates workflows |
| `src/plate_core/pr_main_source_gate.py` | internal | CI / pr-gates workflows |
| `src/plate_core/pr_release_window_gate.py` | internal | CI / pr-gates workflows |
| `src/plate_core/pr_reviewer_model_gate.py` | internal | CI / pr-gates workflows |
| `src/plate_core/pr_ui_pr_image_check.py` | internal | CI / pr-gates workflows |

---

## 2. MCP tools and schemas

**Server:** `plate-mcp` → `plate_core.mcp_server:run` (stdio JSON-RPC `2024-11-05`). **Schema file:** `src/plate_core/mcp_server.py` (`tools/list` → `all_tools`). **Profiles:** `src/plate_core/mcp/tool_profiles.py`.

- **Catalog size:** 209 tools in `tools/list` when `PLATE_MCP_TOOL_PROFILES=all`.
- **Default profile:** 22 tools (`default` → issue, task, review, delegation, process).
- **Dispatch:** `src/plate_core/mcp_server.py` → `_handle_tools_call()`; Q&A tools delegate to `src/plate_core/mcp/curiosity_tools.py`; Playwright tools to `src/plate_core/mcp/tools.py`.

### 2.1 Known profiles

| Profile | Tool count | Typical class | Source |
|---|---:|---|---|
| `adoption` | 13 | stable | `tool_profiles.py` + `mcp_server.py` |
| `artifacts` | 6 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `audit` | 3 | stable | `tool_profiles.py` + `mcp_server.py` |
| `autonomy` | 10 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `bug_loop` | 8 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `collab` | 8 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `config` | 6 | stable | `tool_profiles.py` + `mcp_server.py` |
| `costs` | 1 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `delegation` | 7 | stable | `tool_profiles.py` + `mcp_server.py` |
| `design` | 8 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `discussions` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `e2e` | 3 | stable | `tool_profiles.py` + `mcp_server.py` |
| `feature_loop` | 9 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `feature_media` | 9 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `fleet` | 9 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `hybrid` | 10 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `issue` | 3 | stable | `tool_profiles.py` + `mcp_server.py` |
| `ledger` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `migrate` | 3 | stable | `tool_profiles.py` + `mcp_server.py` |
| `monitor` | 5 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `packaging` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `planning` | 16 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `pm` | 8 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `process` | 2 | stable | `tool_profiles.py` + `mcp_server.py` |
| `qanda` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `release` | 10 | stable | `tool_profiles.py` + `mcp_server.py` |
| `review` | 7 | stable | `tool_profiles.py` + `mcp_server.py` |
| `scheduled_ops` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `stubs` | 7 | experimental | `tool_profiles.py` + `mcp_server.py` |
| `task` | 3 | stable | `tool_profiles.py` + `mcp_server.py` |

### 2.2 Full tool catalog (by profile)

#### Profile `adoption`

| Tool | Class | Schema source |
|---|---|---|
| `plate_adoption_first_qa_plan` | stable | `src/plate_core/mcp_server.py` |
| `plate_adoption_session` | stable | `src/plate_core/mcp_server.py` |
| `plate_adoption_status` | stable | `src/plate_core/mcp_server.py` |
| `plate_bootstrap` | stable | `src/plate_core/mcp_server.py` |
| `plate_import_payload` | stable | `src/plate_core/mcp_server.py` |
| `plate_payload_classify` | stable | `src/plate_core/mcp_server.py` |
| `plate_payload_list` | stable | `src/plate_core/mcp_server.py` |
| `plate_payload_manifest` | stable | `src/plate_core/mcp_server.py` |
| `plate_payload_root` | stable | `src/plate_core/mcp_server.py` |
| `plate_self_migrate_merge_markers` | stable | `src/plate_core/mcp_server.py` |
| `plate_self_migrate_plan` | stable | `src/plate_core/mcp_server.py` |
| `plate_self_migrate_pr_plan` | stable | `src/plate_core/mcp_server.py` |
| `plate_self_migrate_verify` | stable | `src/plate_core/mcp_server.py` |

#### Profile `artifacts`

| Tool | Class | Schema source |
|---|---|---|
| `plate_artifact_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_artifact_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_artifact_history` | experimental | `src/plate_core/mcp_server.py` |
| `plate_artifact_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_artifact_propose` | experimental | `src/plate_core/mcp_server.py` |
| `plate_artifact_resubmit` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `audit`

| Tool | Class | Schema source |
|---|---|---|
| `plate_perform_information_audit` | internal | `src/plate_core/mcp_server.py` |
| `plate_spec_audit` | stable | `src/plate_core/mcp_server.py` |
| `plate_spec_audit_followups` | stable | `src/plate_core/mcp_server.py` |

#### Profile `autonomy`

| Tool | Class | Schema source |
|---|---|---|
| `plate_autonomy_budget` | experimental | `src/plate_core/mcp_server.py` |
| `plate_autonomy_list_procedures` | experimental | `src/plate_core/mcp_server.py` |
| `plate_autonomy_run_cycle` | experimental | `src/plate_core/mcp_server.py` |
| `plate_autonomy_run_procedure` | experimental | `src/plate_core/mcp_server.py` |
| `plate_autonomy_simulate` | experimental | `src/plate_core/mcp_server.py` |
| `plate_autonomy_status` | experimental | `src/plate_core/mcp_server.py` |
| `plate_checkpoint_create` | experimental | `src/plate_core/mcp_server.py` |
| `plate_checkpoint_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_checkpoint_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_checkpoint_list` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `bug_loop`

| Tool | Class | Schema source |
|---|---|---|
| `plate_bug_loop_advance` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_cancel` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_start` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_tick` | experimental | `src/plate_core/mcp_server.py` |
| `plate_bug_loop_update` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `collab`

| Tool | Class | Schema source |
|---|---|---|
| `plate_collab_check` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_concurrent` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_etiquette` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_issue_status` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_ownership_claim` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_ownership_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_ownership_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_collab_ownership_release` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `config`

| Tool | Class | Schema source |
|---|---|---|
| `plate_config_get` | stable | `src/plate_core/mcp_server.py` |
| `plate_config_init` | stable | `src/plate_core/mcp_server.py` |
| `plate_config_upgrade` | stable | `src/plate_core/mcp_server.py` |
| `plate_config_validate` | stable | `src/plate_core/mcp_server.py` |
| `plate_hooks_install` | stable | `src/plate_core/mcp_server.py` |
| `plate_hooks_status` | stable | `src/plate_core/mcp_server.py` |

#### Profile `costs`

| Tool | Class | Schema source |
|---|---|---|
| `plate_costs` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `delegation`

| Tool | Class | Schema source |
|---|---|---|
| `plate_agent` | stable | `src/plate_core/mcp_server.py` |
| `plate_agents` | stable | `src/plate_core/mcp_server.py` |
| `plate_context` | stable | `src/plate_core/mcp_server.py` |
| `plate_contexts` | stable | `src/plate_core/mcp_server.py` |
| `plate_delegate_to_agent` | stable | `src/plate_core/mcp_server.py` |
| `plate_skill` | stable | `src/plate_core/mcp_server.py` |
| `plate_skills` | stable | `src/plate_core/mcp_server.py` |

#### Profile `design`

| Tool | Class | Schema source |
|---|---|---|
| `plate_design_contract_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_propose` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_scaffold` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_update` | experimental | `src/plate_core/mcp_server.py` |
| `plate_design_contract_validate` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `discussions`

| Tool | Class | Schema source |
|---|---|---|
| `plate_add_discussion_comment` | internal | `src/plate_core/mcp_server.py` |
| `plate_create_discussion` | internal | `src/plate_core/mcp_server.py` |
| `plate_get_discussion` | internal | `src/plate_core/mcp_server.py` |
| `plate_list_discussion_categories` | internal | `src/plate_core/mcp_server.py` |
| `plate_list_discussion_comments` | internal | `src/plate_core/mcp_server.py` |
| `plate_list_discussions` | internal | `src/plate_core/mcp_server.py` |
| `plate_list_open_ideas` | internal | `src/plate_core/mcp_server.py` |

#### Profile `e2e`

| Tool | Class | Schema source |
|---|---|---|
| `init_playwright` | stable | `src/plate_core/mcp_server.py` |
| `record_e2e_gif` | stable | `src/plate_core/mcp_server.py` |
| `validate_e2e_tests` | stable | `src/plate_core/mcp_server.py` |

#### Profile `feature_loop`

| Tool | Class | Schema source |
|---|---|---|
| `plate_feature_loop_advance` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_cancel` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_estimate` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_start` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_tick` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_loop_update` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `feature_media`

| Tool | Class | Schema source |
|---|---|---|
| `plate_feature_media_attach_fragment` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_estimate_cost` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_plan` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_register` | experimental | `src/plate_core/mcp_server.py` |
| `plate_feature_media_skip` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `fleet`

| Tool | Class | Schema source |
|---|---|---|
| `plate_fleet_allocate` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_complete` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_handoff` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_plan` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_roles` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_status` | experimental | `src/plate_core/mcp_server.py` |
| `plate_fleet_update` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `hybrid`

| Tool | Class | Schema source |
|---|---|---|
| `plate_hybrid_contract` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_detect` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_list_artifacts` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_list_kinds` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_list_validation` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_planning_template` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_profile` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_set_kind` | experimental | `src/plate_core/mcp_server.py` |
| `plate_hybrid_validation_plan` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `issue`

| Tool | Class | Schema source |
|---|---|---|
| `plate_epic_status` | stable | `src/plate_core/mcp_server.py` |
| `plate_features` | stable | `src/plate_core/mcp_server.py` |
| `plate_health` | stable | `src/plate_core/mcp_server.py` |

#### Profile `ledger`

| Tool | Class | Schema source |
|---|---|---|
| `plate_ledger_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_query` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_record` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_record_jev` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_record_spend` | experimental | `src/plate_core/mcp_server.py` |
| `plate_ledger_summary` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `migrate`

| Tool | Class | Schema source |
|---|---|---|
| `plate_migrate_apply` | stable | `src/plate_core/mcp_server.py` |
| `plate_migrate_docs_namespace` | stable | `src/plate_core/mcp_server.py` |
| `plate_migrate_plan` | stable | `src/plate_core/mcp_server.py` |

#### Profile `monitor`

| Tool | Class | Schema source |
|---|---|---|
| `plate_monitor_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_monitor_discussions` | experimental | `src/plate_core/mcp_server.py` |
| `plate_monitor_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_monitor_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_monitor_market` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `packaging`

| Tool | Class | Schema source |
|---|---|---|
| `plate_packaging_build` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_plan` | experimental | `src/plate_core/mcp_server.py` |
| `plate_packaging_render` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `planning`

| Tool | Class | Schema source |
|---|---|---|
| `plate_er_planning_answer` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_build` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_list_pending` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_resubmit` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_script` | experimental | `src/plate_core/mcp_server.py` |
| `plate_er_planning_start` | experimental | `src/plate_core/mcp_server.py` |
| `plate_plan_epic` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_answer` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_build` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_decide` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_history` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_list_pending` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_resubmit` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_script` | experimental | `src/plate_core/mcp_server.py` |
| `plate_planning_start` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `pm`

| Tool | Class | Schema source |
|---|---|---|
| `plate_pm_assign` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_complete` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_queue` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_run_cycle` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_run_loop` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_status` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_team` | experimental | `src/plate_core/mcp_server.py` |
| `plate_pm_tick_loops` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `process`

| Tool | Class | Schema source |
|---|---|---|
| `plate_feed` | stable | `src/plate_core/mcp_server.py` |
| `plate_what_next` | stable | `src/plate_core/mcp_server.py` |

#### Profile `qanda`

| Tool | Class | Schema source |
|---|---|---|
| `plate_contemplate` | experimental | `src/plate_core/mcp_server.py` |
| `plate_create_blocking_question` | experimental | `src/plate_core/mcp_server.py` |
| `plate_get_answers` | experimental | `src/plate_core/mcp_server.py` |
| `plate_get_question` | experimental | `src/plate_core/mcp_server.py` |
| `plate_list_questions` | experimental | `src/plate_core/mcp_server.py` |
| `plate_record_answer` | experimental | `src/plate_core/mcp_server.py` |
| `plate_synthesize_priorities` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `release`

| Tool | Class | Schema source |
|---|---|---|
| `plate_release_cleanup_branches` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_media_decide` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_media_feed` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_media_manifest` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_media_render` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_media_validate_paths` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_notes` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_repair` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_status` | stable | `src/plate_core/mcp_server.py` |
| `plate_release_target_epic` | stable | `src/plate_core/mcp_server.py` |

#### Profile `review`

| Tool | Class | Schema source |
|---|---|---|
| `plate_get_actionable_review_threads` | stable | `src/plate_core/mcp_server.py` |
| `plate_get_pr_merge_gates` | stable | `src/plate_core/mcp_server.py` |
| `plate_get_unresolved_review_threads` | stable | `src/plate_core/mcp_server.py` |
| `plate_pr_babysit` | stable | `src/plate_core/mcp_server.py` |
| `plate_pr_packet` | stable | `src/plate_core/mcp_server.py` |
| `plate_pr_verify` | stable | `src/plate_core/mcp_server.py` |
| `plate_resolve_review_thread` | stable | `src/plate_core/mcp_server.py` |

#### Profile `scheduled_ops`

| Tool | Class | Schema source |
|---|---|---|
| `plate_scheduled_op_complete` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_op_plan` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_op_run` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_op_runs` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_ops_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_ops_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_scheduled_ops_status` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `stubs`

| Tool | Class | Schema source |
|---|---|---|
| `plate_stub_author` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_author_create` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_create` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_feed` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_get` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_list` | experimental | `src/plate_core/mcp_server.py` |
| `plate_stub_refine` | experimental | `src/plate_core/mcp_server.py` |

#### Profile `task`

| Tool | Class | Schema source |
|---|---|---|
| `plate_task_close` | stable | `src/plate_core/mcp_server.py` |
| `plate_task_create` | stable | `src/plate_core/mcp_server.py` |
| `plate_task_detect` | stable | `src/plate_core/mcp_server.py` |

### 2.3 MCP wiring exceptions

| Tool | Class | Notes | Source |
|---|---|---|---|
| `plate_list_discussions` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_get_discussion` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_list_discussion_comments` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_add_discussion_comment` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_create_discussion` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_list_discussion_categories` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_list_open_ideas` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_perform_information_audit` | internal | Listed in `tools/list`; no `tools/call` branch in `_handle_tools_call` | `mcp_server.py` |
| `plate_backfill_answers` | internal | Handler class exists in `curiosity_tools.py`; not in `tools/list` | `mcp/curiosity_tools.py` |
| `plate_perform_test_coverage_audit` | internal | Dispatch branch exists; not in `tools/list` | `mcp_server.py`, `mcp/audit_tools.py` |

**Related (separate server):** `services/process-docs/` exposes `list_docs`, `get_doc`, `search_docs` (`services/process-docs/src/mcp-tools.ts`) — not part of `plate-mcp`.

---

## 3. `.plate` config schema and defaults

**Authority:** `src/plate_core/plate_config.py` (`CURRENT_CONFIG_VERSION` = **1.4**). **Precedence:** defaults < built-in extension manifests < repo `.plate` file.

### 3.1 Top-level keys

| Key | Class | Source |
|---|---|---|
| `autonomy` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `extensions` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `hooks` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `methodology` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `overrides` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `platform` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `process_docs` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `release` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |
| `version` | stable | `plate_config.py` (`ALLOWED_CONFIG_TOP_LEVEL_KEYS`, strict mode) |

### 3.2 Default object (code defaults)

```json
{
  "version": "1.4",
  "methodology": {
    "epic_naming_pattern": "Epic: {name}",
    "marker_prefix": "PLATES-CORE",
    "feature_workflow": "feature/{slug}"
  },
  "extensions": {
    "enabled": true,
    "sources": [],
    "installed": {}
  },
  "overrides": {},
  "release": {
    "triggers": [],
    "default_track": null
  },
  "autonomy": {
    "enabled": true,
    "risk_tolerance": "medium",
    "pr_review_scope": "all",
    "token_budget": {
      "daily": 50000,
      "per_cycle": 8000,
      "action": "throttle"
    },
    "cost_ceiling_usd": 10.0,
    "schedules_enabled": true,
    "loop": {
      "default_sleep_seconds": 300,
      "max_cycles": null
    },
    "comment_attribution": {
      "enabled": true,
      "format": "\ud83e\udd16 {agent} on behalf of {on_behalf_of}"
    }
  },
  "platform": "posix",
  "hooks": {
    "pre_push": {
      "format": "",
      "lint": "",
      "typecheck": ""
    },
    "pre_commit": {
      "format": "",
      "lint": "",
      "typecheck": ""
    }
  },
  "process_docs": {
    "base_url": "https://plateprocess.dev",
    "mcp_url": "https://plateprocess.dev/mcp",
    "version": "v0.12.0"
  }
}
```

**Source:** `DEFAULT_CONFIG` in `src/plate_core/plate_config.py`. Validation: `validate_plate_config()` (platform enum, autonomy budgets, hooks via `git_hooks.py`, `process_docs` via `process_docs.py`).

---

## 4. Release fragment format

**Authority:** `.agentic/releases/unreleased/README.md` (also shipped in template payload).

### 4.1 Fragment file (`unreleased/<slug>.json` or `epic-*/<slug>.json`)

| Field | Required | Class | Source |
|---|---|---|---|
| `slug` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `change_type` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `surface` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `summary` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `migration_impact` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `agent_notes` | yes | stable | `.agentic/releases/unreleased/README.md` |
| `migration_guidance` | no | stable | `.agentic/releases/unreleased/README.md` |
| `breaking` | no | stable | `.agentic/releases/unreleased/README.md` |
| `links` | no | stable | `.agentic/releases/unreleased/README.md` |
| `requires` | no | stable | `.agentic/releases/unreleased/README.md` |
| `media` | no | experimental | `.agentic/releases/unreleased/README.md` |

**`change_type` values:** `feature`, `fix`, `docs`, `process`, `breaking`, `hardening` (same file).

### 4.2 Aggregated `release.json` (post-cut)

| Field | Class | Source |
|---|---|---|
| `version` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `summary` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `cut_at` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `fragment_count` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `fragment_slugs` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `entries` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `media` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `media_summary` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `media_markdown` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |
| `closes_block` | stable | `.agentic/releases/v0.12.0/release.json` (example) + `scripts/cut_release.py` |

---

## 5. `.agentic/` layouts

**Registry:** `.agentic/process.yml` → `artifacts:` lists canonical paths. **Class:** stable process metadata unless noted.

### 5.1 Root files

| Path | Class | Source |
|---|---|---|
| `.agentic/process.yml` | stable | `process.yml` / on-disk |
| `.agentic/skills.yml` | stable | `process.yml` / on-disk |
| `.agentic/extensions.yml` | stable | `process.yml` / on-disk |
| `.agentic/audit.yml` | stable | `process.yml` / on-disk |
| `.agentic/traceability.yml` | stable | `process.yml` / on-disk |
| `.agentic/marketing.yml` | stable | `process.yml` / on-disk |
| `.agentic/migration.yml` | stable | `process.yml` / on-disk |
| `.agentic/ui-paths.yml` | stable | `process.yml` / on-disk |
| `.agentic/COSTS.md` | stable | `process.yml` / on-disk |

### 5.2 Directories

| Path | Purpose | Class | Source |
|---|---|---|---|
| `.agentic/releases/` | Release fragments + versioned release.json | stable | `.agentic/process.yml`, on-disk tree |
| `.agentic/releases/unreleased/` | Pending fragments | stable | `.agentic/process.yml`, on-disk tree |
| `.agentic/releases/vX.Y.Z/` | Cut release artifacts | stable | `.agentic/process.yml`, on-disk tree |
| `.agentic/releases/epic-*/` | Epic-scoped fragments | stable | `.agentic/process.yml`, on-disk tree |
| `.agentic/adoption/` | Adoption seed JSON | stable | `.agentic/process.yml`, on-disk tree |
| `.agentic/ledger/` | Ledger README / conventions | experimental | `.agentic/process.yml`, on-disk tree |
| `.agentic/procedures/` | Autonomy procedure definitions (JSON) | experimental | `.agentic/process.yml`, on-disk tree |

### 5.3 Template payload mirror

| Path | Class | Source |
|---|---|---|
| `src/plate_core/template_payload/.agentic/*` | stable | `src/plate_core/data/template_payload_inventory.json` (inventory reference) |

---

## 6. Labels

**Authority:** `.github/labels.yml` (47 labels). Enforced by `.github/workflows/label-check.yml`. Semantic rules in `.agentic/process.yml` → `labels:`.

| Label | Class | Source |
|---|---|---|
| `Feedback Response` | stable | `.github/labels.yml` |
| `Bug` | stable | `.github/labels.yml` |
| `Feature` | stable | `.github/labels.yml` |
| `Epic` | stable | `.github/labels.yml` |
| `Documentation` | stable | `.github/labels.yml` |
| `Hardening` | stable | `.github/labels.yml` |
| `Research` | stable | `.github/labels.yml` |
| `Audit` | stable | `.github/labels.yml` |
| `Migration` | stable | `.github/labels.yml` |
| `Release` | stable | `.github/labels.yml` |
| `Major` | stable | `.github/labels.yml` |
| `Minor` | stable | `.github/labels.yml` |
| `Patch` | stable | `.github/labels.yml` |
| `Design` | stable | `.github/labels.yml` |
| `Question` | stable | `.github/labels.yml` |
| `Task` | stable | `.github/labels.yml` |
| `area:product` | stable | `.github/labels.yml` |
| `area:frontend` | stable | `.github/labels.yml` |
| `area:backend` | stable | `.github/labels.yml` |
| `area:infra` | stable | `.github/labels.yml` |
| `area:docs` | stable | `.github/labels.yml` |
| `area:tests` | stable | `.github/labels.yml` |
| `area:agent` | stable | `.github/labels.yml` |
| `area:security` | stable | `.github/labels.yml` |
| `area:marketing` | stable | `.github/labels.yml` |
| `risk:low` | stable | `.github/labels.yml` |
| `risk:medium` | stable | `.github/labels.yml` |
| `risk:high` | stable | `.github/labels.yml` |
| `risk:critical` | stable | `.github/labels.yml` |
| `need:reproduction` | stable | `.github/labels.yml` |
| `need:decision` | stable | `.github/labels.yml` |
| `need:tests` | stable | `.github/labels.yml` |
| `need:docs` | stable | `.github/labels.yml` |
| `need:design` | stable | `.github/labels.yml` |
| `need:security-review` | stable | `.github/labels.yml` |
| `need:human-review` | stable | `.github/labels.yml` |
| `need:wiki-sync` | stable | `.github/labels.yml` |
| `auto-merge` | stable | `.github/labels.yml` |
| `no-issue` | stable | `.github/labels.yml` |
| `main-source-override` | experimental | `.github/labels.yml` |
| `release-window:open` | experimental | `.github/labels.yml` |
| `release-window-override` | experimental | `.github/labels.yml` |
| `status:blocked` | experimental | `.github/labels.yml` |
| `status:ready-to-work` | experimental | `.github/labels.yml` |
| `status:stub` | experimental | `.github/labels.yml` |
| `status:implemented` | experimental | `.github/labels.yml` |
| `no-guidance-update` | stable | `.github/labels.yml` |

---

## Gaps (undocumented, ambiguous, or inconsistent)

1. **No single generated CLI reference** — Flags exist only in argparse; README shows examples, not the full 73-invocation tree. *Maintainer action:* Add `gh plate` reference generator or publish help snapshot in docs.

2. **MCP catalog vs dispatch** — 8 discussion/audit tools appear in `tools/list` without `tools/call` handlers; 2 audit/curiosity tools dispatch but are omitted from `tools/list`. *Maintainer action:* Align list + dispatch or mark deprecated in schema.

3. **Stable vs experimental boundaries** — README lists `gh plate autonomy` as public, but autonomy MCP tools are experimental profile-only. *Maintainer action:* Document 1.0 stable subset explicitly (README ↔ this inventory).

4. **`plate_perform_test_coverage_audit`** — Callable via dispatch but absent from profile map and `tools/list`. *Maintainer action:* Add schema + profile or remove dead dispatch.

5. **process-docs MCP** — Hosted docs MCP (`plateprocess.dev`) is separate from `plate-mcp` but linked via `.plate` `process_docs`. *Maintainer action:* Cross-link in `docs/mcp.md` with version pinning rules.

6. **CLI internal gates** — `pr_*_gate.py` modules are executable CLIs but undocumented in operator docs. *Maintainer action:* Keep internal or document under CI maintainer guide.

7. **`.agentic/procedures/`** — JSON procedures ship in repo; not listed in README public surfaces. *Maintainer action:* Clarify autonomy experimental status for adopters.

8. **Epic label `Epic: *`** — Legacy supplemental labels may exist on GitHub but are not in `labels.yml`. *Maintainer action:* Registry sync vs organic labels.

9. **Classification not machine-checked** — This inventory is manual/heuristic; no CI guard compares README ↔ argparse ↔ MCP list. *Maintainer action:* Optional hardening test mirroring `test_payload_surface.py`.

