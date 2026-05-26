# Automatic Epic Creation

> **Status:** Research complete — awaiting human decision.  
> **Issue:** #28  
> **Full analysis:** [`docs/research/automatic-epic-creation.md`](../research/automatic-epic-creation.md)

## Summary

When a Feature issue references an `Epic: short-name` label that doesn't yet exist, the system should automatically create both the label and a stub Epic issue. This eliminates the friction of requiring manual Epic administration before Feature work can begin.

## Recommended Approach

**Option B — Free-form field with workflow-driven auto-creation.**

A GitHub Actions workflow fires on `issues: [opened]` and:

1. Parses the `Epic traceability label` field from the issue body.
2. Validates the label slug against the naming convention (`/^[a-z0-9][a-z0-9-]{1,38}$/`).
3. Creates the `Epic: short-name` label if it doesn't exist.
4. Applies the label to the triggering issue.
5. If the issue is a Feature and no matching open Epic issue exists, creates a stub Epic with `need:decision` label.

## Options Considered

| Option | Description | Verdict |
|---|---|---|
| A — Dropdown | Static YAML list of existing Epics in the template | Rejected: GitHub forms don't support dynamic dropdowns; requires manual maintenance |
| B — Auto-Create | Free-form input + workflow that creates label/Epic on demand | **Recommended**: lowest friction, agent-compatible, moderate complexity |
| C — Hybrid | Free-form with suggestion hints + naming guard + auto-create | Future enhancement if sprawl becomes an issue |
| D — Status Quo | Fully manual label and Epic management | Rejected: high friction, blocks autonomous workflows |

## Key Design Decisions (Pending Human Input)

1. Naming convention: lowercase-hyphenated slugs only (e.g., `Epic: my-area`)
2. Trigger scope: `opened` events only, or also `edited`?
3. Stub Epic sign-off: Require `need:decision` label clearance before Features proceed?
4. Permission boundary: Limit auto-creation to collaborators?

## Implementation Artifact

The workflow implementation sketch is included in the full research document. Estimated effort: ~50 lines of `actions/github-script` in a new `.github/workflows/epic-auto-create.yml` file.
