# CLI and MCP reference (stable surface)

<!-- PLATE-GENERATED:BEGIN cli-mcp-reference -->
<!-- plate_core 0.12.0 -->

Adopter-facing **stable** `gh plate` commands and `plate-mcp` tools. Classification is taken from
[`docs/plate/research/public-surface-inventory.md`](plate/research/public-surface-inventory.md) (issue #1056). Command flags and tool
parameters are derived from `plate_core.cli.build_parser()` and `plate-mcp` `tools/list` schemas.

Regenerate: `python3 scripts/generate-cli-mcp-reference.py`

## Stable CLI commands

**53** leaf invocations.

### `gh plate adopt`

Adoption readiness, first Q&A seed, or session timer (#935/#949/#955/#633)

| Flag | Description |
| --- | --- |
| `--apply-first-qa` | Attempt live seed (requires --first-qa-plan + injectable runner; blocked without it) |
| `--complete-session` | Complete adoption session and record duration vs 30m (#955) |
| `--first-qa-plan` | Emit first Q&A seed plan (3 starter Questions; dry-run) (#949) |
| `--force` | Force restart of an active adoption session |
| `--json` | Output JSON |
| `--no-optional` | Skip optional SPEC.md/CURRENT.md checks |
| `--repo-root` | Local checkout root (default: current directory) |
| `--require-core-ready` | With --complete-session, refuse if core_ready is false |
| `--session-status` | Show adoption session timer status (#955) |
| `--start-session` | Start local adoption wall-clock session (#955) |

### `gh plate agents delegate`

Delegate a task to a baseline agent

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--task` | Task description to delegate |

### `gh plate agents list`

List baseline agents

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate agents show`

Show baseline agent details

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate autonomy`

Autonomy status, run cycle, and --loop for persistent budgeted long-running operation (Epic #470)

| Flag | Description |
| --- | --- |
| `--budget` | Show durable #634 budget snapshot (limits, spend, remaining, pressure; pairs with feature-loop hydrate) |
| `--budget-reset` | Zero durable spend.json counters for the current UTC day (operator hygiene; does not change .plate limits) |
| `--budget-reset-reason` | Optional note stored on spend.json when using --budget-reset |
| `--dry-run` | Dry run (no side effects) |
| `--estimate-tokens` | With --budget: project would_pause/throttle for this token estimate |
| `--json` | Output JSON |
| `--loop` | Run multiple cycles (use --max-cycles) |
| `--max-cycles` | For --loop |
| `--max-steps` | Cap actions per cycle |
| `--repo` | owner/name; defaults to git remote origin |
| `--run` | Run one cycle (or with --loop) |
| `--scope` | Optional JSON scope for --simulate (e.g. '{"version":"1.0.0"}') |
| `--simulate` | Shadow-simulate a high-impact action without side effects (#645); prints estimates + shadow_id |
| `--sleep-seconds` | Sleep seconds between --loop cycles (defaults to .plate autonomy.loop.default_sleep_seconds or 300; use smaller for demo --loop) |
| `--status` | Show autonomy status (risk tolerance, budget, autopilot score) |

### `gh plate bootstrap`

Plan/apply baseline PLATE bootstrap actions

| Flag | Description |
| --- | --- |
| `--adopt` | Force adoption mode for existing/mature repos (#619) |
| `--apply` | Apply supported actions instead of dry-run planning |
| `--existing-repo` | Alias for --adopt |
| `--greenfield` | Force greenfield new-repo bootstrap (disable auto-adopt detect) |
| `--json` | Output JSON |
| `--local-root` | Local checkout path for adoption heuristics (default: cwd) |
| `--platform` | Script platform for this run. Overrides remote .plate and is written on --apply. Default: remote .plate platform, or posix when absent. |
| `--public` | When creating a missing GitHub repository during --apply, create it public (default: private). |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate ci audit`

Split recent workflow jobs into waiting, setup, and running time (#1282)

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--limit` | Number of recent workflow runs to inspect (default: 30) |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate config init`

Create a baseline .plate file if missing

| Flag | Description |
| --- | --- |
| `--apply` | Accepted for parity with bootstrap flows; config init always writes the file. |
| `--force` | Overwrite an existing .plate file |
| `--json` | Output JSON |
| `--repo-root` | Repository root containing .plate (default: current directory) |

### `gh plate config show`

Show effective local .plate configuration

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--repo-root` | Repository root containing .plate (default: current directory) |

### `gh plate config upgrade`

Upgrade an existing .plate file to the current schema

| Flag | Description |
| --- | --- |
| `--apply` | Write the upgraded .plate file back to disk. Without this flag, show the upgrade result only. |
| `--json` | Output JSON |
| `--repo-root` | Repository root containing .plate (default: current directory) |

### `gh plate config validate`

Validate local .plate configuration

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--repo-root` | Repository root containing .plate (default: current directory) |

### `gh plate context list`

List context routes

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate context show`

Show one context route

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate epic status`

Show Epic status summary

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate features`

Show optional PLATE feature detection

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--local` | Use local filesystem checks for Playwright E2E (config.* + tests/e2e + package.json) per #64 heuristic |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate feed`

Endless ranked feed of open Questions + Tasks for user surfacing (#631)

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--limit` | Max items (default 10) |
| `--no-autonomy` | Omit autonomy checkpoints |
| `--no-process` | Omit plate_what_next process item |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate health`

Show PLATE health summary

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--no-spec-audit` | Skip local SPEC audit summary in health output (#340) |
| `--repo` | owner/name; defaults to git remote origin |
| `--repo-root` | Local checkout root for SPEC audit / filesystem signals (#340) |

### `gh plate hooks install`

Install a PLATE git hook template

| Flag | Description |
| --- | --- |
| `--force` | Replace an existing non-PLATE hook |
| `--hook` | Hook to install (default: pre-push) |
| `--json` |  |
| `--repo-root` | Repository root (default: .) |

### `gh plate hooks run`

Run hook logic (called from .git/hooks/*)

| Flag | Description |
| --- | --- |
| `--repo-root` | Repository root (default: .) |

### `gh plate hooks status`

Show hook install state and configured commands

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--repo-root` | Repository root (default: .) |

### `gh plate import-payload`

Import PLATE template payload into a local checkout (dry-run/apply; #616)

| Flag | Description |
| --- | --- |
| `--apply` | Write files according to strategy (disables dry-run). |
| `--dry-run` | Plan only (default). Use --apply to write files. |
| `--escape-hatch` | Write #622 plan.json + PLAN.md + DRAFT_PR_BODY.md under DIR (never auto-force) |
| `--escape-hatch-on-conflict` | If conflicts exist, write escape-hatch bundle under target/.agentic/import-escape-hatch (#622) |
| `--json` | Output JSON report |
| `--namespace-docs` | Force install PLATE docs under docs/plate/ (#1015) |
| `--namespace-scripts` | Force install PLATE scripts under scripts/plate/ (#621) |
| `--no-namespace-docs` | Keep PLATE docs at docs/ even if target has product docs/ |
| `--no-namespace-scripts` | Keep PLATE scripts at scripts/ even if target has scripts/ |
| `--platform` | Script platform for this run. Overrides target .plate and is written on --apply. Default: target .plate platform, or posix when absent. |
| `--strategy` | safe=skip existing; conservative=report conflicts; force=overwrite |
| `--target-dir` | Local target directory (default: cwd) |
| `--template-repo` | Optional explicit template root path (default: package payload) |

### `gh plate migrate apply`

Apply migration (with checkpoints)

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--repo` | owner/name |

### `gh plate migrate plan`

Dry-run migration plan

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--repo` | owner/name |

### `gh plate payload classify`

Classify a relative payload path

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--template-repo` | Optional explicit template root |

### `gh plate payload list`

List payload files + classification

| Flag | Description |
| --- | --- |
| `--include-excluded` |  |
| `--json` |  |
| `--template-repo` | Optional explicit template root |

### `gh plate payload manifest`

Show template payload manifest

| Flag | Description |
| --- | --- |
| `--json` |  |

### `gh plate payload root`

Resolve payload root path

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--template-repo` | Optional explicit template root |

### `gh plate pm`

Project Manager orchestrator (#660): status, team personas, run assignment cycle

| Flag | Description |
| --- | --- |
| `--apply` | With --run/--loop: attempt delegation (default dry-run) |
| `--complete` | Mark assignment done/cancelled, or Approve & run with --complete-status run |
| `--complete-status` | Status for --complete: done\|cancelled\|run\|approve (run = explicit delegate + dispatch) |
| `--fetch-loop-gates` | With --apply: fetch PR merge gates when ticking babysit loops |
| `--json` |  |
| `--limit` | Queue list limit |
| `--loop` | Multi-cycle orchestrator loop |
| `--max-assignments` |  |
| `--max-cycles` |  |
| `--no-tick-loops` | Skip syncing/completing delegated #638/#639 loops on --run |
| `--note` | Note for --complete |
| `--queue` | List durable assignment queue |
| `--queue-status` | Filter queue: proposed\|delegated\|blocked\|done\|cancelled\|all |
| `--repo` | owner/name |
| `--run` | Run one orchestration cycle |
| `--status` | Show PM status (default) |
| `--team` | List personas |
| `--tick-loops` | Tick delegated #638/#639 loops only (no new assigns); use --apply to advance estimate_cost/babysit |

### `gh plate pr babysit`

Monitor a PR for actionable review feedback and optionally post a local babysit trigger

| Flag | Description |
| --- | --- |
| `--act` | Post a babysit trigger comment when actionable feedback exists |
| `--agents` | Comma-separated GitHub login allowlist (overrides --scope / autonomy.pr_review_scope). |
| `--branch-update-strategy` | How to handle out-of-sync base branch: local-rebase (default), copilot-request (opt-in), or none |
| `--cap-hours` | Hour budget stored when a cap ledger is created (default 12). Later watches keep the saved budget until --reset-caps. |
| `--full-every` | Force a full babysit_pr every N watch ticks (0 disables; safety net) |
| `--json` | Output JSON |
| `--max-hours` | Stop --watch after this many hours (0 disables the limit) |
| `--max-interval` | Maximum polling interval in seconds for --watch mode |
| `--max-wakes` | Wake budget stored when a cap ledger is created (default 10). Later watches keep the saved budget until --reset-caps. |
| `--min-interval` | Minimum polling interval in seconds for --watch mode (--interval is deprecated) |
| `--repo` | owner/name; defaults to git remote origin |
| `--reset-caps` | Start a new watch budget, clearing this PR's saved cap ledger (requires --watch) |
| `--scope` | Who counts as actionable (#496): all (default), bot-only, or human-only. Overrides .plate autonomy.pr_review_scope. |
| `--status` | Show the saved watch budget and usage without polling GitHub |
| `--stop` | Stop babysit --watch processes recorded in .agentic/babysit (one PR, or all when pr_number is omitted) |
| `--watch` | Continuously monitor the PR until stopped or a spend cap is reached |

### `gh plate pr create`

Run preflight then gh pr create (passes through remaining gh arguments)

| Flag | Description |
| --- | --- |
| `--json` | Output JSON preflight report on failure |
| `--repo` | owner/name; defaults to git remote origin |
| `--repo-root` | Repository root (default: .) |

### `gh plate pr health`

Get comprehensive merge gates status for a PR (labels, threads, CI, etc.) using the get_pr_merge_gates helper

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate pr preflight`

Run local plate-pr-gates + labels checks before opening a PR

| Flag | Description |
| --- | --- |
| `--base` | Integration base branch for --base validation |
| `--body-file` | PR body file (also accepted via trailing gh args) |
| `--json` | Output JSON |
| `--labels` | Comma-separated PR type/area labels (same as gh pr create --label, combined) |
| `--repo` | owner/name; defaults to git remote origin |
| `--repo-root` | Repository root (default: .) |

### `gh plate pr verify`

Run scripted pre-merge checks for a PR (read-only; never merges)

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--repo` | owner/name; defaults to git remote origin |
| `--repo-root` | Repository root for --run-tests (default: .) |
| `--run-tests` | Run PYTHONPATH=src python3 -m unittest discover -s tests locally |

### `gh plate qanda`

Curiosity / Q&A Mode (list, view, record answers on Question issues; Epic #139)

| Flag | Description |
| --- | --- |
| `--answer` | Answer text when using --record |
| `--by` | Who is answering (for provenance) |
| `--json` | Output JSON |
| `--limit` | Max results for synthesize |
| `--list` | List + synthesize priorities for open Questions (default) |
| `--question` | Show full details for a specific Question number |
| `--record` | Record an answer to this Question number |
| `--repo` | owner/name; defaults to git remote origin |
| `--synthesize` | Just return prioritized list |

### `gh plate release cleanup-branches`

Find and optionally delete dead remote branches (merged + no open PR).

| Flag | Description |
| --- | --- |
| `--apply` | Delete candidate branches. Without this flag, command runs in dry-run mode. |
| `--base` | Base branch to compare merge state against (default: repository default branch). |
| `--json` | Output JSON |
| `--limit` | Optional maximum number of candidate branches to delete/report. |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate release cut`

Cut a release: aggregate fragments to versioned dir (first-class MVP per #261)

| Flag | Description |
| --- | --- |
| `--dry-run` | Do not write files (dry-run) |
| `--json` | Output JSON (future) |
| `--releases-dir` | Path to releases directory (default: .agentic/releases) |
| `--version-type` | Override bump type for auto-detect |

### `gh plate release finalize`

Finalize a release: tag, kick .plate-configured downstream triggers, ensure next 'Next Release' issue (per refined ceremony)

| Flag | Description |
| --- | --- |
| `--apply` | Perform side effects including fast-forward of release branches to the tag (no force push). GitHub Release creation is attempted by default (idempotent via existence check). |
| `--dry-run` | Do not execute side effects (dry-run) |
| `--force-hard-reset` | Admin-only: force-with-lease reset of existing release track branches (requires --apply). Not part of the automatic ceremony. |
| `--json` | Output JSON (future) |
| `--releases-dir` | Path to releases directory (default: .agentic/releases) |

### `gh plate release init`

Alias for release repair (#320): ensure standing Next Release state

| Flag | Description |
| --- | --- |
| `--apply` |  |
| `--json` |  |
| `--repo` | owner/name |

### `gh plate release notes`

Show release notes diff between versions

| Flag | Description |
| --- | --- |
| `--from` | Start version (exclusive) |
| `--json` | Output JSON |
| `--releases-dir` | Path to releases directory (default: .agentic/releases) |
| `--to` | End version (inclusive) |

### `gh plate release repair`

Init/repair standing release tracks + Next Release issue (#320)

| Flag | Description |
| --- | --- |
| `--apply` | Create missing branches/issues (default dry-run) |
| `--json` |  |
| `--repo` | owner/name |

### `gh plate release status`

Show current release status

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |
| `--releases-dir` | Path to releases directory (default: .agentic/releases) |
| `--repo` | owner/name; defaults to git remote origin |

### `gh plate release target-epic`

Validate an Epic against the active Next Release and print the manual issue-link step required by GitHub UI (#313)

| Flag | Description |
| --- | --- |
| `--json` | Output JSON guidance |
| `--repo` | owner/name |

### `gh plate runner add`

Register an ephemeral runner with plate-local + OS labels (dry-run by default)

| Flag | Description |
| --- | --- |
| `--apply` | Perform registration (default is dry-run plan only) |
| `--json` |  |
| `--os` | OS label to register (default: detect from local platform) |
| `--repo-root` | Repository root for .agentic/runner.json |

### `gh plate runner doctor`

Check labels, token scope, service state, and isolation settings

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--repo-root` |  |

### `gh plate runner remove`

Unregister runners and clear local state (dry-run by default)

| Flag | Description |
| --- | --- |
| `--apply` | Perform removal |
| `--json` |  |
| `--repo` | owner/name (default: from .agentic/runner.json) |
| `--repo-root` |  |

### `gh plate runner status`

List runners and online/idle state

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--repo` | owner/name (default: from .agentic/runner.json) |
| `--repo-root` |  |

### `gh plate self-migrate`

Pin/payload plan or PLATES-CORE marker merge (#939/#943/#649); dry-run default

| Flag | Description |
| --- | --- |
| `--allow-high-risk` | Permit apply of non-low-risk PR plans (still requires runner) |
| `--allow-network` | Permit live PyPI fetch when used with --resolve-upstream (default: no network) |
| `--apply-markers` | Write merged marker content (requires --merge-markers); default dry-run |
| `--apply-pr` | Attempt live PR apply (requires --pr-plan; needs injectable runner; blocked without it) |
| `--base` | PR base branch for --pr-plan (default: release) |
| `--closes` | Optional issue ref for PR body (e.g. #947) |
| `--json` | Output JSON |
| `--merge-markers` | Plan/apply PLATES-CORE sectional merge vs upstream (#943) |
| `--no-payload` | Omit import-payload step from the plan |
| `--path` | Relative path to merge (repeatable); default: marker-bearing refresh files |
| `--plan` | Emit plan (default behavior; accepted for explicit UX) |
| `--pr-plan` | Emit low-risk migration PR plan (dry-run; no git) (#947) |
| `--repo-root` | Local checkout root (default: current directory) |
| `--resolve-upstream` | Resolve upstream plate-core version for target (#945); offline unless --allow-network |
| `--target-version` | Optional target plate-core version (default: installed __version__) |
| `--upstream-dir` | Directory of upstream files for --merge-markers (mirrors relative paths) |
| `--verify` | Offline post-migrate verify: drift + adoption + .plate (#965); no writes |

### `gh plate skills list`

List baseline skills

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate skills show`

Show baseline skill details

| Flag | Description |
| --- | --- |
| `--json` | Output JSON |

### `gh plate spec-audit`

Audit SPEC.md vs release fragments and path citations (#338)

| Flag | Description |
| --- | --- |
| `--apply-followups` | Create follow-up GitHub issues (never writes SPEC.md; #339) |
| `--followups` | Plan follow-up issues + SPEC draft from findings (#339) |
| `--json` | Output JSON report |
| `--max-followups` | Max actionable issues to plan/create (default 10) |
| `--releases-dir` | Optional path to .agentic/releases |
| `--repo` | owner/name for issue creation (default: git remote) |
| `--repo-root` | Repository root containing SPEC.md (default: cwd) |
| `--show-draft` | Print proposed additive SPEC markdown draft |
| `--spec` | Optional path to SPEC.md |

### `gh plate task`

Create/close human Task issues (#359): required 6-field contract

| Flag | Description |
| --- | --- |
| `--apply` | With --detect: create Task issues for blockers (default detect-only) |
| `--close` | Close Task #N with PLATE-TASK-CLOSED |
| `--comment` | Completion comment for --close |
| `--context` | Context and affected artifacts |
| `--create` | Create a Task issue |
| `--detect` | Detect human-only blockers from --signal (#360) |
| `--done-signal` | Override default done signal text |
| `--dry-run` |  |
| `--epic-milestone` | Epic milestone title to inherit |
| `--human-action` | What the human must do |
| `--instructions` | Best-effort next steps |
| `--json` |  |
| `--milestone` | Milestone number or title |
| `--related` | Related links (text) |
| `--repo` | owner/name |
| `--signal` | Text signal to classify (CI log, error, note) |
| `--title` | Task title (human action summary) |
| `--why` | Why the agent cannot safely proceed |

### `gh plate tasks validate`

Validate task spec YAML files

| Flag | Description |
| --- | --- |
| `--json` |  |
| `--path` | Validate a single file (repeatable); skips directory scan |
| `--repo-root` | Repository root (default: current directory) |
| `--tasks-dir` | Override tasks directory (default: <repo-root>/.agentic/tasks) |

### `gh plate what-next`

Recommend next PLATE process step (budget → open PRs → epics) (#789/#791)

| Flag | Description |
| --- | --- |
| `--agent-type` |  |
| `--json` | Output JSON |
| `--no-budget` | Skip budget snapshot |
| `--no-fragments` | Skip unreleased fragment count |
| `--no-prs` | Skip open PR scan |
| `--repo` | owner/name; defaults to git remote origin |

## Stable MCP tools

**59** tools from the stable profiles in the inventory.

### `init_playwright`

Initialize Playwright E2E testing in a repository.

| Parameter | Description |
| --- | --- |
| `force` | Overwrite existing tests/e2e/ directory. Defaults to false. |
| `repo_path` | Path to target repository. Defaults to current directory. |
| `template_repo` | Path to template source override. Defaults to plate payload in this repository. |

### `plate_adoption_first_qa_plan`

First Q&A seed plan after adoption core_ready (#949/#633). Dry-run default; apply needs injectable runner.

| Parameter | Description |
| --- | --- |
| `apply` | Attempt live seed (requires runner; default false). |
| `repo_root` | Local checkout root (default cwd). |

### `plate_adoption_session`

Adoption wall-clock session timer for <30m proof (#955/#633). action=start|complete|status; local only.

| Parameter | Description |
| --- | --- |
| `action` | start \| complete \| status (default status). |
| `force` | Force restart when action=start. |
| `repo_root` | Local checkout root (default cwd). |
| `require_core_ready` | When action=complete, refuse if core_ready is false. |

### `plate_adoption_status`

Local adoption readiness checklist for <30m onboarding (#935/#633). Status only — no apply.

| Parameter | Description |
| --- | --- |
| `no_optional` | When true, skip optional SPEC.md/CURRENT.md checks. |
| `repo_root` | Local checkout root (default cwd). |

### `plate_agent`

Return one baseline agent by id.

| Parameter | Description |
| --- | --- |
| `agent_id` | Baseline agent id. |

### `plate_agents`

Return the baseline agent catalog.

_No schema properties (empty object)._

### `plate_bootstrap`

Plan or apply baseline PLATE bootstrap actions. Supports adoption mode (#619) via adopt=true for existing/mature repos.

| Parameter | Description |
| --- | --- |
| `adopt` | Force adoption mode (true) or leave null for auto-detect; false forces greenfield. |
| `apply` | When true, apply supported actions; default false (dry-run). |
| `existing_repo` | Alias for adopt=true. |
| `local_root` | Local checkout path for adoption heuristics (default cwd). |
| `platform` | Script platform for this run. Overrides remote .plate and is written when apply=true. Omit to use remote .plate, or posix when absent. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_config_get`

Return effective local .plate configuration state for the current repository or repo_root.

| Parameter | Description |
| --- | --- |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_config_init`

Create a baseline root .plate configuration file if missing (or overwrite with force).

| Parameter | Description |
| --- | --- |
| `force` | Overwrite an existing .plate file when true. |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_config_upgrade`

Upgrade an existing local .plate file to the current schema version, optionally writing it back to disk.

| Parameter | Description |
| --- | --- |
| `apply` | When true, write the upgraded .plate file back to disk. |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_config_validate`

Validate local .plate configuration and return the effective report shape.

| Parameter | Description |
| --- | --- |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_context`

Return one canonical PLATE context-map route by id.

| Parameter | Description |
| --- | --- |
| `context_id` | Context route id. |

### `plate_contexts`

Return the canonical PLATE context-map routes used to decide where authoritative truth lives for a task.

_No schema properties (empty object)._

### `plate_delegate_to_agent`

Route a task to a baseline agent (by id) and return a narrow delegation packet (details, skills, constraints, short prompt). Always call with a short task_description per the plate persona. Packets include retrieval hints; keep responses scoped and quiet per guidance.

| Parameter | Description |
| --- | --- |
| `agent_id` | Baseline agent id to delegate the task to. |
| `task_description` | Free-text description of the task to delegate. |

### `plate_epic_status`

Return Epic and child issue summary for a repository.

| Parameter | Description |
| --- | --- |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_features`

Return optional PLATE capability detection for a repository.

| Parameter | Description |
| --- | --- |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_feed`

Ranked endless feed of open Questions + Tasks (plus process/autonomy signals) for native TUI/CLI presentation (#631). Prefer this for user-facing Q&A/Task surfacing.

| Parameter | Description |
| --- | --- |
| `include_autonomy` | Include open autonomy checkpoints (default true). |
| `include_process` | Include plate_what_next process item (default true). |
| `limit` | Max items (default 10). |
| `repo` | owner/name. Optional. |

### `plate_get_actionable_review_threads`

List actionable (unresolved, non-outdated) review threads for a PR under pr_review_scope (#496: all|bot-only|human-only; default all includes Copilot). High-level helper: GraphQL reviewThreads, databaseId, suggestion metadata. Use with plate_resolve_review_thread / plate_pr_babysit. Addresses #516/#496.

| Parameter | Description |
| --- | --- |
| `agent_logins` | Comma-separated login allowlist (optional; overrides scope). |
| `pr_number` | Pull request number. |
| `repo` | owner/name. Optional if running inside repo clone. |
| `scope` | pr_review_scope (#496). Default all. |

### `plate_get_pr_merge_gates`

Get comprehensive merge gates status for a PR using the get_pr_merge_gates helper (merge state, threads, note with checklist). Complements plate_pr_babysit for full 'make mergeable' ownership per #526.

| Parameter | Description |
| --- | --- |
| `pr_number` | Pull request number. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_get_unresolved_review_threads`

List all unresolved review threads (isResolved: false, including outdated) for address-pr-feedback fetch and done gate (#1155). Use plate_get_actionable_review_threads for scoped actionable work only.

| Parameter | Description |
| --- | --- |
| `pr_number` | Pull request number. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_health`

Return PLATE health summary for a repository, including local SPEC audit drift signals (#340).

| Parameter | Description |
| --- | --- |
| `no_spec_audit` | When true, skip local SPEC audit summary. |
| `repo` | owner/name. Optional if running inside repo clone. |
| `repo_root` | Local checkout root for SPEC audit filesystem signals. Defaults to current working directory. |

### `plate_hooks_install`

Install the PLATE pre-push or pre-commit git hook template (#1281/#1302). Prefer this over shelling out to gh plate hooks install.

| Parameter | Description |
| --- | --- |
| `force` | Replace an existing non-PLATE hook when true. |
| `hook` | Hook to install (default pre-push). |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_hooks_status`

Report install state and configured commands for PLATE pre-push and pre-commit hooks (#1302).

| Parameter | Description |
| --- | --- |
| `repo_root` | Optional local repository root path. Defaults to current directory. |

### `plate_import_payload`

Import PLATE template payload into a local checkout (#616). Dry-run by default; set apply=true to write. Strategies: safe|conservative|force. namespace_scripts installs under scripts/plate/ when product scripts/ exists (#621). namespace_docs installs under docs/plate/ when product docs/ exists (#1015); omit for auto-detect, false to keep docs/ root. platform is posix (default), posix-and-windows, or windows; it filters PLATE-owned script twins and is written on apply. escape_hatch_dir writes plan.json+PLAN.md+DRAFT_PR_BODY.md for hard merges (#622); never force-overwrite high-value paths without human approval.

| Parameter | Description |
| --- | --- |
| `apply` | Write files (default false). |
| `dry_run` | Plan only (default true). |
| `escape_hatch_dir` | Write #622 escape-hatch bundle under this directory. |
| `escape_hatch_on_conflict` | Auto-write escape hatch under target/.agentic/import-escape-hatch when conflicts exist. |
| `namespace_docs` | Force docs/plate/ install; omit for auto-detect; false keeps docs/ root (#1015). |
| `namespace_scripts` | Force scripts/plate/ install; omit for auto-detect. |
| `platform` | Script platform for this run. Overrides target .plate and is written when apply=true. Omit to use target .plate, or posix when absent. |
| `strategy` | safe \| conservative \| force (default safe). |
| `target_dir` | Local target directory (default .). |
| `template_repo` | Optional explicit template root path. |

### `plate_migrate_apply`

Apply migration steps (with checkpoint/rollback support). Use after reviewing plan.

| Parameter | Description |
| --- | --- |
| `dry_run` | Simulate only (default true for safety). |
| `repo` | owner/name. Optional. |

### `plate_migrate_docs_namespace`

Migrate PLATE docs from docs/ root to docs/plate/ namespace (#1027). Uses git mv to move PLATE-owned doc directories (adr, audits, bootstrap, design, marketing, migration, research, wiki) and PLATE root doc files. Preserves AGENTS.md, SPEC.md, CURRENT.md and all product docs. Rewrites references in repository files. Idempotent (safe to re-run). Dry-run by default; set apply=true to perform the migration.

| Parameter | Description |
| --- | --- |
| `apply` | Apply the migration (default: false for dry-run) |
| `target_dir` | Repository root directory (default: current directory) |

### `plate_migrate_plan`

Generate dry-run migration plan for template-to-plate cutover using current inventory and .plate state.

| Parameter | Description |
| --- | --- |
| `repo` | owner/name. Optional. |

### `plate_payload_classify`

Classify a relative path against the payload manifest (#621).

| Parameter | Description |
| --- | --- |
| `path` |  |
| `template_repo` |  |

### `plate_payload_list`

List PLATE template payload files with classification and path_rules (#621).

| Parameter | Description |
| --- | --- |
| `include_excluded` |  |
| `template_repo` |  |

### `plate_payload_manifest`

Show template payload manifest including path_rules (#621).

_No schema properties (empty object)._

### `plate_payload_root`

Resolve package payload root path and source kind (#621).

| Parameter | Description |
| --- | --- |
| `template_repo` |  |

### `plate_pr_babysit`

Inspect a pull request for unresolved review feedback (scope: all|bot-only|human-only per #496) and base branch sync state. Optionally post trigger comments and auto-resolve outdated threads (--act / act=true).

| Parameter | Description |
| --- | --- |
| `act` | When true, post trigger comments if issues detected and auto-resolve outdated threads. |
| `agents` | Optional comma-separated login allowlist (overrides scope). |
| `branch_update_strategy` | How to handle out-of-sync base branch: local-rebase (default, local worktree rebase+push), copilot-request (opt-in, triggers Copilot merge assist), or none (detect only). |
| `pr_number` | Pull request number. |
| `repo` | owner/name. Optional if running inside repo clone. |
| `scope` | pr_review_scope (#496). Default all (from .plate or built-in). |

### `plate_pr_packet`

Compact JSON evidence packet for PR review feedback (#1364): threads, failing check excerpts, PR facts, probe deltas. Prefer over re-reading raw bot comments.

| Parameter | Description |
| --- | --- |
| `cloud_agent_id` |  |
| `max_bytes` | UTF-8 size cap before truncation (default 6144). |
| `pr_number` | Pull request number. |
| `record_ledger` | Record handoff_packet_size (+ optional turns) to spend ledger. |
| `repo` | owner/name. Optional if running inside repo clone. |
| `run_id` |  |
| `turns` |  |

### `plate_pr_verify`

Run scripted pre-merge checks for a PR (base main, labels, fragment, milestone, closing keyword, CI, review threads). Read-only; never merges. Optional run_tests.

| Parameter | Description |
| --- | --- |
| `pr_number` | Pull request number. |
| `repo` | owner/name. Optional if running inside repo clone. |
| `repo_root` | Repository root for run_tests (default: .). |
| `run_tests` | When true, run PYTHONPATH=src python3 -m unittest discover -s tests locally and include the count (warns on stale-base signatures). |

### `plate_release_cleanup_branches`

Find dead remote branches (merged into base and no open PR) and optionally delete them as a fallback cleanup tool.

| Parameter | Description |
| --- | --- |
| `apply` | When true, delete candidate branches. Defaults to false (dry-run). |
| `base_branch` | Base branch to compare merge state against. Defaults to repository default branch. |
| `limit` | Optional max number of candidate branches to process. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_release_media_decide`

Approve/reject a media item in-memory (persist by editing fragment) (#635).

| Parameter | Description |
| --- | --- |
| `decision` |  |
| `index` |  |
| `path` |  |
| `releases_dir` |  |
| `url` |  |

### `plate_release_media_feed`

Feed items for pending release media approval (#635).

| Parameter | Description |
| --- | --- |
| `releases_dir` |  |

### `plate_release_media_manifest`

Aggregate GIF/video media from unreleased fragments for release notes (#635).

| Parameter | Description |
| --- | --- |
| `releases_dir` |  |
| `version` |  |

### `plate_release_media_render`

Render release media markdown from fragments (#635).

| Parameter | Description |
| --- | --- |
| `only_approved` |  |
| `releases_dir` |  |

### `plate_release_media_validate_paths`

Check that fragment media paths exist on disk (#635).

| Parameter | Description |
| --- | --- |
| `releases_dir` |  |

### `plate_release_notes`

Return a structured diff of PLATE release notes between two versions, including migration steps. Use to understand what changed between your current PLATE version and the latest.

| Parameter | Description |
| --- | --- |
| `from_version` | Start version (exclusive, e.g. '0.1.2'). Omit for all versions from beginning. |
| `releases_dir` | Path to the releases directory. Defaults to .agentic/releases. |
| `to_version` | End version (inclusive, e.g. '0.2.0'). Omit for latest. |

### `plate_release_repair`

Init/repair standing release tracks (release-major/minor/patch + legacy release) and ensure exactly one Next Release issue (#320). Default dry-run; set apply=true to create missing artifacts.

| Parameter | Description |
| --- | --- |
| `apply` |  |
| `repo` |  |

### `plate_release_status`

Return the current PLATE release status: release branch existence, open Release issues, active Next Release visibility, linked/on-hold Epics, track summary, pending unreleased fragments, and extension release checks.

| Parameter | Description |
| --- | --- |
| `releases_dir` | Path to the releases directory. Defaults to .agentic/releases. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_release_target_epic`

Validate an Epic against the active Next Release and return the manual issue-linking guidance required because GitHub does not expose a public API to create the issue-to-issue sidebar link directly.

| Parameter | Description |
| --- | --- |
| `epic_number` | Epic issue number to validate against the active Next Release. |
| `repo` | owner/name. Optional if running inside repo clone. |

### `plate_resolve_review_thread`

Resolve a pull request review thread via GitHub GraphQL resolveReviewThread.

| Parameter | Description |
| --- | --- |
| `repo` | owner/name. Optional if running inside repo clone. |
| `thread_id` | GraphQL node ID of the review thread to resolve. |

### `plate_self_migrate_merge_markers`

Plan/apply PLATES-CORE marker sectional merge vs upstream files (#943/#649). Dry-run unless apply=true; no network.

| Parameter | Description |
| --- | --- |
| `apply` | When true, write merged content. Default false (dry-run). |
| `paths` | Relative paths to merge; default marker-bearing refresh files. |
| `repo_root` | Local checkout root (default cwd). |
| `upstream_root` | Directory of upstream files mirroring relative paths. |

### `plate_self_migrate_plan`

Dry-run self-migrate plan for plate-core pin/payload drift (#939/#945/#649). No apply; network only if resolve_upstream+allow_network.

| Parameter | Description |
| --- | --- |
| `allow_network` | Permit live PyPI JSON fetch for resolve_upstream. Default false. |
| `no_payload` | When true, omit import-payload step from the plan. |
| `repo_root` | Local checkout root (default cwd). |
| `resolve_upstream` | Attempt upstream version resolve (#945). Offline unless allow_network. |
| `target_version` | Optional target plate-core semver; default installed version. |

### `plate_self_migrate_pr_plan`

Low-risk self-migrate migration PR plan (#947/#649). Dry-run by default; apply needs injectable runner and low-risk pin-only eligibility.

| Parameter | Description |
| --- | --- |
| `allow_high_risk` | Permit non-low-risk apply when runner provided. |
| `allow_network` | Permit network for resolve_upstream. |
| `apply` | Attempt live apply (requires runner; default false). |
| `base` | PR base branch (default release). |
| `closes` | Optional issue ref for PR body. |
| `no_payload` | Omit payload step from underlying migrate plan. |
| `repo_root` | Local checkout root (default cwd). |
| `resolve_upstream` | Resolve upstream version for target. |
| `target_version` | Optional target plate-core semver. |

### `plate_self_migrate_verify`

Offline post-migrate verify: pin/payload drift + adoption core_ready + .plate validity (#965/#649). No writes, no network by default.

| Parameter | Description |
| --- | --- |
| `allow_network` | Permit network for resolve_upstream. Default false. |
| `no_payload` | Omit payload from underlying migrate plan when checking drift. |
| `repo_root` | Local checkout root (default cwd). |
| `resolve_upstream` | Resolve upstream version for target. |
| `target_version` | Optional target plate-core semver. |

### `plate_skill`

Return one baseline skill by id.

| Parameter | Description |
| --- | --- |
| `skill_id` | Baseline skill id. |

### `plate_skills`

Return the baseline skill catalog.

_No schema properties (empty object)._

### `plate_spec_audit`

Audit SPEC.md against unreleased fragments and path citations (#338). Returns structured findings (aligned/undocumented/stale_evidence/future_ok).

| Parameter | Description |
| --- | --- |
| `releases_dir` | Optional .agentic/releases path. |
| `repo_root` | Local repo root (default .). |
| `spec_path` | Optional path to SPEC.md. |

### `plate_spec_audit_followups`

From SPEC audit findings, plan (default) or create follow-up issues and a SPEC draft table (#339). Never writes SPEC.md. apply=true creates GitHub issues with human-checkpoint bodies.

| Parameter | Description |
| --- | --- |
| `apply` | Create issues when true (default false dry-run). |
| `max_issues` | Cap actionable issues (default 10). |
| `releases_dir` |  |
| `repo` | owner/name for issue creation |
| `repo_root` |  |
| `spec_path` |  |

### `plate_task_close`

Close a Task with <!-- PLATE-TASK-CLOSED --> after human completion (#359). Do not invent completion.

| Parameter | Description |
| --- | --- |
| `comment` |  |
| `dry_run` |  |
| `number` |  |
| `repo` |  |

### `plate_task_create`

Create a human-only Task issue with the 6-field contract (#359). Redacts secret-looking text. Agents never complete the human work.

| Parameter | Description |
| --- | --- |
| `context` |  |
| `done_signal` |  |
| `dry_run` |  |
| `epic_milestone` |  |
| `human_action` |  |
| `instructions` |  |
| `milestone` |  |
| `related_links` |  |
| `repo` |  |
| `title` |  |
| `why_agent_cannot` |  |

### `plate_task_detect`

Detect human-only blockers (credentials, PyPI, billing, marketplace, external accounts) and optionally create Task issues (#360). Default detect-only (create=false, dry_run=true).

| Parameter | Description |
| --- | --- |
| `context` |  |
| `create` |  |
| `dry_run` |  |
| `repo` |  |
| `signal` |  |
| `signals` |  |
| `text` |  |

### `plate_what_next`

Returns the next recommended PLATE process step and a short prompt segment, based on live health/epics/labels/fragments/Goals. Use first for autonomous or looped flows; follow quiet turn-summary rules for long-running use.

| Parameter | Description |
| --- | --- |
| `agent_type` | Optional hint for specialized guidance (general, coding, docs, etc.). |
| `repo` | owner/name. Optional if running inside repo clone. |

### `record_e2e_gif`

Record and generate a demo GIF from a Playwright E2E test.

| Parameter | Description |
| --- | --- |
| `quality` | Quality: 'low' (10fps), 'medium' (15fps), 'high' (30fps). Defaults to 'medium'. |
| `repo_path` | Path to repository with Playwright setup. |
| `test_name` | Name of test to record (e.g., 'login', 'feature-flow'). |

### `validate_e2e_tests`

Validate Playwright E2E setup and detect missing configuration.

| Parameter | Description |
| --- | --- |
| `repo_path` | Path to repository. Defaults to current directory. |

<!-- PLATE-GENERATED:END cli-mcp-reference -->
