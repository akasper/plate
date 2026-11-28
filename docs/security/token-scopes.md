# PLATE token and permission surfaces

This document maps **which credentials each PLATE surface uses**, the **permissions declared in repository workflows**, and **what fails when a permission is missing**. Claims are tied to files in `akasper/plate` (and the mirrored template payload under `src/plate_core/template_payload/` unless noted).

**Not covered here:** exploit steps, live tokens, or editing `SECURITY.md` (tracked separately).

**Related issues:** #1061 (this doc), Epic #1059, design notes in `docs/agents/branch-model-and-ceremonies.md` and `docs/design/issue-lifecycle.md`.

---

## How PLATE talks to GitHub

Almost all runtime GitHub access from the `gh plate` CLI and **plate-mcp** goes through `GhClient` in `src/plate_core/github_client.py`, which shells out to authenticated **`gh api`** (and GraphQL via the same entry point). The effective credential is whatever `gh auth login` (or `GH_TOKEN` / `GITHUB_TOKEN` in the environment) provides for that invocation.

```66:73:src/plate_core/github_client.py
@dataclass
class GhClient:
    """Minimal GitHub API helper using the authenticated `gh` CLI.

    Enhanced for beta: retries with backoff/jitter for transient errors (rate limits,
    5xx, timeouts), rate-limit awareness (sleep on detected limit), secret redaction
    in errors. Supports partial resilience for autonomous tools (babysit, health, etc.).
    """
```

**Least privilege (local agents):** Use one dedicated machine user or fine-grained PAT scoped to the repos you automate; avoid sharing a personal owner token across agents.

**What breaks without any GitHub credential:** Any command that calls `GhClient` fails at the first `gh api` with authentication errors (`gh plate runner doctor` reports `Could not read gh auth scopes`).

---

## 1. GitHub CLI (`gh auth`) for `gh plate` and helpers

### 1.1 Enforced minimum scope (self-hosted runner doctor)

`gh plate runner doctor` reads scopes from `gh auth status` and **requires classic OAuth scope `repo`**:

```17:17:src/plate_core/runner.py
REQUIRED_TOKEN_SCOPES = frozenset({"repo"})
```

| Scope / permission | Why (code) | If missing |
|---|---|---|
| `repo` (classic) | `REQUIRED_TOKEN_SCOPES` in `src/plate_core/runner.py` | `runner doctor` → `token_scopes` **fail**; other commands may still run until they hit a forbidden API |

The doctor does **not** enumerate every scope PLATE might need for optional flows (see below).

### 1.2 Additional classic scope: `workflow`

When `gh plate bootstrap` writes files under `.github/workflows/`, bootstrap error text states that classic PATs need **`workflow` in addition to `repo`**:

```593:598:src/plate_core/bootstrap.py
    workflow_scope_hint = ""
    if rel_path.startswith(".github/workflows/"):
        workflow_scope_hint = (
            " This path is under .github/workflows/, so classic PATs must include "
            "`workflow` scope in addition to `repo`."
        )
```

| Scope | Why | If missing |
|---|---|---|
| `workflow` (classic, with `repo`) | Updating workflow YAML via Git Data / contents API on default branch | Bootstrap / import-payload writes under `.github/workflows/` fail with the hint above |

### 1.3 Bootstrap / `scripts/bootstrap_github.sh`

| Operation | Source | Implied GitHub access |
|---|---|---|
| `gh auth status` | `scripts/bootstrap_github.sh` | Valid `gh` login |
| Label list/create/edit/delete | `gh label …` | Repository metadata (within `repo` for classic tokens) |
| `gh repo edit … --delete-branch-on-merge` | same script | Administration-style repo settings |
| Branch protection PUT | `gh api repos/$REPO/branches/.../protection` | Admin or bypass-capable identity |
| Wiki clone/push via `gh auth token` | `GIT_ASKPASS` + wiki remote | `repo` (wiki is part of repository) |

