# Kickoff prompts

Paste these into Kiro in order. They are written to be **specific enough to get a usable
result on the first generation**, because a regeneration costs as much as the original.

Before pasting anything:

1. `.kiro/steering/` is committed and Kiro has loaded it. The steering files carry the
   constraints, so these prompts do not repeat them — repeating context costs credits and
   invites contradictions.
2. Model is set to **Auto**. Check it at the start of every session.
3. Read `.kiro/steering/credit-policy.md`. The two rules that matter most: start tasks with
   the **Start task** control rather than chat, and **never run all tasks**.

---

## Prompt 1 — the skeleton spec

> Create a feature spec named `skeleton` for The Crypt, following the steering files in
> `.kiro/steering/`.
>
> Scope: **only** the shared skeleton in `skeleton/`. Not `medium/`, not `debt-collector/`.
> Anything persona-specific belongs in a later spec.
>
> The skeleton provides six subsystems:
>
> 1. **Ingest** — accept a public git repo URL or an uploaded archive; produce a code graph
>    of files, symbols, and imports using tree-sitter with the **Python grammar only**;
>    attach git history metadata (per-file commit count, last-modified date, author count).
>    Pin and record the analysed commit SHA. Enforce a size limit and a clone timeout.
> 2. **Signals** — a plugin protocol for analyzers plus three analyzers for v1: `churn`,
>    `staleness`, `todo_age`. Every finding carries `analyzer`, `file`, `line_start`,
>    `line_end`, `evidence` (a verbatim slice), `severity` (0.0–1.0, computed in code), and
>    `metrics` (the raw numbers a persona is permitted to quote). Design `complexity`,
>    `dependency_age`, and `dead_code` as the same protocol but do not implement them yet.
> 3. **Personas** — a TOML config format (voice, goals, allowed tools, example lines) and a
>    loader, so a new persona needs no change under `skeleton/`.
> 4. **Verify** — the citation verifier from `grounding-rule.md`, including the reject-and-
>    regenerate-once behaviour and the structured failure reason the UI renders as a
>    banishment.
> 5. **MCP** — a server exposing the signals as tools, so a persona queries facts rather
>    than guessing them.
> 6. **UI shell** — themeable React components: CRT terminal frame, file tree with
>    highlight-on-cite, chat panel, meter, and sound hooks. Two themes, one component set.
>
> Produce requirements with acceptance criteria first. Stop there and wait for my review
> before writing the design.
>
> In the tasks phase, size each task so it touches **one subsystem and at most three
> files**, and order them so `verify` and its Hypothesis property-based tests come before
> any persona work. The verifier is the component that must not have an untested branch.

**Review the requirements by hand before approving.** Editing a requirement costs nothing;
discovering it was wrong after ten tasks costs the tasks and their rework.

---

## Prompt 2 — The Medium

Only after the skeleton spec's tasks are executing cleanly.

> Create a feature spec named `medium` for app 1, The Medium, per `.kiro/steering/`.
>
> It consumes `skeleton/` and adds **no code under `skeleton/`**. If something here appears
> to require a skeleton change, stop and tell me — that is a skeleton design bug, not a
> reason to special-case the app.
>
> Scope:
> - A persona TOML for the ghost: voice, goals, allowed MCP tools, example lines.
> - An interview loop: user question → MCP signal queries → grounded answer with citations
>   → verification → render or banish.
> - File-tree possession: the tree highlights each file as the ghost cites it.
> - A resurrection plan generator emitting requirements, design, and tasks for modernising
>   the analysed system, every claim citation-backed.
> - The CRT theme for this app, built from the shared UI shell.

---

## Prompt 3 — The Debt Collector

> Create a feature spec named `debt-collector` for app 2, per `.kiro/steering/`.
>
> Same constraint: consumes `skeleton/`, adds nothing under it.
>
> Scope:
> - A persona TOML for the collector.
> - Debt itemisation: each finding becomes a line item with principal and **interest**
>   (estimated cost of leaving it). The interest formula lives in code, not in the prompt,
>   and its inputs come from `Finding.metrics` — the model never does arithmetic.
> - Escalating notices: tone and urgency rise with total severity.
> - A debt meter that falls as the user accepts refactors; the largest debts render as
>   boss fights.
> - A ranked repayment plan, ordered by interest per unit of effort.
> - The collector theme, from the same shared UI shell.

---

## Hooks — command, never agent

Agent hooks bill **at least one credit every time they fire**. A `PostFileSave` agent hook
over 18 days of normal editing can exceed the entire 4,000-credit allotment. Command hooks
run a shell command and cost **nothing**.

No hook in this project needs to write code, so no hook in this project is an agent hook.

Create these in `.kiro/hooks/` as JSON files — do **not** ask Kiro to generate them, that
is a credit spent on four lines of config:

`.kiro/hooks/test-signals-on-save.json`
```json
{
  "version": "v1",
  "hooks": [{
    "name": "Test signals on save",
    "trigger": "PostFileSave",
    "matcher": "^skeleton/signals/.*\\.py$",
    "action": { "type": "command", "command": "uv run pytest tests/signals -q" }
  }]
}
```

`.kiro/hooks/verify-on-persona-change.json`
```json
{
  "version": "v1",
  "hooks": [{
    "name": "Verify citations when a persona changes",
    "trigger": "PostFileSave",
    "matcher": "personas/.*\\.toml$",
    "action": { "type": "command", "command": "uv run pytest tests/verify -q" }
  }]
}
```

`.kiro/hooks/guard-kiro-committed.json`
```json
{
  "version": "v1",
  "hooks": [{
    "name": "Guard: .kiro must never be gitignored",
    "trigger": "PostFileSave",
    "matcher": "^\\.gitignore$",
    "action": { "type": "command", "command": "./scripts/check-kiro-committed.sh" }
  }]
}
```

The `.kiro` guard also runs as a real git `pre-commit` hook and in CI, because a Kiro hook
only fires while Kiro is open and this one is a disqualification risk. Install it with
`./scripts/install-git-hooks.sh`.

Verify the trigger names and JSON shape against Kiro's current hooks documentation before
relying on them — hook schemas have changed between CLI versions.

---

## Order of work

1. Create the repo and push `.kiro/`, `LICENSE`, `README.md`. **Confirm MIT shows in the
   GitHub About panel.**
2. Open the repo in Kiro; confirm the steering files are loading.
3. Run **Prompt 1**. Review and edit the requirements by hand. Approve. Review the design.
   Approve. Review the tasks.
4. Execute skeleton tasks **one at a time** with the Start task control. Read each diff.
   Commit after each. Never run all tasks.
5. Record actual credit usage in `docs/CREDIT-BUDGET.md` after the first three tasks and
   recompute the plan against measured numbers.
6. Repeat for **Prompt 2**, then **Prompt 3**.
7. Fill `docs/KIRO-USAGE.md` as you go, not on Dec 2.
