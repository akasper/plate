# Migrating existing PLATE installations to docs/plate/

**Context:** Feature #1015 introduces automatic namespacing of PLATE documentation under `docs/plate/` when importing into repositories that have product documentation. This guide helps existing PLATE adopters migrate their installations.

## Prerequisites

Before migrating, ensure you have:

- **plate-core v0.8.3 or later** for the `migrate-docs-namespace` command, OR
- **Manual migration capability** (git, basic shell commands)
- **The `gh plate` CLI extension installed** (for the migration command)
  ```bash
  # Install the gh plate extension if needed
  gh extension install akasper/gh-plate
  
  # Or use the Python API directly
  pip install --upgrade plate-core
  python -m plate_core.cli migrate-docs-namespace [--apply]
  ```

## Who needs to migrate?

**You need to migrate if:**
- You already imported PLATE into your repository
- PLATE docs currently live at `docs/` root (design/, wiki/, research/, etc.)
- You have (or plan to have) product documentation under `docs/` that collides with PLATE scaffolding

**You can skip migration if:**
- Your repository has no `docs/` directory yet
- You have no product docs under `docs/` (only PLATE scaffolding)
- PLATE docs are already under `docs/plate/` (from a prior manual namespace)

## Decision tree

```
Do you have PLATE docs at docs/ root (design/, wiki/, etc.)?
├─ No → Skip migration, you're done
└─ Yes → Do you have product docs under docs/ too?
    ├─ No → You can keep PLATE at docs/ root (no namespace needed)
    └─ Yes → Migrate PLATE docs to docs/plate/
        ├─ Have plate-core v0.8.3+? → Use `gh plate migrate-docs-namespace`
        └─ Older version? → Use manual migration (Option B below)
```

## Migration checklist

Follow these steps in order:

### 1. Inventory your current docs/ structure

```bash
# List all top-level docs/ directories
ls -la docs/

# Identify what's PLATE scaffolding vs. product docs
# PLATE subdirs: adr/, audits/, bootstrap/, design/, marketing/, migration/, research/, wiki/
# PLATE root files are identified by template content, not filename alone:
#   README.md must contain "# Documentation Index" and "playwright-e2e-guide.md"
#   playwright-e2e-guide.md must contain the template title
#   "Playwright E2E Testing & Demo GIF Generation Guide"
# A product docs/README.md with different content is product docs and triggers namespacing.
# Everything else is product docs
```

### 2. Back up your current state

```bash
# Create a backup branch before starting
git checkout -b backup/pre-docs-namespace
git push origin backup/pre-docs-namespace
git checkout main  # or your working branch
```

### 3. Choose your migration path

**⚠️ IMPORTANT: The automatic re-import path is NOT SAFE for migration.**

`gh plate import-payload --namespace-docs` creates NEW files under `docs/plate/` but **does NOT move or remove** existing files from `docs/`. This leaves duplicates and does not preserve your customizations. The `--strategy force` flag will **overwrite your customized AGENTS.md** with the generic template.

**For safe migration, use the purpose-built migration command or manual migration.**

**Option A: Use the migration command (recommended, requires plate-core v0.8.3+)**

```bash
# Dry-run first to see what will be moved
gh plate migrate-docs-namespace

# Review the plan, then apply
gh plate migrate-docs-namespace --apply

# This will:
# - Use git mv to move PLATE doc directories: adr/, audits/, bootstrap/, design/, 
#   marketing/, migration/, research/, wiki/ → docs/plate/
# - Move PLATE root doc files (README.md, playwright-e2e-guide.md if they match templates)
# - Preserve AGENTS.md, SPEC.md, CURRENT.md and all product docs (never touched)
# - Rewrite references in repository files
# - Report any issues
# - Be idempotent (safe to re-run)
```

**Option B: Manual migration (always safe, works with any plate-core version)**

Use when:
- You don't have the migration command yet (plate-core < v0.8.3)
- You want full control over what moves where
- You have heavily customized content that needs review

```bash
# 1. Create the namespace directory
mkdir -p docs/plate

# 2. Move PLATE scaffolding directories
for dir in adr audits bootstrap design marketing migration research wiki; do
  if [ -d "docs/$dir" ]; then
    git mv "docs/$dir" "docs/plate/$dir"
  fi
done

# 3. Move PLATE root files (if present and not customized)
if [ -f "docs/README.md" ]; then
  # Review content first - if it's product docs, keep it at root
  git mv "docs/README.md" "docs/plate/README.md"
fi

if [ -f "docs/playwright-e2e-guide.md" ]; then
  git mv "docs/playwright-e2e-guide.md" "docs/plate/playwright-e2e-guide.md"
fi

# 4. Your product docs stay at docs/ root (no move needed)
# Examples: docs/api/, docs/tutorial/, docs/architecture/, etc.
```

### 4. Fix relative links in moved root files

If you moved `docs/README.md` to `docs/plate/README.md`, its relative links are now broken:

