# Skills Hub

PLATE is building toward a hub for **skills** (installable packs), **techniques** (documented practices), and **resources** (outside references agents consult but do not install). Full taxonomy and vetting rules are tracked in [#1206](https://github.com/akasper/plate/issues/1206) (design) and [#1202](https://github.com/akasper/plate/issues/1202) (machine-readable registry). This page is the curated **outside resources** index until the registry ships.

**Attribution rule:** Link and cite only. Do not copy substantial text or code from listed projects unless their license explicitly allows it and the notice travels with the copy. PLATE adopts *ideas* in original wording with credit (see [#1232](https://github.com/akasper/plate/issues/1232)).

## Outside resources

### [t3dotgg/tstack](https://github.com/t3dotgg/tstack)

| Field | Value |
| --- | --- |
| **What it is** | Nine agent prompt skills plus a Python `pr-wait` script focused on the pull-request lifecycle: file a PR, review, babysit CI and bots, merge (or stop before merge), modernize stale PRs, and take over another author’s PR. |
| **Maker** | Theo Browne ([@t3dotgg](https://github.com/t3dotgg)) |
| **License** | [MIT License](https://github.com/t3dotgg/tstack/blob/main/LICENSE), Copyright (c) 2026 Theo Browne. Use and adaptation require retaining the copyright and permission notice on substantial copies; PLATE does **not** vendor tstack—consult the upstream repo. |
| **Vetted** | 2026-11-01 (linked for attribution and comparison; see [#1238](https://github.com/akasper/plate/issues/1238)) |

**What PLATE took (ideas only, PLATE-original implementations):** Research [#1232](https://github.com/akasper/plate/issues/1232) mapped overlap and gaps. Landed or in-flight PLATE work inspired by tstack includes:

- **PR watcher guards** ([#1233](https://github.com/akasper/plate/issues/1233)) — required-check pending-by-omission, stable polls, restart-safe reporting, REST fallback patterns aligned with `pr-wait` guard ideas, not the upstream polling loop.
- **Pre-merge recheck and small review loops** ([#1234](https://github.com/akasper/plate/issues/1234)) — refresh PR state immediately before merge; decline out-of-scope review asks with a written reason and follow-ups (`AGENTS.md`, `address-pr-feedback` skill).
- **`modernize-pr` skill** ([#1235](https://github.com/akasper/plate/issues/1235)) — MODERNIZE / REWORK / CLOSE verdict with evidence, `git range-diff`, and `--force-with-lease`; never auto-close or auto-merge.

Other tstack themes (handoff credit, bounded second reviewer, “proof” wording) remain open under [#1236](https://github.com/akasper/plate/issues/1236), [#1237](https://github.com/akasper/plate/issues/1237), and [#1053](https://github.com/akasper/plate/issues/1053).

**Harness- and vendor-specific (adopter choices, not PLATE defaults):** Upstream skills assume tools such as [T3 Code](https://github.com/pingdotgg/t3code) (`watch_pull_request`, `delegate_task`), a “GPT Sol” reviewer loop, Greptile and Macroscope as gating review bots, and `agents/openai.yaml` for Codex. PLATE stays harness-neutral; Copilot review and `gh plate pr babysit` are the default surfaces unless an adopter opts in elsewhere.

**Reference only (cost):** The `council` skill (multi-provider review until consensus) is listed here for awareness only. It conflicts with PLATE cost goals; do not enable it as a default ceremony.
