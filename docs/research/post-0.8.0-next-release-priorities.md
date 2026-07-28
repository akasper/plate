# Research: Post–v0.8.0 next-release priorities (Q&A session)

- **Issues:** #989, #990, #992 (product bet absorbed here); related #991 / #993 (Goals hybrid — separate Documentation work)
- **Session:** `qanda-2026-07-28-post-080`
- **Standing target:** #983 Next Release
- **Date:** 2026-07-28
- **Status:** Decisions recorded via PLATE-ANSWER; this note is the committed artifact for closure

## Context

**v0.8.0** shipped autonomy/adoption/packaging foundations, public **PyPI** (`plate-core==0.8.0`), **gh-plate** thin-shim sync, and release-track alignment. Open Question inventory was empty; a post-cut Q&A session seeded #989–#992 and captured human decisions via native TUI + Contemplation.

Related durable answers:

| Question | Issue | PLATE-ANSWER (example) |
|----------|-------|------------------------|
| Next release theme | #989 | https://github.com/akasper/plate/issues/989#issuecomment-5108543835 |
| Marketplace ranking | #990 | https://github.com/akasper/plate/issues/990#issuecomment-5108547866 |
| Product bet | #992 | https://github.com/akasper/plate/issues/992#issuecomment-5108554803 |

Curiosity storage mirrors under `docs/curiosity/answers/` (engine-written during record).

---

## #989 — What should land after v0.8.0?

### Decision

**Primary must-ship theme: adopter time-to-value.**

### Buckets for #983

| Bucket | Scope | Notes |
|--------|--------|------|
| **Must-ship** | Under-30m adopt / `import-payload` polish; docs + install path (pip + gh-plate + plugin); self-migrate verify UX and pin/target clarity | Highest leverage after foundations + public install surfaces already exist |
| **Should-ship** | Residual bugs and docs alignment from the 0.8.0 cut | Capacity-dependent |
| **Defer** | Deeper PM / fleet / feature–bug loop expansion as a *primary* theme; treating marketplace as the release product theme | Autonomy stacks remain maintenance-only (bugfixes OK) |

### Explicit non-choice

- Not “backlog groom only”
- Not “distribution completeness” as the product theme (PyPI + gh-plate already updated)
- Not autonomy-first as the next cut’s north star

### Follow-up

Define or refine an **Epic** (or ordered Feature stubs) under #983 for adopter time-to-value. Themes listed under #992 below are the recommended child outline.

---

## #990 — Marketplace publication vs product work

### Decision

**Parallel human track** — Tasks **#380** / **#381** do **not** block Next Release (#983).

| Track | Owner | Done signal |
|-------|--------|-------------|
| Product (#983 adopter theme) | Agents + human judgment on merges | Normal Feature/PR process |
| Marketplace #380 / #381 | Human | Task completion comment with `<!-- PLATE-TASK-CLOSED -->` (no secrets) |

### Reassess when

Promote marketplace only if **install friction evidence** shows absence of marketplace entries is the dominant adopter failure mode (new answer or Question; do not silently reprioritize).

### Explicit non-choices

- Block next release on marketplace
- Formal freeze / “defer past next cut” without reassess criteria
- Block only #381 while treating #380 as optional gate for the cut

---

## #992 — Product bet: adoption vs deeper autonomy

### Decision

**Primary product bet for the next 1–2 cuts: adoption under-30m polish** (consistent with #989).

### Themes (candidate Epic / Feature titles)

1. **Bootstrap / `import-payload` reliability** — clear next commands, conflict strategies, failure messages  
2. **Docs + install path consistency** — pip, `gh extension` / gh-plate pin, plugin marketplace install docs  
3. **Self-migrate verify UX** — pin vs target vs installed; no false drift after packaging cuts  
4. **First-Q&A seed / session path** — under-30m clock remains credible end-to-end  

### Non-goals (next 1–2 cuts)

- Deeper PM / fleet / feature-loop / scheduled-ops expansion as primary investment (bugfixes allowed)
- Marketplace as the product bet (#990 parallel human)
- v1.0 endless-lifecycle (#654) scope expansion

### Optional sequencing

Autonomy reliability may become the theme of the cut *after* the adopter path is crisp — not required by this answer.

---

## Synthesis for agents

```
Priority order for autonomous / semi-autonomous work targeting #983:
1. Adopter path reliability (bootstrap, import-payload, install docs, self-migrate verify, first-qa session)
2. Residual 0.8.0 bugs/docs
3. Do not prioritize PM/fleet/loop epics or marketplace automation over (1)
```

**Goals.md:** Hybrid rewrite decided under #991; implementation tracked as Documentation **#993** (not closed by this PR unless scoped in).

---

## Answer signal map (closure evidence)

### #989

- [x] Must-ship / should-ship / defer buckets with links — this document + #983 / #990  
- [x] PLATE-ANSWER recorded — comment 5108543835  
- [x] Follow-up path — themes for Epic/Features under #992 section (groom #983; not “no epic”)  

### #990

- [x] Ranking: parallel human track  
- [x] Owner + done-signal for #380/#381  
- [x] Reassess criterion: install friction evidence  

### #992

- [x] Primary bet: adoption under-30m  
- [x] 2–4 concrete themes  
- [x] Explicit non-goals  

---

## Closing

This file is the required git artifact for **#989**, **#990**, and **#992**. Land via PR with:

```
Closes #989
Closes #990
Closes #992
```

Do **not** close #991 / #993 here (Goals content rewrite remains open).
