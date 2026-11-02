# Template Integrity Rules

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Template Integrity Rules

- Keep `.github/copilot-instructions.md` present and aligned with the repository's real CI/runtime commands.
- Keep `.github/workflows/ci.yml` pointed at executable validation logic (`scripts/validate_plate_repo.sh`) rather than placeholder echo steps.
- For repositories that add runtime manifests, replace placeholder CI/docs claims in the same PR that introduces the runtime.
- Use repository-local temporary paths for scripts and validation helpers; avoid platform-specific assumptions such as `/tmp`.
