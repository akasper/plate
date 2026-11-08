# Trusted policy runtime — threat model (#1449)

## Assets

- Branch-policy outcomes (`integration-base`, `main-source`) that gate merges on release tracks.
- `.agentic/policy-runtime.json` module manifest.

## Untrusted inputs (per PR event)

- PR head commit: workflow job definitions, shell steps, `src/plate_core`, root packages, manifests.
- PR body and labels (issue-context inputs).

## Trusted boundary (what this PR implements in code)

1. **Policy modules** load only from `PLATE_POLICY_PYTHONPATH`, prepared from `git archive origin/<default_branch>` (`src/plate_core` + manifest).
2. **No workspace fallback.** If default-branch archive cannot satisfy the manifest, the job **fails** (fail-closed).
3. **Isolated CWD:** gate CLIs run under `PLATE_POLICY_RUN_DIR` (empty temp dir) with `PYTHONNOUSERSITE=1` so workspace-root packages cannot shadow `PYTHONPATH`.
4. **Provenance check:** `policy_runtime_verify --require-provenance` asserts imported modules’ `__file__` paths live under the trusted `src` tree.

## Not enforced in this repository (deployment prerequisite)

- **Workflow definition** for `pull_request` still comes from the PR merge ref until merged; a malicious PR could edit steps. Only default-branch **`main`** (or org-pinned workflow/App identity) can make the *check execution path* authoritative — e.g. plate-lifecycle App or a workflow version pinned to `main` via rulesets requiring that file from default branch.
- **Merging to `release-minor` alone** does not populate `main`; archive-on-`main` trusted runtime requires a **separate release/deploy** to default branch.
- **PyPI `plate-core==0.9.0`** lacks integration gates; adopters must vendor default-branch `src` or install a **published** wheel built from a release that includes required modules.

## Operator expectations

| Scenario | Expected pr-gates behavior |
|----------|--------------------------|
| Default branch lacks vendored policy + manifest | Prepare step fails; branch-policy gates do not run authoritatively |
| PR attempts to weaken archive/fallback steps | Job fails closed (no fallback path) |
| Clean adopter, no vendor, only PyPI 0.9.0 | `ensure_plate_core` / manifest verify fails |
| Clean adopter, installs wheel built from current plate-core | Manifest verify passes in isolated venv |
