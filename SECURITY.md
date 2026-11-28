# Security Policy

## Supported Versions

We address security issues in **the latest published release** of PLATE (`plate-core` on PyPI, the matching `gh-plate` extension release, and tagged releases of this repository).

A formal supported-versions and compatibility policy is tracked in issue **#1057** and is **not settled yet**. Until that work lands, treat “latest release” as the practical support window and check [GitHub Releases](https://github.com/akasper/plate/releases) for the current version.

## Scope

This policy covers security issues in:

| Area | What it includes |
|---|---|
| **plate-core** | The `plate_core` Python package (`src/plate_core/`), including `plate-mcp` and library code shipped on PyPI as `plate-core`. |
| **gh-plate** | The `gh plate` CLI extension ([`akasper/gh-plate`](https://github.com/akasper/gh-plate)), including install/upgrade behavior and how it pins `plate-core`. |
| **Template payload** | Files under `src/plate_core/template_payload/` that adopters receive via `gh plate import-payload` / bootstrap. |
| **Actions** | GitHub Actions workflows in this repository (`.github/workflows/`) and the workflow templates in the template payload. |

Vulnerabilities in **downstream adopter repositories** (your product code, infrastructure, and secrets) are outside this policy unless they stem from a defect in the surfaces above.

General process questions, feature requests, and non-security bugs belong in [GitHub Issues](https://github.com/akasper/plate/issues); use the reporting path below only for **security-sensitive** defects.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report them privately through GitHub **private vulnerability reporting** / **security advisories** for this repository:

1. Open [Report a vulnerability](https://github.com/akasper/plate/security/advisories/new) (Security → Advisories → *Report a vulnerability*), or use the **Security** tab on [akasper/plate](https://github.com/akasper/plate) when private reporting is enabled.
2. Provide as much detail as you can so we can reproduce and assess impact.

We do **not** accept vulnerability reports via personal email addresses published in this file. Use the GitHub advisory flow above so correspondence stays on-platform and access-controlled.

### What to include

Helpful reports usually include:

- A clear description of the issue and the affected component (plate-core, gh-plate, template payload, or Actions).
- Steps to reproduce, proof-of-concept, or failing scenario.
- Impact assessment (confidentiality, integrity, availability, privilege boundary crossed).
- Affected versions or commits, if known.
- Your contact preference on GitHub (we reply through the advisory thread).

### Response expectations (best effort)

We will make a **best effort** to:

- Acknowledge receipt of a valid private report.
- Ask clarifying questions when needed.
- Investigate and coordinate a fix or mitigation.
- Credit reporters when advisories are published, if you want acknowledgment.

We **do not** commit to fixed response or remediation timeframes (no SLAs). Severity, complexity, and release coordination affect timing. We may decline reports for unsupported versions, third-party dependencies outside PLATE’s control, or issues that do not constitute a practical security defect in scope.

## In-repo security review (`need:security-review`)

For **planned changes** inside this repository (pull requests and issues), PLATE uses the GitHub label **`need:security-review`** when work needs explicit review for security, permissions, secrets, privacy, or abuse risk (see `.github/labels.yml`).

That label is part of our **development process**, not a substitute for private vulnerability reporting. If you found a vulnerability in released or mainline code, still use [private vulnerability reporting](#reporting-a-vulnerability) above.