# Decision Ledger Directory

This directory holds append-only decision and provenance ledger JSON files written by the PLATE autonomy engine.

## Purpose

The decision ledger provides an inspectable, queryable record of autonomous actions and decisions:
- Why each action was chosen or skipped
- Data sources (health, Goals, Q&A, SPEC, shadow/checkpoint IDs)
- Cost and risk reasoning
- Structured PLATE-DECISION markers for GitHub comments

## Storage Format

Each ledger entry is stored as `.agentic/ledger/<id>.json` where `<id>` is a unique decision identifier (e.g., `dec-a1b2c3d4e5f6`).

Files are local repository artifacts, not stored in a separate SaaS service.

## Usage

Ledger entries are created automatically by:
- `plate_core.ledger.record_decision()` — Python API
- `plate_ledger_record` — MCP tool
- `gh plate ledger --record` — CLI command
- AutonomyEngine during `run_cycle` for autonomous decisions

Query and inspect entries via:
- `plate_ledger_list`, `plate_ledger_get`, `plate_ledger_query`, `plate_ledger_summary` — MCP tools
- `gh plate ledger --list`, `--get`, `--query`, `--summary` — CLI commands
- Direct file system access to JSON files

## State

An empty directory is valid and expected until autonomous decisions are recorded. The directory structure is created on first write.

## Related

- Implementation: `src/plate_core/ledger.py` (`LEDGER_DIR = Path(".agentic/ledger")`)
- Feature: #647 (Provenance + decision ledger)
- Audit artifacts: Local durable records; commit selected entries for project truth or keep gitignored for ephemeral session logs
