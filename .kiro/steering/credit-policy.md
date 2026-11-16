---
inclusion: always
---

# Credit policy

Budget: **4,000 Kiro credits, one-time, no top-up.** Redeem by 2026-12-04; redeemed credits
expire 2026-12-31 23:59 PT. Full budget and maths: `docs/CREDIT-BUDGET.md`.

Unused credits after the 2026-12-04 submission are worthless. The risk is not finishing with
a surplus — it is burning the allotment in week one on automation and then hand-coding the
demo. Spend deliberately, not sparingly.

## Model routing

`Auto` (1.0x) is the default for everything. Deviate only per this table.

| Work | Model | Multiplier |
|---|---|---|
| Default: specs, design, implementation | **Auto** | 1.0x |
| Boilerplate, scaffolds, fixtures, docstrings, config, repetitive edits | **Claude Haiku 5.5** | **0.06x** |
| Focused bug fixes, code review, a stalled Auto task | Claude Sonnet 5.5 | 1.3x |
| Genuinely hard: verifier semantics, code-graph design, MCP contract | Claude Opus 5.5 | 2.0x |
| Forbidden on this project | Fable 5.1 (6x), GPT-5.6 Sol (4.4x), Grok 4.7 (2.7x), Kimi K3 (2.4x) | — |

- Haiku 5.5 jumps **0.06x → 0.3x above 100K tokens of context**. Use it in short, fresh
  sessions only. A long Haiku session loses most of its advantage.
- Opus 5.5 is capped at **15 prompts for the whole project**. Log each use in
  `docs/CREDIT-BUDGET.md`. If you want a sixteenth, something upstream is wrong.

## Rules

1. **Hooks are `command` actions, never `agent` actions.** A shell command costs zero
   credits; an agent hook costs at least one credit *every time it fires*. At a normal
   ~200 saves a day over 18 days an agent save-hook alone exceeds the entire allotment.
   Tests, linting, and the `.gitignore` guard all run as shell commands.
2. **Start spec tasks with the "Start task" control, not by asking in chat.** Chatting to
   steer spec mode spends extra on coordination for the same work.
3. **Never "run all tasks".** Tasks execute concurrently in waves; one bad design document
   multiplies into a whole wave of wasted work with no point to intervene. Run tasks one at
   a time, read the diff, commit, then start the next.
4. **Regenerate at most once.** If the second attempt is wrong, the spec is wrong. Fix the
   requirement or the design, cheaply, by hand — then re-run.
5. **Start a fresh session per task.** Context carried between tasks is re-billed on every
   turn and pushes cheap models over their token thresholds.
6. **Do zero-credit work outside Kiro**: README, LICENCE, Devpost copy, video script, blog
   post, config files, commit messages. Kiro usage is judged on the artefacts in `/.kiro`
   and the write-up, not on credits consumed.
7. **Keep always-on steering lean.** Every file in this directory is injected into every
   request. Context-heavy reference material uses `inclusion: manual` and is pulled in with
   `#name` only when needed.
8. **Log actuals.** After each spec phase, read the usage dashboard and record real credits
   in `docs/CREDIT-BUDGET.md`. The estimates there are derived, not published; replace them
   with measurements as soon as measurements exist.

## Checkpoints

Stop and re-plan at **1,000 / 2,000 / 3,000** credits consumed. At 3,000 with the demo not
yet deployed, stop generating and hand-finish: a submitted rough demo beats a polished one
that misses 14:00 PT on 2026-12-04.
