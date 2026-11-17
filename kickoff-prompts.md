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

The skeleton is built and green. Check `.kiro/specs/skeleton/` for what exists before
assuming anything; the names below are real modules, not placeholders.

> Create a feature spec named `medium` for app 1, The Medium, per `.kiro/steering/`.
>
> The skeleton is complete: ingest, signals, personas, verify, mcp, ui-shell and api are
> built, tested and green. This app **consumes** it and adds **no code under `skeleton/`**.
> If something here appears to need a skeleton change, stop and say so — that is a skeleton
> design bug, not a licence to special-case the app. `import-linter` will fail the build
> either way.
>
> **Consume the API, do not rebuild it.** `skeleton/api` already exposes snapshot ingest,
> findings, file facts and `POST /snapshots/{ref}/ask`, which runs the grounded turn and
> returns `AnswerResult`. The app is a persona config, a theme, a thin UI and a few routes
> of its own. It does not re-implement verification, tool routing or prompt assembly.
>
> **The app folder is top-level `medium/`**, not `apps/medium/`. A Skeleton Crew submission
> must show two separate application folders at the repository root.
>
> Scope:
>
> 1. **The provider adapter** (see "Where the adapter lives" below). First real
>    `LLMClient` implementation, in a new top-level `providers/` package. This is the first
>    time the system talks to a real model, so it belongs in this spec.
> 2. **Persona TOML** for the ghost: voice, goals, `allowed_tools`, `example_lines`,
>    `decline_line`. No example line may contain a digit — the loader warns about this and
>    the digit scan will banish copied numbers.
> 3. **Interview loop**: question -> `POST /ask` -> render `AnswerResult` unchanged.
>    `ChatPanel` already renders claims, guesses, banishments and declines; do not reshape
>    the payload.
> 4. **File-tree possession**: `FileTree` already takes `cited` and `active` props and
>    expands ancestors. Wire the app's state to them.
> 5. **Resurrection plan**: generate requirements, design and tasks for modernising the
>    analysed system, every claim citation-backed through the same verified path. A plan
>    that bypasses the verifier is not acceptable.
> 6. **The CRT theme** for this app, built from the shared `ThemeProvider` tokens. No
>    component may be forked or branched on `theme.id`.
> 7. **A banishment-rate harness** (see below).
>
> In the tasks phase, keep R8.1: one subsystem, at most three files per task. Mark cuttable
> tasks explicitly as the skeleton plan does.

### Where the adapter lives — settle this, do not let the spec choose

`skeleton/personas/llm.py` defines `LLMClient` as a one-method async Protocol, and no
adapter exists anywhere: R7.3 kept provider SDKs out of the skeleton, and `import-linter`
enforces it with a `forbidden_modules` rule naming `anthropic`, `openai` and `boto3`.

The adapter cannot go in `skeleton/` (the contract forbids it) and must not go in `medium/`
(then `debt-collector/` would have to import from a sibling app, which breaks app
independence). So:

- A **new top-level `providers/` package** holds it. Both apps import it; `skeleton/` never
  does.
- Add a fourth `import-linter` contract: `skeleton` must not import `providers` either.
- Keep it thin. Translate `LLMRequest` to the provider's call, map tool calls back to
  `ToolCall`, surface errors as exceptions the flow already treats as a failed attempt
  (R4.15). No retry logic: the flow's one-regeneration rule owns that.
- The API still takes an `LLMClient` by argument, so tests keep using `FakeLLMClient` and
  nothing in `skeleton/` learns the provider's name.

### The banishment-rate harness — the point of this spec

Watch item 1 has been unmeasurable until now, because nothing has run a real model. The
Medium is the first thing that does, so it measures it.

Both failure modes kill the demo, in opposite directions:

- **Too lenient** — the model learns that flagging a claim as a guess avoids rejection, so
  everything comes back a guess, no banishment ever fires, and the signature moment never
  happens on camera.
- **Too strict** — the digit scan or the citation rules reject nearly everything, every
  answer reaches the decline path, and the demo looks broken rather than principled.

Require a task that runs a fixed set of roughly 20 questions against the real patient and
reports: share of claims verified, share banished by reason code, share marked guess, and
share of turns that declined. Record the numbers in `docs/KIRO-USAGE.md`. The levers, in
order of preference, are `cfg.allowed_numbers`, the `GROUNDING` prompt wording, and the
`classify_attempt` seam in `skeleton/verify/flow.py` — which exists precisely for this.

**Do this before the UI work, not after.** If the rate is wrong, the fix is in prompts and
config, and you want to find that out while there is still time to change it.

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
    "action": { "type": "command", "command": "./scripts/run-tests.sh tests/signals" }
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
    "action": { "type": "command", "command": "./scripts/run-tests.sh tests/verify" }
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
