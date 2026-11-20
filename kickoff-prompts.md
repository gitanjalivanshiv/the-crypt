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

## Prompt 2b — Skeleton amendment: SCR-2 (run before the Medium tasks)

The Medium spec filed four skeleton change requests. **SCR-2 is taken now, pre-emptively,
before task 1.1 of the Medium.** The other three stay reactive as that spec has them.

Why now rather than on breach: `allowed_numbers` is empty and the digit scan is strict by
design, so `unbacked_number` over-rejection is the most likely band breach in the harness.
Reactively it stalls Medium task 5.2 with the whole UI group blocked behind gate 5.3, and
resolving it then needs this same amendment anyway, several days later. The amendment
defaults to exactly today's behaviour, so it changes nothing that the harness measures.

> Create a feature spec named `skeleton-amendment-scr2`.
>
> **Scope: one change. Resist every temptation to widen it.** This spec exists because the
> Medium spec's stop-condition process worked and filed a change request; it is not an
> invitation to refactor the API.
>
> The change: `skeleton/api/app.py` line 272 passes `cfg=VerifyConfig()`, constructed
> inline, to `run_grounded_turn`. `VerifyConfig.allowed_numbers` is therefore permanently
> the empty frozenset and no caller can set it. `ApiConfig` has six fields and none is
> `verify`.
>
> Make it injectable:
>
> 1. Add `verify: VerifyConfig = VerifyConfig()` to `ApiConfig`. The default must be exactly
>    the current value, so behaviour is unchanged for every existing caller and every
>    existing test.
> 2. At line 272 pass the configured value instead of a fresh one. `cfg` is already the
>    `ApiConfig` in that closure's scope, so this is `cfg=cfg.verify`. That reads oddly
>    because `run_grounded_turn`'s keyword is also named `cfg`; use a local alias if it is
>    clearer, but do not rename either parameter.
> 3. One test: an app built with `ApiConfig(verify=VerifyConfig(allowed_numbers=frozenset({"42"})))`
>    accepts a claim whose prose contains a bare `42`, and an app built with the default
>    rejects the same claim with `unbacked_number`. Use `FakeLLMClient`; no network.
>
> Out of scope, explicitly: SCR-1, SCR-3 and SCR-4; any other `ApiConfig` field; any change
> under `skeleton/verify/`; any change to `GROUNDING`; any new route; threading
> `VerifyConfig` anywhere else.
>
> Constraints:
> - `skeleton/verify/` is untouched, so the 100% branch-coverage gate is unaffected. If a
>   task wants to touch it, the task is wrong.
> - All four import-linter contracts keep passing.
> - The full suite stays green: 598 Python tests and 74 UI tests at the time of writing.
>
> This should be **two or three tasks**. If the task list comes back longer, the scope has
> drifted and the spec needs cutting before any task runs.

After it is done, run the full suite and `./scripts/check-verify.sh` before starting Medium
task 1.1. Then record in `docs/KIRO-USAGE.md`, under "Skeleton change requests", that SCR-2
was taken pre-emptively and why — the stop-condition discipline visibly working is worth
more at judging than a quiet edit.

## Prompt 2c — Skeleton amendment: SCR-5 (blocks Medium task 5.1)

Found by running the harness. The first live run aborted after 3 consecutive provider
errors and reported a 66.7% declined share. **Neither number measures the grounding rule.**
The real error, recovered by instrumenting the adapter:

```
ProviderError: response truncated: stop_reason=max_tokens
   max_tokens=1024  system_len=4434  msgs=13
```

An answer carries verbatim source quotes in every citation, so a few claims exceed 1024
output tokens. R1.8 of the Medium spec correctly raises on truncation; the default is
simply far too small for the payload this system produces. Every failing turn failed this
way, both attempts, so the turn declined. Run 1's numbers are an artefact and must be
discarded, not tuned against.

> Create a feature spec named `skeleton-amendment-scr5`.
>
> **Scope: two defects in the skeleton, found by the Medium's harness. Nothing else.**
>
> **Defect 1 — the output budget makes grounded answers impossible.**
> `skeleton/personas/llm.py` line 36 sets `max_tokens: int = 1024` on `LLMRequest`, and
> `ToolLoopGenerator` in `skeleton/personas/generator.py` never overrides it. A grounded
> answer embeds a verbatim `quote` per citation, so three or four claims exceed the budget,
> the response is truncated, and the adapter raises. Both attempts fail the same way and
> the turn declines.
> - Raise the default to **4096**.
> - Let `ToolLoopGenerator` take `max_tokens` as a constructor argument defaulting to that,
>   so an app can raise it without another skeleton change.
> - Output tokens are billed as generated, so a higher ceiling costs nothing when unused.
>
> **Defect 2 — a failed attempt is undiagnosable.**
> `skeleton/verify/flow.py` line 66 records `AttemptFailure("generator_error",
> type(exc).__name__)`. The detail is the class name alone, `"ProviderError"`, so the
> message that names the actual cause never reaches `AttemptRecord`, the `AnswerResult`, or
> the harness run files. Defect 1 cost a full diagnostic session for this reason.
> - Record the message as well, as `f"{type(exc).__name__}: {exc}"`, truncated to 300
>   characters.
> - `skeleton/verify/` is under the 100% line-and-branch coverage gate and `pragma: no
>   cover` is banned there. Extend the existing flow tests to cover both paths rather than
>   weakening the gate. **If this defect cannot be fixed without touching the gate, stop and
>   report; ship defect 1 alone.**
> - Safety: the generator is untrusted, so the message may carry model text. Truncate, never
>   log it outside the structured record, and keep the existing tests that assert no key or
>   prompt leaks.
>
> Out of scope: any other skeleton change, SCR-1, SCR-3, SCR-4, any retry or backoff logic
> (`max_retries=0` stays), any change to the adapter, the harness, the bands or the question
> set.
>
> Constraints: all four import-linter contracts keep passing; the full suite stays green
> (599 Python, 74 UI at the time of writing); `./scripts/check-verify.sh` stays at 100%.
>
> This should be **three or four tasks**. Longer means the scope drifted.

After it lands, discard run 1 and re-run the harness from scratch:

```
uv run python -m medium.eval --runs 2
```

Record in `docs/KIRO-USAGE.md` under "Skeleton change requests" that SCR-5 was found by the
harness rather than by review — the harness earning its place before the UI was built is
exactly the argument for ordering it first, and it is worth saying so in the write-up.

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
