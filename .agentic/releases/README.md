# PLATE release notes

This directory is the machine-readable source of truth for PLATE release notes.

## Layout

Store one JSON file per semantic version:

- `.agentic/releases/v0.1.0.json`
- `.agentic/releases/v0.2.0.json`

Semantic version tags group the release notes. Each file contains the changes for that PLATE release.

## Required fields

Every release file must include:

- `version` — semantic version string for the PLATE release
- `summary` — short release summary
- `entries` — ordered list of release-note entries

Every entry must include:

- `change_type` — e.g. `feature`, `fix`, `docs`, `process`, `breaking`
- `surface` — affected template / workflow / docs surface
- `migration_impact` — what a downstream repo must do
- `agent_notes` — agent-friendly upgrade guidance

Optional fields:

- `breaking` — boolean
- `links` — related issue / PR references
- `requires` — dependency version(s) or prior note identifiers

## Rendering

Use `scripts/render_release_notes.py` to render a file or the entire directory into human-readable Markdown.

## Example

See `v0.1.0.json` for a starter record.
