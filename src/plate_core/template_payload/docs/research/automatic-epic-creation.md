# Research: Automatic Epic Creation

- **Issue:** #28
- **Researched by:** @copilot
- **Date:** 2026-05-25
- **Status:** Complete — awaiting human decision

## Research Question

How should the PLATE template handle the `Epic: short-name` traceability label when a Feature issue references an Epic that does not yet exist? Specifically: should the Feature issue template use a **dropdown** (selecting from existing open Epics), a **free-form field** that triggers automatic Epic creation, or a hybrid approach?

## Context

Today the system works as follows:

1. **Feature issue template** (`.github/ISSUE_TEMPLATE/feature.yml`) has a free-form `input` field where the author types the desired `Epic: short-name` label name.
2. **Epic issue template** (`.github/ISSUE_TEMPLATE/epic.yml`) similarly has a free-form `input` field for the dedicated label name.
3. **Label check workflow** (`.github/workflows/label-check.yml`) validates that Feature and Epic issues carry exactly one `Epic: short-name` label — but does not verify the label already exists in the repository.
4. **Bootstrap guidance** tells humans to manually create `Epic: short-name` labels and the first Epic issue.

The gap: a developer can create a Feature issue referencing `Epic: new-thing`, but no label or Epic issue for `new-thing` exists. The label check will fail until a human creates the label manually, creating friction.

## Options

### Option A: Dropdown Field (Existing Epics Only)

**Mechanism:** Replace the `input` field in the Feature template with a `dropdown` populated by a static list of known Epic labels maintained in the YAML file.

**Workflow:**
1. Maintainer creates an Epic issue and its label.
2. Maintainer updates `feature.yml` to add the new label to the dropdown list.
3. Feature authors select from the dropdown.

| Benefit | Cost |
|---|---|
| Zero chance of typos or orphan references. | Requires manual template maintenance every time an Epic is created or retired. |
| Simple mental model for feature authors. | GitHub issue form dropdowns are static YAML lists — no API-driven dynamic population is supported. |
| No automation or token requirements. | Scales poorly as Epic count grows; dropdown becomes long and stale. |
| No risk of runaway Epic creation. | Cannot create a Feature for a planned-but-not-yet-filed Epic. |

**Feasibility:** GitHub issue form `dropdown` fields only support static option lists defined in the YAML file. There is no native mechanism to dynamically query existing labels and present them. This makes the approach inherently manual and high-maintenance.

---

### Option B: Free-Form Field with Workflow-Driven Auto-Creation

**Mechanism:** Keep the free-form `input` field. Add a GitHub Actions workflow that fires on `issues: [opened]`, reads the `epic_label` field from the issue body, and:
1. Checks whether the label already exists.
2. If not, creates the label via the API.
3. Applies the label to the issue.
4. Optionally creates a stub Epic issue if no open Epic issue carries that label.

**Workflow:**
1. Feature author types `Epic: my-feature-area` in the template field.
2. Workflow creates label + stub Epic issue automatically.
3. A maintainer refines the stub Epic later with scope, success criteria, and child features.

| Benefit | Cost |
|---|---|
| Zero friction for feature authors — just type and go. | Requires `issues: write` and `contents: read` permissions on the workflow. |
| Labels and Epic issues are always consistent. | Risk of Epic sprawl — anyone can accidentally create new Epics via typos. |
| No manual template maintenance needed. | Stub Epics may lack meaningful scope/success criteria until a human edits them. |
| Supports the "Feature before Epic" workflow for rapid prototyping. | More complex automation to build and maintain. |
| Epic naming conventions can be validated with regex. | Naming collisions if free-text is not normalized (e.g., capitalization). |

**Mitigation strategies:**
- Normalize label text (trim, lowercase slug after `Epic: `).
- Require the label to match `/^Epic: [a-z0-9][a-z0-9-]{1,38}$/` (max 40 chars).
- Post a comment on the newly created stub Epic prompting the maintainer to fill in scope.
- Add a `need:decision` label to stub Epics so they surface in triage.