Bootstrap repository creation uses REST `POST orgs/{owner}/repos` then `POST user/repos` (`src/plate_core/bootstrap.py`). The code does not name an OAuth scope; creating org-owned repos requires an identity with **org repository creation** rights (see Open questions).

### 1.4 `GhClient` operations by command family

The table below maps **representative REST/GraphQL calls** in `plate_core` to permission needs. Classic scope **`repo`** covers all of these for private repositories on github.com. For **public** repos, unauthenticated or `public_repo` may suffice for read-only calls; PLATE does not special-case that path—agents typically use full `repo`.

| Family | Commands / MCP tools (examples) | API surface (file) | Needs (classic) | If under-provisioned |
|---|---|---|---|---|
| Read / status | `release status`, `health`, `epic status`, `pr verify`, `get_release_status`, most planning reads | `GET repos/...`, GraphQL read (`release.py`, `health.py`, `epics.py`, `pr_verify.py`) | `repo` (private) or public read | 404/403 on private data; gates report incomplete |
| Issues & labels | Stub author/create, release ceremony issue filing, cost harvesting reads | `repos/.../issues`, labels (`release.py`, stub tools) | `repo` | Cannot create/update issues or labels |
| Pull requests & review threads | `pr babysit`, `resolve_review_thread`, MCP babysit tools | GraphQL + `repos/.../issues/{pr}/comments` (`pr_babysit.py`) | `repo` | Cannot list threads, comment, or resolve review threads |
| Contents & git refs | `bootstrap`, `import-payload`, remote fragment writes | Git trees/commits/refs, contents API (`bootstrap.py`, `import_payload.py`) | `repo`; **`workflow`** when path is under `.github/workflows/` | Push/ref update failures; bootstrap error with workflow hint |
| Releases & tags | `release finalize`, `create_github_release` | `repos/.../releases` (`release.py`; also used from `.github/workflows/release.yml`) | `repo` | Tag/release creation or metadata fetch fails |
| Branches | `release cut`, fast-forward helpers, `cleanup_dead_branches` | `repos/.../branches`, `git/refs` (`release.py`) | `repo` | Branch create/update blocked by branch rules or token |

`gh plate pr create` / MCP equivalents ultimately call **`gh pr create`** after local preflight (`src/plate_core/pr_preflight.py`); that requires permission to open a PR on the target repo (included in `repo`).

### 1.5 PR image attachments (`gh pr create --attach`)

AGENTS.md documents that **local** agents with user PATs (`gho_`, `ghp_`, `github_pat_`) can attach images. Third-party cloud agents without a user PAT cannot use `--attach`. This is a **host/token-type** constraint, not an extra OAuth scope name in the codebase.

### 1.6 Self-hosted runner selection (composite action)

`.github/actions/plate-select-runs-on/action.yml` documents that the default **`GITHUB_TOKEN` cannot list self-hosted runners**; the probe needs a token with **Administration read** (fine-grained) or a classic PAT with sufficient repo/admin rights:

```14:17:.github/actions/plate-select-runs-on/action.yml
      Token for the self-hosted runner list API. GITHUB_TOKEN cannot call this
      endpoint; use a classic PAT with repo scope or a fine-grained PAT with
      Administration read on the repository. Defaults to the job GITHUB_TOKEN.
```

| Token | Why | If missing / wrong |
|---|---|---|
| Optional `github-token` input (secret PAT) | Call “List self-hosted runners for a repository” | Probe 403/404; action falls back to `ubuntu-latest` (`docs/migration/self-hosted-runners.md`) |

---

## 2. plate-mcp (MCP server)

`src/plate_core/mcp_server.py` exposes tools that call the same Python modules as the CLI (`bootstrap`, `release`, `pr_babysit`, `health`, etc.). There is **no separate MCP credential**: the server process inherits the **`gh` CLI authentication** of its host (or `GH_TOKEN` if `gh` is configured to use it).

| Surface | Credential | Effective permission |
|---|---|---|
| plate-mcp stdio | Host `gh auth` / `GH_TOKEN` | Same as §1 for each tool invoked |

