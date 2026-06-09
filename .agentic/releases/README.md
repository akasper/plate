# PLATE release notes

This directory is the machine-readable source of truth for PLATE release notes.

## Directory layout

```
.agentic/releases/
  v0.1.0.json                  # legacy flat-file records (backward-compat)
  v0.1.4.json
  v0.2.0/                      # versioned release directory (current layout)
    release.json               #   consolidated release record
    fragments/                 #   contributing fragments (moved at release time)
  unreleased/                  # fragments not yet associated with an epic
    <slug>.json
  epic-<NNN>-<slug>/           # per-epic fragment directory (optional)
    <slug>.json
```

### Fragment sources

When cutting a release, `scripts/cut_release.py` collects fragments from two places (in order):

1. **`unreleased/`** — fragments for changes that do not belong to a specific epic.
2. **`epic-<NNN>-<slug>/`** — per-epic directories. Name the directory after the GitHub issue
   number and a short slug (e.g. `epic-123-delete-boondoggles/`). After the release is cut,
   empty epic directories are removed automatically.

## Cutting a release

### Auto-detected version (recommended)

```sh
# Let the tool infer the next version from the current baseline + fragment types:
python scripts/cut_release.py

# Override the bump type (patch / minor / major):
python scripts/cut_release.py --version-type minor

# Preview without writing anything:
python scripts/cut_release.py --dry-run
```

The tool determines the next version by:
1. Finding the highest semver in this directory (flat files, versioned dirs) and in git tags.
2. Inferring the bump type from the pending fragments:
   - Any `breaking: true` → **major**
   - Any `change_type: "feature"` → **minor** (when no breaking changes)
   - Otherwise → **patch**

### Explicit version

```sh
python scripts/cut_release.py v0.3.0
# or via the gh plugin:
gh plate release cut v0.3.0
```

### User override

When the auto-detected version is wrong, pass an explicit version on the command line.
The tool will use it verbatim and note when it differs from the inferred version.

### After cutting

1. Review `vX.Y.Z/release.json` and adjust the `summary` field if needed.
2. Commit the new `vX.Y.Z/` directory (fragments have already been moved).
3. Open a PR: `release` → `main`.
4. Ensure the Release PR passes the version-sync and remote tag-conflict checks.
5. After merge, the Release workflow creates and pushes `vX.Y.Z` from the merged Release PR commit.
6. Hard-reset the release branch:
   `git checkout release && git reset --hard vX.Y.Z && git push --force-with-lease`

## Fragment schema

Every fragment file must include:

| Field | Required | Description |
|---|---|---|
| `slug` | ✅ | Kebab-case identifier, unique within its source directory |
| `change_type` | ✅ | `feature`, `fix`, `docs`, `process`, or `breaking` |
| `surface` | ✅ | Affected template / workflow / docs surface |
| `summary` | ✅ | One-line description of the change |
| `migration_impact` | ✅ | Prose: what a downstream repo must do |
| `agent_notes` | ✅ | Agent-friendly upgrade guidance |
| `migration_guidance` | — | Array of ordered steps for unambiguous upgrade recipe |
| `breaking` | — | `true` if downstream repos break without migration |
| `links` | — | Related issue / PR references |
| `requires` | — | Dependency version(s) or prior note identifiers |

Use `migration_guidance` (array) when the migration requires numbered, ordered actions.
Use `migration_impact` (prose) for a quick human-readable summary.
Both fields serve different readers: `migration_impact` for scanning, `migration_guidance`
for precise agent execution.

## Rendering migration guidance

```sh
# All versions:
python scripts/render_release_migrations.py .agentic/releases

# Specific range:
python scripts/render_release_migrations.py .agentic/releases --from-version 0.1.3 --to-version 0.2.0

# Auto-detect the from-version from a downstream repo:
python scripts/render_release_migrations.py .agentic/releases \
    --auto-from ../my-downstream-repo/.agentic/releases
```

The `--auto-from` flag reads the downstream repo's own releases directory to determine
its current PLATE baseline, so you no longer need to know the exact version manually.

## Examples

See `v0.1.0.json` for a legacy flat-file record.
See `unreleased/release-issue-type.json` for a fragment with `migration_guidance`.
