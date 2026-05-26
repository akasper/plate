# New Repository Bootstrap Checklist

Use this checklist immediately after creating a repository from the PLATE template. It separates the steps that can be standardized from the ones that still require human judgment.

## Fast Path

From the generated repository root, choose the script for your operating system:

**macOS / Linux / WSL (bash):**
```bash
bash scripts/bootstrap_github.sh --repo OWNER/REPO --local-repo . --owner-handle @your-handle --remove-default-labels --set-delete-branch-on-merge --protect-branch main
# Add --init-wiki only if you plan to enable wiki sync.
```

**Windows (PowerShell):**
```powershell
.\scripts\BootstrapGitHub.ps1 -Repo OWNER/REPO -LocalRepo . -OwnerHandle @your-handle -RemoveDefaultLabels -SetDeleteBranchOnMerge -ProtectBranch main
# Add -InitWiki only if you plan to enable wiki sync.
```

Both scripts require only `gh` (GitHub CLI) and `git`. They cover the repeatable GitHub bootstrap work that otherwise gets missed in brand-new repositories.

## Automatable Steps

| Step | Why It Matters | Covered by Helper |
|---|---|---|
| Sync canonical PLATE labels from `.github/labels.yml` | The label taxonomy drives routing, enforcement, and review semantics. | Yes |
| Remove conflicting default GitHub labels | Default labels such as `documentation` and `enhancement` create drift from the canonical PLATE taxonomy. | Yes |
| Replace `@PLATE_REPO_OWNER` in `.github/CODEOWNERS` | Placeholder owners break review routing and code-owner protection. | Yes |
| Enable delete-branch-on-merge | Keeps the repository clean after reviewed work lands. | Yes |
| Initialize the wiki from `docs/wiki/Home.md` | Prevents the GitHub wiki from starting empty when the repository-managed source already exists. | Yes, when `--init-wiki` / `-InitWiki` is passed |
| Apply conservative baseline branch protection | Provides immediate protection against force-pushes and branch deletion while requiring conversation resolution. | Yes, when `--protect-branch BRANCH` / `-ProtectBranch BRANCH` is passed |

## Human Decisions Still Required

| Step | Why Human Review Is Still Needed |
|---|---|
| Decide the final branch protection policy | Approval counts, code-owner review, required checks, and linear history depend on team size and merge model. |
| Configure GitHub Projects fields | Project field names and lifecycle shape should match the team’s planning model. |
| Replace placeholder product language in docs | Only a human product owner can define the initial repository’s real intent and public claims. |
| Create the first real `Epic: short-name` labels | Epics should reflect the project’s actual roadmap, not the template example. |
| Tune CI, release, pages, and audit workflows | The template ships scaffolds, but real commands and release policy depend on the project stack. |
| Decide whether to enable wiki sync | Write automation, token scope, and wiki publication policy require explicit approval. |

## Common Bootstrap Failure Modes

1. Default GitHub labels remain in place, so pull requests get labeled with `documentation` instead of `Documentation`.
2. `.github/CODEOWNERS` still contains `@PLATE_REPO_OWNER`, so review ownership is never actually configured.
3. The GitHub wiki exists but stays empty even though `docs/wiki/Home.md` already defines the intended homepage.
4. The repository claims GitHub Projects should hold mutable planning state, but no actual project fields have been created yet.
5. Branch protection is missing or too weak for a GitHub-first workflow.

## Recommended First Follow-Up Issue

Open a `Research` or `Epic` issue to capture the repository’s first real roadmap slice, then create the matching `Epic: short-name` label so Feature work can remain traceable from the first implementation PR.
