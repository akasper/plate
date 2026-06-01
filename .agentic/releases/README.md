# PLATE release notes

This directory is the machine-readable source of truth for PLATE release notes.

## Layout

Two layouts are supported and coexist for backward compatibility:

**Flat files (legacy):** One JSON file per semantic version at the root level:
- `.agentic/releases/v0.1.0.json`
- `.agentic/releases/v0.1.3.json`

**Fragment-first layout (current, from v0.2.0+):**
- Feature authors commit fragments to `.agentic/releases/unreleased/<slug>.json` on their feature/epic branch.
- At release time, `gh plate release cut vX.Y.Z` aggregates all fragments into `.agentic/releases/vX.Y.Z/` (a directory containing the consolidated record and the original fragments for traceability).

## Fragment schema (unreleased/<slug>.json)

Every unreleased fragment must include:

- `slug` — kebab-case identifier, unique within unreleased/ (e.g. `release-issue-type`)
- `change_type` — e.g. `feature`, `fix`, `docs`, `process`, `breaking`
- `surface` — affected template / workflow / docs surface
- `summary` — one-line description of the change
- `migration_impact` — what a downstream repo must do (required)
- `migration_guidance` — ordered list of concrete steps for upgrading (string or array of strings; preferred over prose-only migration_impact when steps are discrete)
- `agent_notes` — agent-friendly upgrade guidance

Optional fields:

- `breaking` — boolean
- `links` — related issue / PR references
- `requires` — dependency version(s) or prior note identifiers

## When to use migration_guidance

Use `migration_guidance` (array of steps) when the migration requires discrete, ordered actions.
Use `migration_impact` (prose) for a plain-English description of what changed.
Both fields serve different audiences: `migration_impact` for quick scanning, `migration_guidance` for unambiguous recipe execution by agents.

## Versioned release directories (vX.Y.Z/)

After `gh plate release cut vX.Y.Z`:
- `.agentic/releases/vX.Y.Z/` contains the aggregated release notes JSON + all contributing fragments.
- Agents can answer "what changed between my version and latest?" by diffing these directories.

## Rendering

Use `scripts/render_release_notes.py` to render a file or the entire directory into human-readable Markdown.
Use `scripts/render_release_migrations.py` to render an ordered migration guide between versions.

Both renderers support the `migration_guidance` field. When present, a **Migration steps** section is shown
prominently in the output so agents have an unambiguous action recipe.

## Example

See `v0.1.0.json` for a legacy flat-file record.
See `unreleased/release-issue-type.json` for a current fragment example with `migration_guidance`.
