# Risk Assessment And Labeling

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

## Risk Assessment and Labeling

The `risk:*` label family communicates review burden and operational caution to humans and agents. Every PR may carry at most one `risk:*` label, selected from: `risk:low`, `risk:medium`, `risk:high`, `risk:critical`.

**risk:low** - Minimal review burden and low operational impact:
- Addresses third-party feedback or applies reviewed suggestions (Feedback Response PRs are **automatically** labeled `risk:low`)
- Small, localized changes that do not affect API boundaries, data models, or authentication
- Pure documentation, comment, or test-only changes that do not affect production behavior
- Dependency version bumps that pass all CI gates
- Formatting, naming, or cleanup changes with no semantic impact
- Changes that provably reduce technical debt with no functional change

**risk:medium** - Moderate review burden or operational caution:
- New features behind feature flags or in non-production code paths
- Behavioral changes to non-critical subsystems (logging, monitoring, utilities)
- Database migrations with forward/backward compatibility; schema changes with no data loss
- Configuration or deployment changes with straightforward rollback paths
- Public API additions that are purely additive (no removal or breaking changes)

**risk:high** - High review burden, user impact, or migration risk:
- Behavioral changes to critical paths (auth, payment, data integrity)
- Public API breaking changes or removals
- Database migrations that lose data or cannot be rolled back
- Infrastructure or deployment changes with unknown rollback procedure
- Changes affecting multiple subsystems or cross-cutting concerns
- Changes that modify `SPEC.md`, per-feature change files in `.agentic/releases/`, or public product claims

**risk:critical** - Release, security, compliance, or data risk:
- Security vulnerabilities (auth bypass, data exposure, injection flaws)
- Compliance or legal changes (privacy, terms, licensing)
- Changes affecting billing, pricing, or subscription logic
- Customer data access, deletion, or transformation
- Changes to `.github/CODEOWNERS`, `AGENTS.md`, or branch protection rules
- Modifications to `.github/AUTONOMOUS_MODE` or autonomous mode eligibility criteria

**When to apply risk:low:**
- Always apply to `Feedback Response` PRs — the `.github/workflows/auto-label-feedback-responses.yml` workflow does this automatically
- Apply to `Documentation` and `Refactoring` PRs unless they update product specification or public claims
- Apply to test-only or CI-only PRs that do not affect deployed code
- Apply to pure chore PRs (dependency bumps, code cleanup) when no behavior changes

**When NOT to apply risk:low:**
- If `risk:medium`, `risk:high`, or `risk:critical` is more accurate — apply the higher label instead
- If unsure, apply `risk:medium` or ask a human reviewer to clarify
- If the PR carries `need:human-review`, `need:security-review`, or `need:decision`, re-assess after those needs are satisfied
