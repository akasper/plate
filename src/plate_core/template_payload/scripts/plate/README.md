# `scripts/plate/` — PLATE-owned helper scripts

**Convention (#621):** PLATE supporting scripts install under `scripts/plate/` when
adopting into a repo that already has a product `scripts/` tree, so project
scripts and PLATE helpers do not collide.

Greenfield template clones may still place scripts at top-level `scripts/` for
backward compatibility with older docs; `gh plate import-payload` auto-detects
an existing product `scripts/` and namespaces into `scripts/plate/`.

## Discoverability

```bash
gh plate payload list --json
gh plate payload root
gh plate payload classify scripts/validate_plate_repo.sh
gh plate import-payload --dry-run --namespace-scripts
```

Workflows written during a namespaced import rewrite `scripts/<name>` references
to `scripts/plate/<name>` for known PLATE helpers.