**Least privilege:** Run MCP only on a host whose `gh` identity is scoped to the repos that agent may touch; do not export owner PATs into shared MCP processes.

---

## 3. `GITHUB_TOKEN` in GitHub Actions

Workflows set least-privilege defaults via top-level or job-level `permissions:`. The template payload copies most of these files into adopter repos via `import-payload` / bootstrap.

**Legend — “what breaks”:** Typical failure modes are **403** from `actions/github-script` or `gh api`, check failures, or skipped jobs (when secrets are absent).

### 3.1 Workflows in `.github/workflows/` (akasper/plate)

| Workflow file | `permissions` (workflow default unless noted) | Job-level override | Primary token use | What breaks without declared permission |
|---|---|---|---|---|
| `ci.yml` | `contents: read`, `actions: read` | — | Checkout, read Actions metadata | Cannot run checkout or inspect Actions (job fails early) |
| `release.yml` | `contents: write` | `fast-forward-release-branches`: `contents: write`, `issues: write`; `deploy`: `contents: read` | Tag push, `create_github_release` via `GH_TOKEN: ${{ github.token }}`; optional App checkout token | No tag on merge; release create step fails; fast-forward skipped without App secrets (warning only) |
| `plate-pr-gates.yml` | `contents: read`, `issues: read`, `pull-requests: write`, `actions: read` | `mark-implemented-on-release-merge`: `contents: read`, `issues: write`, `pull-requests: read` | `gh api` PR fetches; issue link gate; **`gh_actions_mark_implemented`** with `GITHUB_TOKEN` | PR checks cannot update; mark-implemented cannot label/close issues |
| `label-check.yml` | `contents: read`, `issues: read` | — | Read issue labels | Gate cannot read issue labels → false failures or skipped validation |
| `labels.yml` | `contents: read`, `pull-requests: read` | — | Read PR labels | Label type gate cannot read PR |
| `plate-ui-pr-image-check.yml` | `contents: read`, `pull-requests: read` | — | `GH_TOKEN` + `gh` to inspect PR diffs | UI image gate cannot read PR/content |
| `plates-on-issue-closed.yml` | `contents: write`, `issues: write` | — | Commit `.agentic/COSTS.md`, push default branch; optional dashboard comment | Cost log not updated; comment not posted |
| `plates-address-pr-feedback.yml` | `contents: read`, `pull-requests: write`, `issues: write` | — | `github-token: ${{ secrets.COPILOT_TRIGGER_PAT \|\| github.token }}` for PR comments | Copilot trigger comments fail (best-effort with `GITHUB_TOKEN`) |
| `plates-start-feature.yml` | `actions: write`, `issues: write` | — | `workflow_dispatch` another workflow; issue labels | Cannot chain orchestrator; label updates fail |
| `plates-unblock-features.yml` | `actions: write`, `issues: write` | — | Same pattern | Blocked-feature promotion does not run |
| `plates-agentic-orchestrator.yml` | `issues: write`, `pull-requests: write`, `actions: write` | — | Issue label orchestration (stub) | Orchestrator cannot write issues/PR metadata |
| `question-handling.yml` | `contents: read`, `issues: write` | — | `/question-batch` comment handling | Slash command handler cannot write issues |
| `sync-wiki-on-merge.yml` | `contents: read`, `pull-requests: read` | — | Gating only; push uses **`secrets.WIKI_TOKEN`** | Wiki sync steps skip unless `PLATE_WIKI_SYNC_ENABLED` + `WIKI_TOKEN` |
| `auto-merge.yml` | (none at workflow root) | Job `auto-merge`: `pull-requests: write`, `contents: write` | `gh pr merge --auto` with `secrets.GITHUB_TOKEN` | Cannot enable auto-merge |
| `publish-pypi.yml` | `contents: read`, `id-token: write` | — | OIDC to PyPI trusted publisher | Publish 403 without PyPI trusted publisher setup |
| `publish-gh-plate-extension.yml` | `contents: read` | — | Uses **`secrets.THIN_SHIM_DEPLOY_TOKEN`** for cross-repo push | Cannot push `akasper/gh-plate` shim (plate-core only workflow) |
| `pages.yml` | *(no explicit block — repo default `GITHUB_TOKEN` permissions apply)* | — | Pages deploy | Depends on repository **Workflow permissions** default |

