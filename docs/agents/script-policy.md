# Script Policy

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Script Policy and Platform Support

**Default:** PLATE repositories use **POSIX shell (`.sh`) scripts only**. Do not create parallel PowerShell (`.ps1`) twins unless the project explicitly declares Windows support.

**Platform support tiers:**

1. **Default (no platform stated, or Unix-first / cross-platform without explicit Windows):** Ship **shell scripts only** (`.sh`). Do not require or invent parallel `.ps1` scripts.

2. **Windows supported (developer explicitly states):** Keep shell scripts as primary **and also** provide PowerShell equivalents where operators need them (dual-stack). Both `.sh` and `.ps1` must implement the same behavior.

3. **Windows-only (developer explicitly states):** PowerShell is sufficient; POSIX/shell scripts **may be eschewed**.

**Determining platform support:** Platform support must come from **human-stated project intent** in one of these sources:
- `SPEC.md` or project documentation
- `.plate` configuration (`platform`: `posix` | `posix-and-windows` | `windows`; a missing key means `posix`)
- Onboarding answers or bootstrap configuration
- Explicit instruction during repository setup

**Never infer platform support** from:
- The developer's laptop operating system
- The presence of Windows-specific dependencies
- CI/CD platform choices

**Agent responsibilities:**
- When creating new scripts, check project platform support first
- For default projects (no explicit Windows support): create `.sh` only
- For Windows-supported projects: create both `.sh` (primary) and `.ps1` (equivalent)
- For Windows-only projects: create `.ps1` only
- When modifying existing scripts, maintain consistency with the project's declared platform support

**`.plate` platform:** Set `platform` to `posix` (the default when the key is absent), `posix-and-windows`, or `windows`. `gh plate import-payload` and `gh plate bootstrap --apply` copy PLATE-owned scripts for that value. `posix` omits PLATE `.ps1` twins and validation requires `gif-from-video.sh` under `scripts/` or `scripts/plate/`. `posix-and-windows` copies both flavors and validation requires both GIF scripts; template CI still runs the shell validator. `windows` omits PLATE `.sh` twins, validation requires `gif-from-video.ps1` under `scripts/` or `scripts/plate/`, and the copied template CI test job runs `pwsh -File scripts/ValidatePlateRepo.ps1 -Root .` on `windows-latest`. The copied `process-gifs` job calls `gif-from-video.ps1` through `pwsh` and fails if that helper or `pwsh` is missing. `--platform` states the value for that run and is written into `.plate` on apply. The filter names PLATE-owned basenames only (`validate_plate_repo.sh`, `ValidatePlateRepo.ps1`, `bootstrap_github.sh`, `BootstrapGitHub.ps1`, `check_toolchain.sh`, `CheckToolchain.ps1`, `question_batch.sh`, `QuestionBatch.ps1`, `e2e-record.sh`, `e2e-record.ps1`, `gif-from-video.sh`, `gif-from-video.ps1`). `scripts/README.md` and `scripts/dev-server.js` are always copied. Adopter-owned scripts are not deleted, including namespaced files under `scripts/plate/`. The template payload stays the dual-stack superset. This repository sets `posix-and-windows`.
