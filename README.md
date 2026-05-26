<!-- Trivial rebuild trigger to refresh GitHub mergeability status (mobile app cache) -->

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