### 3.2 `mark-implemented-on-release-merge` (REST mapping)

`src/plate_core/gh_actions_mark_implemented.py` uses `GITHUB_TOKEN` to:

| REST call | Maps to `permissions` |
|---|---|
| `GET /issues/{n}` | `issues: read` (job grants `issues: write`, which includes read) |
| `DELETE/POST /issues/{n}/labels` | `issues: write` |
| `POST /issues/{n}/comments`, `PATCH /issues/{n}` (close) | `issues: write` |

Without `issues: write`, integration merges to `release-*` / `epic/*` branches do not apply `status:implemented` or auto-close linked issues.

### 3.3 Template-only workflows (`src/plate_core/template_payload/.github/workflows/`)

Adopters receive these in addition to (or instead of) the plate-core repo set:

| Workflow | `permissions` | Notes vs akasper/plate |
|---|---|---|
| `ci.yml` | `contents: read`, `issues: write`, `pull-requests: write`, `actions: read` | Template CI can label PRs / issues in the `labels` job; plate-core `ci.yml` is slimmer |
| `cost-tracking.yml` | `contents: read`, `issues: write`, `pull-requests: read`, `actions: read` | Not shipped in akasper/plate root workflows |
| `platform-monitor.yml` | `contents: read`, `issues: write` | Creates research issues on schedule |
| `test-e2e.yml` | `contents: read`, `pull-requests: write`, `checks: write`, `actions: read` | Posts/checks E2E results on PRs |
| `auto-label-feedback-responses.yml` | Job: `pull-requests: write` | Adds `risk:low` + `auto-merge` on Feedback Response PRs |
| Others (`release.yml`, `plate-pr-gates.yml`, …) | Same blocks as `.github/workflows/` counterparts in this repo (payload kept in sync by tests such as `tests/test_native_github_pr_integration.py`) | — |

### 3.4 Repository secrets (not `GITHUB_TOKEN`)

| Secret | Where referenced | Required permission (documented) | If absent |
|---|---|---|---|
| `PLATE_APP_ID`, `PLATE_APP_PRIVATE_KEY` | `.github/workflows/release.yml` `actions/create-github-app-token@v1` | GitHub App with **Contents (read/write)**, **Issues and Pull requests (read/write)**, **Actions** + **Checks (read)** per `docs/agents/branch-model-and-ceremonies.md` | Fast-forward job logs warning; release branches not updated automatically |
| `THIN_SHIM_DEPLOY_TOKEN` | `publish-gh-plate-extension.yml` | Fine-grained PAT or App token **`contents: write` on `akasper/gh-plate` only** | Shim repo not updated |
| `COPILOT_TRIGGER_PAT` | `plates-address-pr-feedback.yml` | User PAT able to route `@copilot` comments | Falls back to `GITHUB_TOKEN` (often insufficient for Copilot routing) |
| `WIKI_TOKEN` | `sync-wiki-on-merge.yml` | PAT with push access to `*.wiki` git remote | Wiki sync fails when enabled |
| `RUNNER_PROBE_TOKEN` (optional pattern) | Pass as `github-token` to `plate-select-runs-on` | Admin read / classic `repo` per action.yml | Idle-runner probe falls back to hosted |

---

## 4. GitHub App installations

### 4.1 PLATE lifecycle App (release fast-forward)

When both `PLATE_APP_ID` and `PLATE_APP_PRIVATE_KEY` are set, `.github/workflows/release.yml`:

1. Mints an installation token via `actions/create-github-app-token@v1`.
2. Uses it for `actions/checkout` on the fast-forward job.
3. Documents required App permissions and ruleset bypass in workflow warnings and `docs/agents/branch-model-and-ceremonies.md`.

