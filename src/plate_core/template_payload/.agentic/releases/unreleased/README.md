# PLATE unreleased fragments

This directory holds release-note fragments not yet tied to a versioned release.

Author Feature/process changes as `<slug>.json` here (see PLATE fragment contract
in upstream `akasper/plate` / `docs` and `AGENTS.md`). At release cut, fragments
aggregate into `.agentic/releases/vX.Y.Z/`.

This starter file is included in the greenfield template payload so adoption
readiness (`core_ready`) can see a valid `.agentic/releases/unreleased/` layout
after `gh plate bootstrap --apply`.
