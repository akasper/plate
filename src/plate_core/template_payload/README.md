# PLATE Template

`plate_template` is the canonical starter repository for the **Process Lifecycle Agentic Task Engine (PLATE)** methodology.

PLATE is a GitHub-first delivery model where:

- **Humans keep judgment** (scope, risk, approvals, releases).
- **Agents do the toil** (implementation, docs, triage, repetitive operations).
- **GitHub holds truth** (issues, labels, PRs, checks, `SPEC.md`, `CURRENT.md`, wiki artifacts).

## What a PLATE project is

A PLATE project is a repository that uses typed work items and durable artifacts to keep autonomous work reviewable and reversible.

Core characteristics:

- Typed issue taxonomy (`Feature`, `Bug`, `Research`, `Design`, `Question`, etc.).
- Epic traceability via `Epic: short-name` labels.
- PR type labels (`Feature`, `Bug`, `Documentation`, `Feedback Response`).
- Required evidence updates (`CURRENT.md`, docs, tests) aligned to issue type.
- Guardrails in workflows for label validity, issue linkage, and documentation quality.

See `AGENTS.md` for the full operating doctrine and authority model.

## Project truth model

PLATE separates future intent from present reality:

- **`SPEC.md`** describes desired future state (vision, users, goals, constraints).
- **`CURRENT.md`** describes what is actually implemented and verified today.

If a claim is not supported by `CURRENT.md`, it should be treated as planned work.

## Getting started: PLATE onboarding

### 1. Create your repository from this template

Use GitHub's "Use this template" flow to create a new repository.

### 2. Run repository bootstrap

From the new repository root:

**macOS / Linux / WSL**
```bash
bash scripts/bootstrap_github.sh --repo OWNER/REPO --local-repo . --owner-handle @your-handle --remove-default-labels --set-delete-branch-on-merge --protect-branch main
```

**Windows (PowerShell)**
```powershell
.\scripts\BootstrapGitHub.ps1 -Repo OWNER/REPO -LocalRepo . -OwnerHandle @your-handle -RemoveDefaultLabels -SetDeleteBranchOnMerge -ProtectBranch main
```

Both bootstrap scripts run a runtime-aware local toolchain preflight (`scripts/check_toolchain.sh` or `scripts/CheckToolchain.ps1`) before GitHub mutations.

See `docs/bootstrap/new-repository-checklist.md` for what is automated vs. what still requires human decisions.

### 3. Answer the onboarding questions

Use the default PLATE onboarding question set to establish durable project context:

1. Project identity and purpose
2. New project vs migration
3. Primary users and outcome
4. Team size / operating model
5. Preferred stack and deployment target
6. Notification and budget posture
7. Testing posture
8. First Epic and first Feature

Reference: `docs/design/default-questions.md`.

### 4. Create first Epic labels and starter issues

Create 1-3 real `Epic: short-name` labels, then open your first Epic and Feature issues using the repository templates.

### 5. Ship the first atomic PR

Open a small PR with:

- one PR type label,
- closing keyword (`Closes #N`),
- updated evidence (`CURRENT.md` and/or docs/tests as required by issue type).

## Testing with Playwright E2E

This repository includes end-to-end testing with Playwright and automatic demo GIF generation for documentation.

- **Run tests:** `npm run test:e2e`
- **Record demo:** `./scripts/e2e-record.sh feature-name --headed`
- **Docs:** [Playwright E2E Guide](docs/playwright-e2e-guide.md)
- **Wiki:** [Feature Showcase](docs/wiki/feature-showcase.md), [E2E Testing](docs/wiki/playwright-e2e.md)
- **Adoption:** [Forward-Port Guide](docs/forward-port-plans/playwright-e2e-adoption.md)

See [`docs/README.md`](docs/README.md) for complete documentation index.

## Repository map

- `AGENTS.md` - operating rules and authority boundaries
- `SPEC.md` - future-state product intent
- `CURRENT.md` - implemented-state record
- `CONTRIBUTING.md` - contributor expectations and traceability rules
- `.agentic/` - machine-readable process and skill metadata
- `docs/` - documentation index and guides
- `docs/bootstrap/` - new repo setup guidance
- `docs/design/`, `docs/research/`, `docs/wiki/` - durable artifacts
- `.github/workflows/` - enforcement and automation checks

## Keeping Your Fork Current

If your repository started from an older `plate_template` release and has local process customizations, avoid full-file replacement during upgrades.

<!-- PLATES-CORE:BEGIN keeping-your-fork-current -->
Use this sync flow:

1. Fetch upstream template updates (`git fetch upstream`) and review diffs for `AGENTS.md`, `.agentic/skills.yml`, `CURRENT.md`, and workflows in `.github/workflows/` that contain `PLATES-CORE` markers.
2. Import only upstream-owned `PLATES-CORE` sections into your customized files.
3. Preserve local sections outside those markers.
4. Open an atomic PR with the correct PR type label and issue linkage (`Closes #N` when applicable).
5. Update your `CURRENT.md` entry with imported behavior and evidence.
6. Run required checks before merge.

This keeps downstream repos aligned with new core PLATE behavior without erasing project-specific policy.
<!-- PLATES-CORE:END keeping-your-fork-current -->
