# Release Notes Validation

## Scenario

Validate a downstream PLATE upgrade from `0.1.0` to `0.1.1` using the structured release-note directory and the migration renderer.

## Input

```bash
python scripts/render_release_migrations.py .agentic/releases --from-version 0.1.0 --to-version 0.1.1
```

## Result

The renderer produced ordered guidance for `v0.1.1` and surfaced the release-note dependencies back to `0.1.0`.

## Gaps

- The renderer still depends on the operator to choose the current and target versions.
- Release-note entries describe the migration impact, but they do not yet emit file-level edit instructions for downstream repos.

## Follow-up

- Opened follow-up issue #178 to investigate automatic baseline detection for downstream upgrades.
