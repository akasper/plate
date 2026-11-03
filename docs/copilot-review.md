# Copilot code review effort (PLATE setup)

Epic [#1091](https://github.com/akasper/plate/issues/1091). Operator policy for **when** to use Copilot review lives in [agents/github-actions-and-copilot.md](agents/github-actions-and-copilot.md) (no auto-review on every push; human or process chooses Copilot once per PR). This page covers **review effort level**—Lite vs Balanced—and how to configure it on GitHub.

## PLATE defaults

| Scope | Effort | When |
|---|---|---|
| Repository (and org default, if you set one) | **Lite** | Default for Copilot code review in PLATE repos, aligned with Actions and Copilot cost policy. |
| Individual review request | **Balanced** | Pull requests labeled **`risk:high`** or **`risk:critical`** when a human or process requests Copilot review on that PR. |

GitHub’s platform built-in default is **Balanced** when no explicit level is chosen ([GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/code-review)). PLATE adopters should **set Lite explicitly** in settings so cost policy does not depend on GitHub’s default.

Lite gives fast, targeted feedback; Balanced uses deeper analysis and consumes more AI credits. See effort descriptions in the same concepts page.

## Manual setup (required)

The default review effort level is a **repository, organization, enterprise, or personal** setting on GitHub—not a file in the repo. Configure it once per level you control.

### Repository (primary for PLATE repos)

1. Open the repository on GitHub.
2. **Settings** → under “Code, planning, and automation”, **Copilot** → **Code review**.
3. Next to **Review effort level**, select **Lite** for automatic reviews in this repository.

Step-by-step reference: [Configuring code review by GitHub Copilot — Customizing Copilot code review](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review#customizing-copilot-code-review).

### Organization (optional)

If your org owns the repo, set a org-wide default so new repos inherit Lite unless they override:

1. **Organization settings** → **Copilot** → **Code review**.
2. Under **General**, next to **Default review effort level**, select **Lite**.

Repository settings override organization defaults ([same configure guide](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review)).

### Personal Copilot settings

Accounts that **request** Copilot reviews (including automation tokens) have a personal **Review effort level** under profile → **Copilot settings** → **Copilot** → **Code review**. Set **Lite** there when that identity is used to request routine reviews. Personal level participates in GitHub’s effort precedence chain when a per-request level is not set ([effort precedence](https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/code-review#review-effort-level)).

### High-risk pull requests

When you request Copilot review on a PR that carries **`risk:high`** or **`risk:critical`**, choose **Balanced** for that request:

- In the PR **Reviewers** sidebar, select **Balanced** next to Copilot before clicking **Request**, or
- When using an API that supports per-request effort, set Balanced on that request ([Copilot code review API support](https://github.blog/changelog/2026-10-02-copilot-code-review-api-support-and-new-default-effort-level/)).

Do not change the repository default to Balanced for all PRs; keep the repo default at Lite and escalate effort only on high-risk reviews.

## Can automation read the default effort level?

**No.** As of the linked GitHub documentation, the **default review effort level** stored in Copilot code review settings is **not readable** through a documented GitHub REST or GraphQL endpoint.

- The [REST API endpoints for Copilot](https://docs.github.com/en/rest/copilot) cover usage metrics, user management, content exclusion, and cloud-agent configuration—not repository **Review effort level**.
- The preview [Get Copilot cloud agent configuration for a repository](https://docs.github.com/en/rest/copilot/copilot-cloud-agent-management#get-copilot-cloud-agent-configuration-for-a-repository) response includes whether `copilot_code_review` is enabled, not which effort level is configured.
- GitHub documents configuring **Review effort level** only through the web UI ([configure code review](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review)).

You **can** set effort on an individual review request via supported REST/GraphQL review APIs ([changelog](https://github.blog/changelog/2026-10-02-copilot-code-review-api-support-and-new-default-effort-level/)); that is not the same as reading the repo’s default setting.

Because the default is not API-readable, PLATE does **not** ship a `doctor` or `adopt` check for “default effort is Lite” in this release ([#1095](https://github.com/akasper/plate/issues/1095)). Verify Lite manually during repo onboarding or cost-policy rollout (see also [actions-cost-rollout.md](migration/actions-cost-rollout.md)).

## Related artifacts

- Copilot review checklist skill: `.github/skills/code-review/SKILL.md` (shipped in template payload, [#1092](https://github.com/akasper/plate/issues/1092)).
- Actions and autostart cost controls: [agents/github-actions-and-copilot.md](agents/github-actions-and-copilot.md).
