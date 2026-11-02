# Agent crew task spec (issue #1333 / design #1327)

Machine-readable task contracts live in `.agentic/tasks/<id>.yml`. They extend the narrow delegation packet from [#395](cost-control-narrow-delegation-packets.md): the YAML is primary; hosts render a short prompt from these fields instead of copying broad policy.

## Schema

- **Version:** `task_spec_version: "1.0"` (JSON Schema at `src/plate_core/data/task_spec.schema.json` in plate-core).
- **Identity:** `id` (kebab-case), `role` (a `baseline_catalog.yml` agent id), `kind` (PLATE issue type label value).
- **Routing (spec fields, not labels):** `level` (`junior` | `senior` | `staff`), `route` (`docs` | `tests` | `fix` | `feature` | `review`).
- **Typed IO:** `inputs` / `outputs` lists of `{id, type, description?, required?}` with types such as `issue_ref`, `file_path`, `artifact_ref`.
- **Acceptance:** `acceptance.checks` (human/agent checklist strings) and `acceptance.success_signal` (done signal for prompt rendering).
- **Tools:** `tools.allow` (explicit MCP tool names) and/or `tools.profiles` (names from `src/plate_core/mcp/tool_profiles.py`).
- **Model policy:** `model_policy.tiers`, `start_tier`, optional single `escalation` step, `max_cost_usd`; when `T3` is allowed, `model_policy.t3_requires_approval: human` and a human `approval` gate are required.
- **Budget:** `budget.max_tokens_per_run`.
- **Workflow edges:** `next` lists `{task_id, when?}` static links to other spec ids; `.agentic/procedures/` remains the workflow layer that chains specs.

## Role vs level vs route

When dispatching from a GitHub issue, **role** may be **inferred** from issue type and labels (see `infer_role_from_issue()` in `plate_core.task_spec`). The spec still declares `role` for deterministic delegation packets. **Level** and **route** are always spec fields—do not encode them as GitHub labels for crew routing.

## Validation

```bash
gh plate tasks validate [--repo-root PATH] [--json]
python -m plate_core.task_spec [--repo-root PATH] [--path FILE ...] [--json]
```

Validates every `*.yml` / `*.yaml` under `.agentic/tasks/` (or explicit `--path` files). Cross-checks `next.task_id` references within the validated set.

## Examples

Shipped under `src/plate_core/data/examples/`:

- `task-spec-research-synthesis.yml`
- `task-spec-design-from-research.yml`

Copy into `.agentic/tasks/` as a starting point for crew pilots (DentalCoach, Happyhouses, etc.).

## Out of scope for #1333

Resource registry/router runtime, reviewer-differs enforcement, new GitHub labels, label-check workflow changes, and procedure authoring are tracked under design #1327 and sibling issues.
