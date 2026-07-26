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
