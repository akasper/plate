# Interactive Epic Planning

Part of the PLATE agent operating rules (formerly in `AGENTS.md`). The always-loaded core is [AGENTS.md](../../AGENTS.md).

<!-- PLATES-CORE:BEGIN interactive-epic-planning -->
## Interactive Epic Planning

When a user expresses intent to plan a new epic, offer a guided Q&A session that extracts requirements and creates the Epic issue and child stubs incrementally. **Present questions using host-native look-and-feel** (Copilot CLI native TUI, Grok Build `ask_user_question`, etc.) rather than free-form chat. This workflow applies in Copilot chat. MCP and CLI surfaces are reserved for Phase 2.

### Intent Detection

Evaluate incoming messages against a 3-tier signal system:

| Tier | Score | Action |
|---|---|---|
| HIGH | ≥ 5 pts | Ask the confirmation question immediately |
| MEDIUM | 3–4 pts | Watch for a follow-up trigger in the next turn; do not interrupt |
| LOW | ≤ 2 pts | Ignore; do not interrupt the conversation |

Signal weights (cumulative): "plan" or "epic" keyword (+2), explicit "feature" or "capability" keyword (+1), question phrasing or "what would it take" (+1), "breaking down" or "scoping" phrasing (+1), scope-size language ("big", "large", "multi-week") (+1), explicit request ("let's create an epic") (+2).

Confirmation question: *"It sounds like you want to plan a new epic. Should I start a structured planning session? I'll ask a few questions and create the Epic issue and child stubs on GitHub as we go."*

If the user declines, drop to MEDIUM watch state. Do not ask again in the same conversation unless the user re-initiates.

### Minimum Creation Threshold

Create the Epic GitHub issue as soon as you have:
- A name (title) for the epic
- A one-sentence problem statement

Do not wait for full AC or scope before creating. Use `need:refinement` on child stubs.

### Duplicate Detection

Before creating, search for open Epic issues with similar titles:

```bash
gh issue list --repo OWNER/REPO --label Epic --state open --json number,title
```

Compute Jaccard similarity on title tokens. If any result scores ≥ 0.5, warn the user and offer:
1. Add child issues to the existing Epic instead
2. Create a new Epic anyway (distinct scope)
3. Cancel and open the existing Epic for review

### Q&A Phase

Run at most 8 turns. Each turn = one agent question + one user answer.

**Acceptance criteria arc (turns 1–3):**
1. "What does success look like when this epic is done?"
2. Probe: "What's the most important part of that — what has to work for this to be useful?"
3. Anchor: "How would you know it's truly complete — what's the 'done' signal?"

**Scope arc (turns 4–6):**
4. "What's explicitly in scope for this epic?"
5. "What are you explicitly NOT trying to solve with this epic?"
6. "Are there any epics, issues, or external changes this depends on?"

**Fast path:** If the user says "that's enough" or "I'll fill in the rest," stop at 3 turns minimum.

### Incremental Issue Updates

After each Q&A turn, update the Epic issue body using `gh issue edit`:

```bash
gh issue edit <NUMBER> --body-file -
```

Store session state in an HTML comment at the end of the body:

```html
<!-- PLATE_SESSION_STATE: {"turn": 3, "ac": [...], "scope_in": [...], "scope_out": [...]} -->
```

Post a `📝 Updated #N` signal in the chat to confirm each update.

### Progressive Child-Issue Creation

Create child stubs in this order: Research → Design → Feature. Create each stub as soon as the need is clear — do not wait until the end of the session.

Required fields for every stub:
- Title
- Type label (`Research`, `Design`, or `Feature`)
- Epic label (`Epic: <slug>`)
- `need:refinement` label
- Body: one-line summary + `<!-- PLATES-EPIC: #<epic-number> -->`

### Session Resumption

Reconstruct state from the `PLATE_SESSION_STATE` HTML comment in the Epic body. Re-entry prompt: *"I found a planning session in progress for Epic #N. Would you like to continue from turn [X], or start over?"*

### Completion

When the session ends (turn budget exhausted or user signals done), post a planning summary comment on the Epic issue listing:
- Final AC items captured
- Scope in/out items
- All child issues created (with numbers)
- Suggested next steps (merge PRs for Research stubs first)
<!-- PLATES-CORE:END interactive-epic-planning -->
