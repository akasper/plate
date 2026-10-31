# Path-based CI job selection

See the canonical guide in the plate-core repository:
`docs/migration/ci-path-job-selection.md` (copied on import-payload).

After bootstrap, copy `.agentic/ci-path-jobs.example.yml` to
`.agentic/ci-path-jobs.yml` and wire `.github/actions/plate-select-ci-jobs` into
your product CI workflow.

Scheduled full-suite example (not auto-enabled):
`docs/examples/plate-ci-scheduled-full-suite.workflow.yml.example` — copy into
`.github/workflows/` after you add optional jobs.