---

### Option C: Hybrid — Free-Form with Suggestion List and Guard Rails

**Mechanism:** Keep the free-form `input` field. Add:
1. A **workflow** (on `issues: [opened, edited]`) that validates the entered label name, creates the label if missing, and applies it.
2. An **issue body hint** listing currently active Epics (maintained by a scheduled workflow or manually).
3. A **guard-rail workflow** that prevents auto-creation unless the label name passes a naming convention regex.

**Workflow:**
1. Feature template shows a markdown block listing open Epics as a reference.
2. Author types the desired `Epic: short-name` (existing or new).
3. If it matches an existing label → apply it.
4. If it's new and passes naming convention → create label, create stub Epic, apply label.
5. If it fails naming convention → post a comment asking for correction and don't apply.

| Benefit | Cost |
|---|---|
| Best of both worlds: discoverability + flexibility. | Most complex to implement (two workflow components). |
| Guards against typos via naming validation. | Requires periodic refresh of the suggestions list (or accept staleness). |
| Supports both "choose existing" and "propose new" workflows. | Slightly more cognitive load for contributors to read the suggestion list. |
| Naming convention enforcement prevents Epic sprawl. | Still requires a human to complete stub Epic details. |

---

### Option D: Status Quo — Manual Label and Epic Management

**Mechanism:** No automation. Humans create Epic issues and labels manually. Features that reference nonexistent labels fail the label check until a human intervenes.

| Benefit | Cost |
|---|---|
| Zero maintenance, zero complexity. | High friction — blocks Feature work on Epic administration. |
| Full human control over Epic lifecycle. | Label typos go unnoticed until the check fails. |
| No accidental Epic creation. | Does not scale for active projects with frequent Feature creation. |

---

## Decision Criteria Comparison

| Criterion | A (Dropdown) | B (Auto-Create) | C (Hybrid) | D (Status Quo) |
|---|---|---|---|---|
| Developer friction | Low (select) | Low (type) | Low (type with hint) | High (manual label creation) |
| Typo resilience | ✅ Impossible | ⚠️ Naming regex helps | ✅ Naming regex enforced | ❌ No guard |
| Epic sprawl risk | ✅ None | ⚠️ Moderate | ✅ Low (guarded) | ✅ None |
| Template maintenance | ❌ Every Epic change | ✅ None | ⚠️ Periodic hint refresh | ✅ None |
| GitHub API limitations | ✅ None (static YAML) | ⚠️ Needs `issues: write` | ⚠️ Needs `issues: write` | ✅ None |
| Supports "Feature-first" flow | ❌ Epic must exist first | ✅ Yes | ✅ Yes | ❌ Epic must exist first |
| Implementation complexity | Trivial | Moderate (~50 LOC workflow) | High (~100 LOC, 2 workflows) | None |
| Best practice alignment | Rigid waterfall | Agile-compatible | Agile with guardrails | Manual overhead |

## Recommendation

**Option B (Free-Form with Auto-Creation)** offers the best value-to-complexity ratio for PLATE's agent-driven workflow, with Option C as a future enhancement if Epic sprawl becomes a problem.

Rationale:
1. PLATE is designed for agent-assisted development where Feature issues are created programmatically. Requiring manual Epic pre-creation blocks autonomous workflows.
2. A naming convention regex (`/^Epic: [a-z0-9][a-z0-9-]{1,38}$/`) prevents most typo-driven sprawl.
3. Stub Epic issues with `need:decision` labels surface in triage without blocking Feature work.
4. The workflow is ~50 lines of `actions/github-script` and requires `issues: write` permission (note: `label-check.yml` currently only has `issues: read`, so this is a permission escalation).
5. Option A is infeasible for dynamic use because GitHub issue forms don't support API-driven dropdowns.

## Implementation Sketch (Option B)

