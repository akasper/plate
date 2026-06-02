# Release Notes Validation

## Scenario

Validate a downstream PLATE upgrade from `0.1.0` to `0.1.1` using the structured release-note directory and the migration renderer.

## Input

```bash
python scripts/render_release_migrations.py .agentic/releases --from-version 0.1.0 --to-version 0.1.1
```

## Result

The renderer produced ordered guidance for `v0.1.1` and surfaced the release-note dependencies back to `0.1.0`.

## Gaps (now resolved)

- **Manual from/to versions** — The renderer required the operator to supply versions manually.
  **Resolved** by `--auto-from <downstream-releases-dir>`: the tool now reads the downstream
  repo's own `.agentic/releases/` directory to detect its current PLATE baseline automatically.

  ```bash
  python scripts/render_release_migrations.py .agentic/releases \
      --auto-from ../my-downstream-repo/.agentic/releases
  ```

- **Manual version when cutting** — `cut_release.py` required an explicit version argument.
  **Resolved**: the tool now auto-detects the current baseline from versioned files / git tags
  and infers the bump type (patch / minor / major) from the fragment metadata. Pass
  `--version-type` to override the inferred bump, or supply an explicit version as before.

  ```bash
  python scripts/cut_release.py            # fully automatic
  python scripts/cut_release.py --version-type major
  python scripts/cut_release.py v1.0.0     # explicit override
  ```

- **Epic fragment organisation** — All fragments lived in `unreleased/` regardless of origin.
  **Resolved**: fragments for a specific epic can now be authored in a dedicated
  `epic-<NNN>-<slug>/` directory. These directories are collected automatically when cutting
  a release and are removed when emptied.

## Follow-up

No remaining blockers. Issue #178 is resolved.
