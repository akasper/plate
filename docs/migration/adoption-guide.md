# Adopting PLATE into an existing repository

Use this guide when **adding PLATE to a mature codebase** (not a brand-new repo from the PLATE template).

Greenfield path: `docs/bootstrap/new-repository-checklist.md`.

## Recommended sequence

1. **Local payload (reviewable diffs)**  
   ```bash
   gh plate import-payload --dry-run --strategy conservative --json
   gh plate import-payload --apply --strategy conservative
   ```
   Prefer `conservative` so differing existing files become conflicts (not silent skips/overwrites). Use `safe` to skip any existing path; `force` only with explicit human approval.

2. **GitHub-side baseline**  
   ```bash
   gh plate bootstrap --repo OWNER/REPO --adopt --apply
   ```
   Adoption mode (auto-detected or `--adopt`):
   - Prefer local import for file payload; remote copy still skips existing Contents paths.
   - Skips seeding a duplicate initial Epic when open Epics already exist.
   - Skips starter Questions when open Questions already exist.
   - Emits adoption-tailored next steps (Goals.md, CODEOWNERS, CI coexistence, migrate plan).

3. **Health + intent**  
   ```bash
   gh plate health
   gh plate config show
   ```
   Write real mission text in `docs/wiki/Goals.md`. Replace CODEOWNERS placeholders.

4. **Optional cutover**  
   If the repo was previously template-derived: `gh plate migrate plan` then review before apply.

## Auto-detect

`gh plate bootstrap` sets `adoption_mode` when heuristics fire (e.g. missing `.plate` plus local CI/package.json, open issues, open Epics/Questions). Force with `--adopt` / `--existing-repo`, or force greenfield with `--greenfield`.

## Related issues

- #619 adoption mode
- #616 / #620 import-payload + shared planner
- #633 frictionless onboarding epic

## Conflict strategies (manifest path_rules)

Import decisions are driven by `template_payload_manifest.yml` `path_rules` (#617), e.g.:

- Existing `.github/workflows/ci.yml` → install PLATE process as `.github/workflows/plate-ci.yml` (product CI preserved).
- Root `package.json` / `SPEC.md` / `README.md` → **conflict** (human merge).
- `.github/labels.yml` and issue templates → **overwrite** (PLATE taxonomy).

Dry-run shows `create_as` / `conflict` / `skip` per file. Customize rules only in a deliberate fork.

## CURRENT.md seeding

`gh plate import-payload` seeds a minimal `CURRENT.md` when missing (#618) so
`validate_plate_repo` and feature detection do not fail after adopt. Prefer
durable evidence in `.agentic/releases/`; treat CURRENT.md as a short index.

## scripts/plate convention

When the target already has product scripts under `scripts/`, import installs
PLATE helpers under `scripts/plate/` and rewrites workflow references (#621).
Discover payload files with `gh plate payload list --json`.
