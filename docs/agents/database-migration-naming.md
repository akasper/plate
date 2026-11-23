# Database Migration Naming

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Convention (#1451)

When adding **new** database schema migrations, use filenames that do not collide across parallel agent branches.

**Default format:** UTC creation timestamp, underscore, short slug, then the extension your toolchain expects—for example `20261109T111800Z_residue_baseline.sql`.

- Timestamp: UTC instant when you **create** the migration file (compact form `YYYYMMDDTHHMMSSZ`).
- Slug: lowercase words separated by underscores; briefly describes the change.
- Extension: match the repo's migration layout (`.sql`, `.up.sql`, etc.).

**Sequential numbering only when required:** Some migration tools mandate monotonic numeric prefixes (for example Flyway version segments, golang-migrate-style `000001_`, or framework-enforced ordering). When the tool requires that:

- Follow the tool's numbering scheme and continue from the highest **existing** migration.
- Document the exception in the adopting repository (`README`, `SPEC.md`, or `docs/migration/`) so agents know sequential names are mandatory.

**Do not rename existing migrations.** Migrations already merged or deployed keep their names. The timestamp convention applies to **new** files only.

**Rationale:** Parallel branches that each chose the next sequential number (for example two PRs both adding `007` in akasper/Lull #72 and #75) collide and require manual renumbering before merge.
