# PLATE unreleased fragments

This directory holds release-note fragments that are **not yet tied to a specific epic**.

If your change is part of a named epic, author the fragment in a dedicated
`epic-<NNN>-<slug>/` directory at the same level as `unreleased/` instead
(e.g. `.agentic/releases/epic-123-delete-boondoggles/my-change.json`).
Both sources are aggregated identically when `cut_release.py` runs.

## Fragment contract

**When to author a fragment:**
Create a fragment for any Feature or Epic PR that changes PLATE process, templates,
agent surfaces, or tooling. Skip for pure documentation fixes or chores that don't affect
downstream repos.

**File name:** `<slug>.json` — kebab-case, unique in this directory.

**Required fields:**

| Field | Description |
|---|---|
| `slug` | Kebab-case identifier, unique within this directory. |
| `change_type` | `feature`, `fix`, `docs`, `process`, `breaking` |
| `surface` | Affected template / workflow / docs surface |
| `summary` | One-line description |
| `migration_impact` | Prose: what a downstream repo must do |
| `agent_notes` | Agent-friendly upgrade guidance |

**Optional fields:**

| Field | Description |
|---|---|
| `migration_guidance` | Array of ordered steps for unambiguous upgrade recipe. Prefer an array when steps are discrete. |
| `breaking` | Boolean — `true` if downstream repos break without migration |
| `links` | Related issue / PR references |
| `requires` | Dependency version(s) |

## When to use migration_guidance

Use `migration_guidance` (array) when the migration requires numbered, ordered actions.
Use `migration_impact` (prose) for a quick summary.
Both fields serve different readers: `migration_impact` for human scanning,
`migration_guidance` for precise agent execution.

## Example

```json
{
  "slug": "my-feature",
  "change_type": "feature",
  "surface": ".github/ISSUE_TEMPLATE/feature.yml",
  "summary": "Adds a required acceptance-criteria field to the Feature template.",
  "migration_impact": "Feature issue template gains a required 'acceptance_criteria' field.",
  "migration_guidance": [
    "1. Copy the updated .github/ISSUE_TEMPLATE/feature.yml into your repo.",
    "2. Existing open Feature issues are not affected -- only new issues use the new template.",
    "3. Update any agent prompts that construct Feature issue bodies programmatically."
  ],
  "agent_notes": "When opening Feature issues, always populate the acceptance_criteria field.",
  "breaking": false,
  "links": ["#42"],
  "requires": ["0.1.3"]
}
```

## Aggregation

At release time, run:
```sh
# Auto-detect the next version (recommended):
python scripts/cut_release.py

# Override the bump type:
python scripts/cut_release.py --version-type minor

# Explicit version:
python scripts/cut_release.py vX.Y.Z
# or: gh plate release cut vX.Y.Z
```

This moves all fragments here (and in any `epic-*/` directories) into
`.agentic/releases/vX.Y.Z/fragments/` and writes a consolidated
`.agentic/releases/vX.Y.Z/release.json`.

The version is determined automatically from:
- the highest semver in `.agentic/releases/` (flat files, versioned dirs) or git tags, and
- the fragment types (`breaking: true` → major, `feature` → minor, otherwise patch).
