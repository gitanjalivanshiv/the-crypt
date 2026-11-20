# How Kiro was used

Working draft for the Devpost write-up. Fill each section **as the work happens**, not from
memory on Dec 2. Keep concrete specifics: file paths, prompts, what failed.

Judges score Technological Implementation (20%) largely on this document. "We used specs and
hooks" scores nothing; "this hook caught this class of bug, here is the file" scores.

---

## Kiro surfaces — IDE / CLI / Web / Crew

Which were used, for what, and how they differed in practice.

> _TODO_

## Spec-driven development

How the three specs were structured, what was edited by hand before approving, where the
spec caught a design problem that vibe coding would have discovered only in code, and where
the spec got in the way.

> _TODO_

## Steering

Six files. Five always-on and deliberately lean, because always-on steering is injected into
every request; `demo-patient.md` is `inclusion: manual` and pulled in with `#demo-patient`
only when the patient is under discussion. Note which steering file changed Kiro's output
most visibly.

> _TODO_

## Agent hooks

Every hook is a `command` hook. Record the workflows automated and the cost reasoning —
command hooks run shell commands for zero credits, where agent hooks bill per firing.

> _TODO_

## MCP

The signals MCP server exposes analyzer findings as tools, so the persona *queries* facts
instead of guessing them. This is the mechanism behind the grounding rule. Record what
became possible that would otherwise have been impractical.

> _TODO_

## Property-based testing

Hypothesis against the citation verifier. Record the specific bugs PBT found that
example-based unit tests missed — fabricated paths, inverted ranges, off-by-one line ends,
CRLF and unicode mismatches.

> _TODO_

## Custom agents and Kiro powers

Which were used, in which surface, and what they changed.

> _TODO_

## Credit discipline

4,000 credits, no top-up. Model routing (Auto by default, Haiku 5.5 at 0.06x for mechanical
work, Opus 5.5 capped at 15 prompts), command hooks over agent hooks, one task at a time
rather than concurrent waves. Final actuals from `docs/CREDIT-BUDGET.md`.

> _TODO_

## Banishment rate (Medium)

Bands for the harness (`python -m medium.eval`), copied from `medium/eval/metrics.py`
(R3.8). Fixed in code before the first live run; not tuned to a result.

| Metric | Band | Reason |
|---|---|---|
| Guess share | ≤ 0.35 | Too lenient above this: the "guess" flag becomes a loophole the model hides behind instead of citing evidence. |
| All-guess turns | ≤ 0.15 of answered turns | Too lenient above this: such a turn is the one `classify_attempt` would route to a decline. |
| Turns with ≥ 1 banishment | 0.10 to 0.50 of turns | Below the lower bound the demo has no on-camera banishment; above the upper bound the ghost is unreliable. |
| Declined share | ≤ 0.15 | Too strict above this: the demo looks broken. |
| Verified share | ≥ 0.50 | A ghost that mostly guesses or is mostly rejected has little to say. |

Measured results: none yet (no live run).

## Skeleton change requests
Filed by the Medium spec (`.kiro/specs/medium/design.md` §7). The skeleton is edited only
through a change request, never as a side effect of a Medium task.

Each request states the requirement or lever, evidence, smallest proposed change and the
blocked Medium task (R9.2). SCR-2 to SCR-4 are opened only if a measured breach points at
them. SCR-1 is a nice-to-have. Evidence is "none yet" for all four until a harness run exists.

| ID | Need (requirement or lever) | Today | Smallest change | Blocks | Evidence |
|---|---|---|---|---|---|
| SCR-1 | File listing for the tree (R5.3) | No route exposes the code graph's files | `GET /snapshots/{ref}/files` listing paths | Nothing (workaround: findings plus cited files) | None yet |
| SCR-2 | `allowed_numbers` per app (lever) | `VerifyConfig()` built inline in `ask` | `ApiConfig.verify: VerifyConfig`, passed to `ask` | Only if the harness shows `unbacked_number` over-rejection | None yet (taken pre-emptively, see below) |
| SCR-3 | Grounding wording (lever) | `GROUNDING` is a constant | Optional persona-level addendum field, or a documented edit to the constant | Only if persona wording cannot fix the guess share | None yet |
| SCR-4 | Acceptance rule (lever) | `classify_attempt` not injectable | Accept `classify` as an argument to `run_grounded_turn`, current function as default | Only if all-guess turns breach their band | None yet |

### SCR-2: `allowed_numbers` per app. Taken pre-emptively, before Medium task 1.1.
Spec: `.kiro/specs/skeleton-amendment-scr2/`. Change: `ApiConfig.verify: VerifyConfig`
(default `VerifyConfig()`), passed as `cfg=cfg.verify` in the `ask` route of
`skeleton/api/app.py`. One test in `tests/api/test_ask.py`. Nothing under `skeleton/verify/`
changed.

The Medium spec says SCR-2 is opened only if the harness shows `unbacked_number`
over-rejection. It was opened before any harness run. Why: `allowed_numbers` was permanently
empty and the digit scan is strict by design, so that breach was the likeliest one.
Reactively it would have stalled Medium task 5.2, with the UI group blocked behind gate 5.3,
and the fix would have needed this same amendment days later. The default equals the old
inline value, so the harness measures the same thing as before.

The stop-condition process worked: the Medium spec filed the request instead of editing the
skeleton, and the request then went through its own spec (three tasks, one source file, one
test file). SCR-1, SCR-3 and SCR-4 stay reactive.

Checks after the change: 599 Python tests and 74 UI tests pass, `./scripts/check-verify.sh`
holds 100% line and branch coverage, import-linter is green (3 contracts exist in
`.importlinter`, not 4).
