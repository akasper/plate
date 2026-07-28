# Adopting PLATE into an existing repository

Use this guide when **adding PLATE to a mature codebase** (not a brand-new repo from the PLATE template).

Greenfield path: `docs/bootstrap/new-repository-checklist.md`.

Epic #633 targets a healthy PLATE state in **under 30 minutes** of mostly automated work. The steps below are the durable operator path; agents follow the same sequence via `plate_what_next` / feed process items.

## Recommended sequence (<30m)

0. **Start wall-clock session (optional but recommended, #955)**  
   ```bash
   gh plate adopt --start-session --json
   ```
   Records `started_at` under `.agentic/adoption/session.json`.  
   MCP: `plate_adoption_session` with `action=start`.  
   While the session is active, `plate_what_next` ranks priority `adoption_session` (#957).

1. **Readiness status (status only, #935)**  
   ```bash
   gh plate adopt --json
   gh plate health --json   # also exposes adoption_core_ready / first_qa_seeded (#953)
   ```
   Machine-checkable checklist: `.plate`, `AGENTS.md`, Goals wiki, `.agentic/releases`,
   labels/plate workflows, optional SPEC/CURRENT.  
   Reports `estimated_minutes_remaining`, `within_30m_budget`, `next_command`, and `first_qa`.  
   MCP: `plate_adoption_status`. Does **not** apply changes.

2. **Local payload (reviewable diffs)**  
   ```bash
   gh plate import-payload --dry-run --strategy conservative --json
   # Follow report.next_command (usually --apply same strategy; conflicts → escape-hatch)
   gh plate import-payload --apply --strategy conservative
   ```
   Prefer `conservative` so differing existing files become conflicts (not silent skips/overwrites).
   Use `safe` to skip any existing path; `force` only with explicit human approval.
   JSON reports include a single **`next_command`** for agents (#996) — do not invent force-apply.

3. **GitHub-side baseline**  
   ```bash
   gh plate bootstrap --repo OWNER/REPO --adopt --apply
   ```
   Adoption mode (auto-detected or `--adopt`):
   - Prefer local import for file payload; remote copy still skips existing Contents paths.
   - Skips seeding a duplicate initial Epic when open Epics already exist.
   - Skips starter Questions when open Questions already exist; on apply, syncs
     `.agentic/adoption/first_qa_seed.json` when Questions are present (#951).
   - Emits adoption-tailored next steps (Goals.md, CODEOWNERS, CI coexistence, migrate plan).

4. **First Q&A seed (if not already seeded, #949 / #1001)**  
   ```bash
   gh plate adopt --first-qa-plan --json
   # Dry-run next_command points at apply (do not re-plan in a loop):
   gh plate adopt --first-qa-plan --apply-first-qa --json   # requires injectable runner
   ```
   Plans three starter Curiosity Questions (same catalog as bootstrap).  
   Live create requires an injectable runner / bootstrap `--apply` path; CLI alone does not open issues.  
   MCP: `plate_adoption_first_qa_plan`.  
   Offline marker: `.agentic/adoption/first_qa_seed.json`.

5. **Health + intent**  
   ```bash
   gh plate health --json
   gh plate config show
   gh plate adopt --json
   gh plate feed --json          # adoption* process items rank high (#959)
   gh plate what-next --json     # or plate_what_next
   ```
   Write real mission text in `docs/wiki/Goals.md`. Replace CODEOWNERS placeholders.

6. **Self-migrate verify (#649 / #965)**  
   ```bash
   gh plate self-migrate --plan --json
   gh plate self-migrate --verify --json
   ```
   Offline post-migrate checks: pin/payload drift, adoption `core_ready`, `.plate` validity.  
   Health also exposes `self_migrate_ready` / `self_migrate_drift` (#967).  
   MCP: `plate_self_migrate_verify`.

7. **Complete session timer (#955 / #1003)**  
   ```bash
   gh plate adopt --session-status --json
   gh plate adopt --complete-session --json
   # Follow report.next_command: first-qa-plan if unseeded; feed only when first_qa_seeded
   ```
   Records `duration_minutes` and `within_30m` against the 30-minute budget.  
   Does **not** jump to feed when `core_ready` but first Q&A is still unseeded (#1003).  
   This is **local proof evidence**, not a claim that every monorepo finished live E2E.

8. **Optional cutover**  
   If the repo was previously template-derived: `gh plate migrate plan` then review before apply.  
   Self-migrate pin/payload drift: `gh plate self-migrate --plan --json` (#649).

## Success signals (do not re-check #654 boxes without live E2E)

| Signal | How to read |
|---|---|
| `core_ready` | `gh plate adopt --json` / health `adoption_core_ready` |
| `first_qa_seeded` | adopt `first_qa.seeded` / health `first_qa_seeded` / marker file |
| Session `within_30m` | `gh plate adopt --complete-session --json` |
| Self-migrate `ready` | `gh plate self-migrate --verify --json` / health `self_migrate_ready` |
| Feed / what_next | No longer stuck on `adoption` / `adoption_session` / `first_qa_seed` / `self_migrate*` |

## Auto-detect

`gh plate bootstrap` sets `adoption_mode` when heuristics fire (e.g. missing `.plate` plus local CI/package.json, open issues, open Epics/Questions). Force with `--adopt` / `--existing-repo`, or force greenfield with `--greenfield`.

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

## Related issues

- #935 adoption readiness status (`gh plate adopt` / `plate_adoption_status`)
- #937 what_next ranks incomplete adoption
- #949 first Q&A seed plan
- #951 bootstrap writes/syncs first_qa marker
- #953 health exposes adoption fields
- #955 adoption session wall-clock timer
- #957 what_next ranks active session
- #959 feed ranks adoption process items
- #619 adoption mode
- #616 / #620 import-payload + shared planner
- #633 frictionless onboarding epic
- #649 self-migrate for adopters