```yaml
# .github/workflows/epic-auto-create.yml
name: PLATE Epic Auto-Create

on:
  issues:
    types: [opened]

permissions:
  issues: write

jobs:
  ensure-epic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const issue = context.payload.issue;
            if (!issue) return;

            const labels = (issue.labels || []).map(l => l.name);
            if (!labels.includes('Feature') && !labels.includes('Epic')) return;

            // Extract epic_label from issue body (form field)
            const match = issue.body?.match(/### Epic traceability label\s*\n\s*(.+)/i)
              || issue.body?.match(/### Dedicated epic label\s*\n\s*(.+)/i);
            if (!match) return;

            const raw = match[1].trim();
            const epicLabel = raw.startsWith('Epic: ') ? raw : `Epic: ${raw}`;
            const slug = epicLabel.replace(/^Epic: /, '');

            // Validate naming convention
            if (!/^[a-z0-9][a-z0-9-]{1,38}$/.test(slug)) {
              await github.rest.issues.createComment({
                ...context.repo,
                issue_number: issue.number,
                body: `⚠️ The epic label \`${epicLabel}\` does not match the naming convention \`Epic: [a-z0-9][a-z0-9-]{1,38}\`. Please edit the issue to correct it.`
              });
              return;
            }

            // Ensure label exists
            try {
              await github.rest.issues.getLabel({ ...context.repo, name: epicLabel });
            } catch (e) {
              if (e.status === 404) {
                await github.rest.issues.createLabel({
                  ...context.repo,
                  name: epicLabel,
                  color: '5319e7',
                  description: `Epic traceability label (auto-created from #${issue.number}).`
                });
              }
            }

            // Apply label to issue
            await github.rest.issues.addLabels({
              ...context.repo,
              issue_number: issue.number,
              labels: [epicLabel]
            });

            // If this is a Feature, check if a matching Epic issue exists
            if (labels.includes('Feature')) {
              const { data: issues } = await github.rest.issues.listForRepo({
                ...context.repo,
                labels: `Epic,${epicLabel}`,
                state: 'open'
              });
              if (issues.length === 0) {
                const { data: stubEpic } = await github.rest.issues.create({
                  ...context.repo,
                  title: `[Epic]: ${slug}`,
                  labels: ['Epic', epicLabel, 'need:decision'],
                  body: [
                    `This Epic was auto-created because Feature #${issue.number} referenced \`${epicLabel}\` and no existing Epic issue was found.`,
                    '',
                    '**Action required:** Fill in scope, success criteria, and child features.',
                    '',
                    '### Desired outcome', '', 'TBD', '',
                    '### Scope and boundaries', '', 'TBD', '',
                    '### Success criteria', '', '- [ ] TBD', '',
                    '### Expected child features', '', `- #${issue.number}`
                  ].join('\n')
                });
                await github.rest.issues.createComment({
                  ...context.repo,
                  issue_number: issue.number,
                  body: `🏷️ Created Epic #${stubEpic.number} and label \`${epicLabel}\` automatically. A maintainer should refine the Epic scope.`
                });
              }
            }
```

## Open Questions for Human Decision

1. **Naming convention strictness:** Should the slug allow uppercase or spaces (e.g., `Epic: My Feature`)? The recommendation is lowercase-hyphenated only.
2. **Auto-creation scope:** Should the workflow also fire on `edited` events (to handle corrections) or only on `opened`?
3. **Stub Epic completeness:** Should auto-created stub Epics require human sign-off (via `need:decision`) before child Features can proceed?
4. **Permission model:** Should Epic auto-creation be limited to repository collaborators, or allowed from any issue opener?

## References

- GitHub Issue Form syntax: only `dropdown`, `input`, `textarea`, `checkboxes`, and `markdown` types are supported. Dropdowns require static option lists.
- GitHub Actions `issues: write` permission allows label and issue creation within the same repository.
- Current PLATE label check: `.github/workflows/label-check.yml`
- Current Feature template: `.github/ISSUE_TEMPLATE/feature.yml`