```bash
# Option: Manual sed rewrite (portable)
if [ -f "docs/plate/README.md" ]; then
  sed 's|(../|\.\./\.\./|g' docs/plate/README.md > docs/plate/README.md.tmp
  mv docs/plate/README.md.tmp docs/plate/README.md
  git add docs/plate/README.md
fi

# The file went one level deeper, so:
# - ../AGENTS.md becomes ../../AGENTS.md
# - ../tests/e2e/ becomes ../../tests/e2e/
# - ./playwright-e2e-guide.md stays the same (same-directory links are fine)
```

### 5. Rewrite references in repository files

After moving files and directories, update references throughout the repository. **Note:** The `migrate-docs-namespace` command does this automatically. For manual migration:

```bash
# Portable reference rewriting (works on macOS and Linux)
# Create a temporary rewrite script
cat > /tmp/rewrite-refs.sh << 'EOF'
#!/bin/sh
# Rewrite directory references
for dir in design research wiki audits migration bootstrap marketing adr; do
  sed "s|docs/$dir/|docs/plate/$dir/|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
  sed "s|\`docs/$dir/|\`docs/plate/$dir/|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
done

# Rewrite root file references (if you moved them)
sed "s|docs/playwright-e2e-guide\.md|docs/plate/playwright-e2e-guide.md|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
sed "s|docs/README\.md|docs/plate/README.md|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
sed "s|\`docs/playwright-e2e-guide\.md|\`docs/plate/playwright-e2e-guide.md|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
sed "s|\.\./docs/playwright-e2e-guide\.md|../docs/plate/playwright-e2e-guide.md|g" "$1" > "$1.tmp" && mv "$1.tmp" "$1"
EOF
chmod +x /tmp/rewrite-refs.sh

# Apply to key files (but NOT AGENTS.md, SPEC.md, CURRENT.md - review those manually)
/tmp/rewrite-refs.sh CONTRIBUTING.md
/tmp/rewrite-refs.sh README.md
# Add other files that reference docs

# Review changes
git diff
```

**Important:** Do NOT automatically rewrite `AGENTS.md`, `SPEC.md`, or `CURRENT.md`. Review those files manually for stale references, as they may contain critical product or process documentation that needs careful handling.

**Files to check for doc references:**
- `AGENTS.md` (review manually - do not auto-rewrite)
- `SPEC.md` (review manually - do not auto-rewrite)
- `CURRENT.md` (review manually - do not auto-rewrite)
- `CONTRIBUTING.md`
- `README.md`
- `.github/workflows/*.yml` (especially sync-wiki-on-merge.yml)
- `.github/ISSUE_TEMPLATE/*.yml`
- `.github/copilot-instructions.md`
- `.github/agents/*.agent.md`
- `.agentic/skills.yml`
- `scripts/README.md` or other script docs
- `scripts/bootstrap_github.sh` and `scripts/BootstrapGitHub.ps1` (may reference docs/wiki/Home.md)
- `.agentic/migration.yml` (may reference docs/migration/)
- Any custom markdown in `.agentic/`

Search command to find all references:
```bash
# Find all doc refs across the repo (excluding .git)
rg 'docs/(design|wiki|research|audits|migration|bootstrap|marketing|adr|playwright-e2e-guide|README)' \
  --type md --type yaml --type yml --type sh --type ps1 \
  | grep -v '^Binary'
```

### 5. Update wiki sync configuration (if applicable)

If you use `.github/workflows/sync-wiki-on-merge.yml`:

```yaml
# Update the workflow to sync from docs/plate/wiki/ instead of docs/wiki/
# Example change in sync-wiki-on-merge.yml:

# Before:
#   docs_dir: docs/wiki
  
# After:
#   docs_dir: docs/plate/wiki
```

### 6. Verify the migration

```bash
# 1. Check that PLATE scaffolding is under docs/plate/
ls -la docs/plate/
# Should see: adr/, audits/, bootstrap/, design/, marketing/, migration/, research/, wiki/
# Plus: README.md, playwright-e2e-guide.md (if they were PLATE's)

# 2. Check that product docs remain at docs/ root
ls -la docs/
# Should see your product dirs: api/, tutorial/, etc.
# Plus the new plate/ subdir

# 3. Verify no duplicates (old PLATE dirs should be gone from docs/ root)
for dir in adr audits bootstrap design marketing migration research wiki; do
  if [ -d "docs/$dir" ]; then
    echo "WARNING: docs/$dir still exists (should have moved to docs/plate/$dir)"
  fi
done

# 4. Verify no broken links
grep -r 'docs/\(design\|wiki\|research\|audits\|migration\|bootstrap\|marketing\|adr\)/' \
  AGENTS.md SPEC.md .github/ .agentic/ 2>/dev/null | grep -v 'docs/plate/' || echo "All refs updated"

# 5. Verify AGENTS.md was not overwritten (check git log)
git log -1 --stat AGENTS.md
# Should only show reference updates, not a complete rewrite

# 6. Test workflows
git add -A
git commit -m "Migrate PLATE docs to docs/plate/ namespace"
# Push to a test branch and verify CI passes

# 7. Run PLATE health check (plate-core v0.8.3+)
gh plate health
# Or: python -m plate_core.cli health
```

### 7. Update open pull requests

If you have open PRs that reference old paths:

```bash
# List open PRs
gh pr list --state open

# For each PR, either:
# A. Rebase/merge main (with migration) into the PR branch, OR
# B. Manually update references in that branch

# Example for a PR branch:
git checkout pr-branch-name
git merge main  # brings in the migration
# Fix any conflicts
git push
```

## Important notes

- **Only `docs/` paths are affected.** This migration does not touch CI, workflows (beyond reference updates), or any code.
- **AGENTS.md, SPEC.md, and CURRENT.md are never moved or overwritten** by the migration command. Only their internal path references are updated.
- **Product documentation stays at `docs/` root.** Only PLATE scaffolding moves to `docs/plate/`.
- **The migration is idempotent.** Running it multiple times is safe.

## Edge cases and special situations

### Mixed product + PLATE docs trees

**Scenario:** You have product docs like `docs/api/` alongside PLATE's `docs/design/`.

**Solution:** 
- Move only PLATE subdirs (adr, audits, bootstrap, design, marketing, migration, research, wiki) to `docs/plate/`
- Keep product subdirs (`api/`, `tutorial/`, etc.) at `docs/` root
- After migration: `docs/api/` and `docs/plate/design/` coexist peacefully
- The migration command handles this automatically

### Customized wiki pages

**Scenario:** You've edited PLATE wiki templates (Goals.md, Home.md) with project-specific content.

**Solution:**
- Use **manual migration** (Option B above)
- Review each wiki page before moving: `git diff docs/wiki/Goals.md`
- If heavily customized, consider:
  - Moving to `docs/plate/wiki/` but marking as customized
  - Keeping a copy at product docs location for discoverability
  - Documenting the split in a comment at the top of each file

### Open PRs referencing old paths

**Scenario:** Open PRs have AGENTS.md changes or workflow edits pointing to `docs/design/`, etc.

**Solution:**
1. Merge the migration PR to main first
2. For each open PR:
   ```bash
   git checkout pr-branch
   git rebase main  # or merge main
   # Resolve path conflicts (docs/design/ → docs/plate/design/)
   git push --force-with-lease
   ```
3. Alternatively, ask contributors to update their branches after migration lands

### CI / wiki sync workflows

**Scenario:** Your CI references `docs/wiki/` in sync jobs or deploys.

**Solution:**
- Update workflow files to use `docs/plate/wiki/` (see step 5 above)
- Update any external doc deployment scripts
- Test the full CI pipeline on a test branch before merging

Example workflow change:
```yaml
# .github/workflows/sync-wiki-on-merge.yml
- name: Sync to wiki
  run: |
    # Before: cp -r docs/wiki/* .wiki/
    # After:
    cp -r docs/plate/wiki/* .wiki/
```

### Already using docs/plate/ manually

**Scenario:** You manually namespaced PLATE docs before this feature existed.

**Solution:** 
- No migration needed!
- Verify your paths match the new standard (all PLATE under `docs/plate/`)
- Re-import with `--namespace-docs` to get reference rewrites and consistency

### Fresh import after migration

**Scenario:** You want to pull updated PLATE scaffolding after migrating.

**Solution:**
```bash
# With product docs present and docs already migrated to docs/plate/:
gh plate import-payload --namespace-docs --strategy safe --apply

# This will:
# - Install new/updated PLATE files under docs/plate/
# - Skip files that already exist (safe strategy)
# - NOT move your existing files (use migrate-docs-namespace for that)
```

**Warning:** `import-payload` does NOT migrate existing files. It only creates new ones. Use `migrate-docs-namespace` to move existing PLATE docs from `docs/` to `docs/plate/`.

## Rollback procedure

If migration causes issues:

```bash
# 1. Revert to backup branch
git checkout backup/pre-docs-namespace

# 2. Create a new working branch
git checkout -b fix/docs-namespace-issues

# 3. Cherry-pick specific fixes if needed
git cherry-pick <commit-hash>

# 4. Or start fresh migration with refined approach
```

## Verification checklist

After migration, verify:

- [ ] All PLATE scaffolding under `docs/plate/` (adr, audits, bootstrap, design, marketing, migration, research, wiki)
- [ ] Product docs remain at `docs/` root (unchanged)
- [ ] AGENTS.md references updated (grep for old paths)
- [ ] Workflow files updated (especially wiki sync)
- [ ] Issue templates updated if they reference docs
- [ ] CI passes on migration branch
- [ ] `gh plate health` reports no issues (if available)
- [ ] Wiki sync still works (if enabled)
- [ ] No 404s when clicking doc links in README or AGENTS.md
- [ ] Open PRs rebased or merged to pick up new paths

## Getting help

If you encounter issues during migration:

1. Check this guide's edge cases section
2. Review the PR discussion: #1016
3. Open a Question issue: `gh issue create --label Question --title "docs/plate migration: [your question]"`
4. Reference the original feature issue: #1015

## Related documentation

- Feature implementation: PR #1016
- Original issue: #1015
- Script namespacing pattern (similar concept): #621
- Import payload guide: `docs/bootstrap/new-repository-checklist.md` (if present)
- Release fragment: `.agentic/releases/unreleased/namespace-docs-on-import.json`
