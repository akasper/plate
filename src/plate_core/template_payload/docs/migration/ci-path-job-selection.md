# Path-based CI job selection

See the canonical guide in the plate-core repository:
`docs/migration/ci-path-job-selection.md` (copied on import-payload).

After bootstrap, copy `.agentic/ci-path-jobs.example.yml` to
`.agentic/ci-path-jobs.yml` and wire `.github/actions/plate-select-ci-jobs` into
your product CI workflow.
