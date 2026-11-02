# Upstream Template Sync

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Upstream PLATE Template Synchronization

<!-- PLATES-CORE:BEGIN upstream-template-sync -->
Downstream PLATE repositories often customize baseline files such as `AGENTS.md`, `.agentic/skills.yml`, and workflow definitions.

**Do not create, clone, fork, or `gh repo create --template` from `akasper/plate_template` or any template repository.** That GitHub template is retired. Never hand-copy PLATE payload files into a target repo. Start new repositories only via **`docs/bootstrap/starting-a-new-repository.md`** (`gh plate bootstrap` / `gh plate import-payload`).

Upgrade and sync scaffold behavior through **`plate-core`** (`gh plate import-payload`, `gh plate self-migrate`, and related surfaces)—not a `plate_template` git remote.

Do not overwrite customized files wholesale during upgrades.

Use **sectional synchronization** for core behavior updates:

1. Plan upgrades with `gh plate self-migrate --plan` (use `--verify` after apply).
2. Import scaffold files with `gh plate import-payload` (dry-run first; pick a safe strategy).
3. For marker-owned files, merge only upstream `PLATES-CORE` blocks (via `gh plate self-migrate` marker merge or manual sectional import).
4. Open an atomic PR labeled `Feature` (or `Documentation` for doc-only syncs) and include `Closes #N` when tied to an issue.
5. Update per-feature change files in `.agentic/releases/` with the imported behavior and evidence links.
6. Run the repository's required checks before requesting review.

Marker format for sync-safe blocks:

```md
<!-- PLATES-CORE:BEGIN block-id -->
... upstream-owned content ...
<!-- PLATES-CORE:END block-id -->
```

When introducing new reusable process guidance, wrap it in a `PLATES-CORE` block so downstream repositories can apply low-friction partial merges without losing local customizations.
<!-- PLATES-CORE:END upstream-template-sync -->