| App permission (documented) | Why | If missing |
|---|---|---|
| Contents read/write | Checkout + non-force ref updates to standing release branches | Push rejected by rulesets; job fails or maintainer must fast-forward manually |
| Issues + Pull requests read/write | Failure comments via `post_release_fast_forward_comment` | Cannot post diagnostic issue comments |
| Actions + Checks read | Listed in branch-model guidance for operational visibility | Secondary; fast-forward push is the critical path |

Register the App installation as a **ruleset bypass actor** on protected `release-*` branches when `GITHUB_TOKEN` cannot push.

### 4.2 Apps not defined in this repository

The codebase references GitHub Apps conceptually in `docs/design/issue-lifecycle.md` (preferred bot identity) but does **not** ship an App manifest in-repo. Operators create Apps in GitHub Settings and store IDs/keys as secrets above.

---

## 5. Least-privilege quick reference

| Actor | Tightest practical setup |
|---|---|
| Human maintainer CLI | Fine-grained PAT: single repo, Contents/Issues/PRs read/write, Metadata read; add Workflow permission only when editing workflows |
| Autonomous agent CLI | Same, on a bot account; never reuse owner token |
| plate-mcp host | Dedicated bot `gh auth login`; no org-wide admin |
| `GITHUB_TOKEN` | Keep workflow-level `permissions` blocks as shipped; avoid `permissions: write-all` |
| Release fast-forward | Dedicated GitHub App on one repo + bypass on release rulesets only |
| Wiki sync | Separate `WIKI_TOKEN` with wiki-only scope when sync is enabled |
| gh-plate shim publish | `THIN_SHIM_DEPLOY_TOKEN` limited to `akasper/gh-plate` contents write |
| Self-hosted runners | Optional PAT with **Administration read** on one private repo for probe only |

---

## 6. Open questions

These gaps are visible in the repository today; they are intentionally **not** invented as scopes in this doc.

1. **Fine-grained PAT mapping:** `REQUIRED_TOKEN_SCOPES` only checks classic `repo`. There is no automated checker for fine-grained permission sets equivalent to each command family (#1421 in `docs/design/issue-lifecycle.md`).

2. **Org bootstrap:** `POST orgs/{owner}/repos` failure paths are handled, but the exact OAuth scope or org role is not named in code—depends on GitHub org settings.

3. **`pages.yml`:** No explicit `permissions:` block; effective token access follows the repository **Settings → Actions → General → Workflow permissions** default.

4. **`plates-agentic-orchestrator.yml`:** Job body is still a stub (`console.log`); real API writes may need narrower permissions once implemented.

5. **Copilot / Copilot CLI in CI:** `ci.yml` installs Copilot CLI for smoke tests but does not document a Copilot service token requirement for those steps (commands use public release assets).

6. **GraphQL rate limits vs REST fallback:** Babysit prefers GraphQL (`pr_babysit.py`); permission errors vs rate limits are not distinguished in user-facing doctor output.

7. **Epic #1059 security review:** This document satisfies the #1061 artifact; human review under `need:security-review` may refine App permission wording or add FG-PAT recipes.

---

## Source index

| Topic | Path |
|---|---|
| CLI wrapper | `src/plate_core/github_client.py` |
| Runner scope check | `src/plate_core/runner.py` |
| Bootstrap workflow hint | `src/plate_core/bootstrap.py` |
| Mark implemented job | `src/plate_core/gh_actions_mark_implemented.py`, `.github/workflows/plate-pr-gates.yml` |
| Release ceremony token | `.github/workflows/release.yml` |
| Branch model App guidance | `docs/agents/branch-model-and-ceremonies.md` |
| Self-hosted runner token | `.github/actions/plate-select-runs-on/action.yml`, `docs/migration/self-hosted-runners.md` |
| Bootstrap shell | `scripts/bootstrap_github.sh` |
| Template workflows | `src/plate_core/template_payload/.github/workflows/` |
| PR attach matrix | `AGENTS.md` (UI screenshots section) |