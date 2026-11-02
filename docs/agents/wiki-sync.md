# Wiki Sync

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../AGENTS.md).

## Wiki Sync Rules

The **Sync to Wiki on Merge** workflow is opt-in. Agents should not enable broad wiki writes without human approval. Prefer scoped page updates, provenance comments, auditable commits, and reversible changes. If wiki synchronization is requested but not configured, add `need:wiki-sync` and escalate.

The `docs/wiki/Goals.md` page (PLATE convention from #224/#229/#266) is a recommended default-scoped file for wiki sync when present. Bootstrap seeds it (with flag/interactive support) when wiki is enabled and the page is absent. Health surfaces report `goals_page_present` as a nudge for adoption. Agents should read it as primary signal for Information Audits (#218).
