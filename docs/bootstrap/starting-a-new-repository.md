# Starting a new repository

PLATE scaffold ships in **`plate-core`** and the **`gh plate`** extension. Do not use GitHub's "Use this template" on `akasper/plate_template` or any other template repo.

## Install (once per machine)

Pin the same version for Python and the extension (see root `README.md` for the current pin):

```bash
pip install -U 'plate-core==0.8.7'
python3 -c "import plate_core; print(plate_core.__version__)"

gh extension install akasper/gh-plate    # or: gh extension upgrade plate
```

## Greenfield: empty GitHub repository

1. Create an **empty** repo (no template):

   ```bash
   gh repo create OWNER/NAME --private
   ```

   Never pass `--template` or fork `akasper/plate_template`.

2. Clone it (or `cd` into your local root) and plan bootstrap:

   ```bash
   gh plate bootstrap --repo OWNER/NAME --greenfield
   ```

3. Apply when the plan looks right:

   ```bash
   gh plate bootstrap --repo OWNER/NAME --greenfield --apply
   ```

`gh plate bootstrap --apply` is **required** for adoption: it materializes the scaffold, applies the canonical label set, seeds starter issues, and writes baseline `.plate` / GitHub settings per project policy (#1193). Dry-run (no `--apply`) is the default.

Follow **[new-repository-checklist.md](./new-repository-checklist.md)** for human decisions after bootstrap.

## Existing local codebase

Add PLATE without replacing your product code:

1. Plan import (default is dry-run):

   ```bash
   gh plate import-payload --strategy conservative
   ```

2. Apply:

   ```bash
   gh plate import-payload --strategy conservative --apply
   ```

3. Finish GitHub-side adoption:

   ```bash
   gh plate bootstrap --adopt --apply
   ```

See **[adoption-guide.md](../migration/adoption-guide.md)** for readiness checks and the full under-30m sequence.

## Agents

Never clone, fork, or `gh repo create --template` from `plate_template` (or hand-copy files from `src/plate_core/template_payload/`). Use **`gh plate bootstrap`** and **`gh plate import-payload`** only.
