---
name: Audit Security Posture
description: Review code, deps, configs, and workflows for security vulnerabilities, secret leaks, and compliance issues.
---

<!-- PLATE-GENERATED:BEGIN skills-surface -->
<!-- Do not edit generated skill surfaces manually. -->
<!-- Source of truth: src/plate_core/data/baseline_catalog.yml -->
<!-- Regenerate: python3 scripts/generate-plugin-skills.py -->

# Audit Security Posture

> Skill id: `audit-security-posture`
> Generated from the baseline catalog. Regenerate with `python3 scripts/generate-plugin-skills.py`.

Review code, deps, configs, and workflows for security vulnerabilities, secret leaks, and compliance issues.

**Owning agents:** security-auditor

## Inputs

- Code or config diffs
- Dependency list
- CI / deployment config

## Outputs

- Risk findings with severity and evidence
- Remediation recommendations

## Examples

- Audit the new auth module and dependency updates for secrets or injection risks.

<!-- PLATE-GENERATED:END skills-surface -->
