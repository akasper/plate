---
name: Run Autonomy Cycle / Loop
description: Drive long-running PLATE work via AutonomyEngine surfaces: plate_autonomy_status, plate_autonomy_run_cycle, plate_autonomy_list_procedures, plate_autonomy_run_procedure (or gh plate autonomy --status|--run|--loop). Respect .plate autonomy.risk_tolerance, token budgets, and quiet_operations (terse bullets only). Use after plate_what_next when the next step is continuous/scheduled progress. See autonomy_loops guidance (#480 / Epic #470).
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Run Autonomy Cycle / Loop

> Skill id: `run-autonomy-cycle`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Drive long-running PLATE work via AutonomyEngine surfaces: plate_autonomy_status, plate_autonomy_run_cycle, plate_autonomy_list_procedures, plate_autonomy_run_procedure (or gh plate autonomy --status|--run|--loop). Respect .plate autonomy.risk_tolerance, token budgets, and quiet_operations (terse bullets only). Use after plate_what_next when the next step is continuous/scheduled progress. See autonomy_loops guidance (#480 / Epic #470).

**Owning agents:** project-manager

## Inputs

- Live autonomy status (risk_tolerance, budget remaining, due procedures)
- Optional dry_run flag
- Optional procedure id

## Outputs

- Cycle report or status dict
- Optional PLATE-AUTONOMY-CYCLE / PLATE-PROCEDURE-RUN markers + USAGE REPORT
- Terse bullet turn summary for loops

## Examples

- Call plate_autonomy_status; if risk_tolerance is medium and budget remains, plate_autonomy_run_cycle dry_run then live.
- gh plate autonomy --loop --max-cycles 3 with quiet bullet summaries only.

<!-- PLATE-GENERATED:END skills-surface -->
