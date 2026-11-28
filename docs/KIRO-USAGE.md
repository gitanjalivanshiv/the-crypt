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
| SCR-5 | Output budget and failure diagnosis (defects) | `LLMRequest.max_tokens` is 1024; `generator_error` detail is the class name only | Default 4096, `ToolLoopGenerator(max_tokens=)`, `AttemptRecord.failure_detail` | Every live harness run | Harness run 1 (see below) |
| SCR-6 | Computed figures cannot be spoken (Debt Collector R8.3) | `Figure` is checked against `Finding.metrics`, and `VerifyConfig.allowed_numbers` is fixed when the app is built, so a principal, interest or total in prose is banished as `unbacked_number` | A per-request or per-snapshot source of allowed numbers, or a second figure kind for values the app computes | none (workaround in place: the UI shows computed numbers from the ledger payload and the persona refers to the ledger). Opened only if the demo needs interest in the collector's own sentences | none yet |
| SCR-7 | Findings have no pagination (Debt Collector R8.3) | `list_findings` clamps at 100 with no offset or cursor, while the patient has 495 findings | An `offset` argument, or a `total_severity` in the response | none (workaround in place: the ledger asks per analyzer and reports `truncated`). Opened only if truncation visibly distorts the ledger on the patient | none yet |

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
holds 100% line and branch coverage, import-linter is green (4 contracts kept).

### SCR-5: output budget and failure diagnosis. Found by the harness, not by review.
Spec: `.kiro/specs/skeleton-amendment-scr5/`. Nobody found this by reading the code. The
first live harness run aborted after 3 consecutive provider errors and reported a 66.7%
declined share. Neither number measured the grounding rule. Instrumenting the adapter showed
`ProviderError: response truncated: stop_reason=max_tokens (max_tokens=1024)`. A grounded
answer quotes the source verbatim in every citation, so three or four claims exceed 1024
tokens, the adapter raises (Medium R1.8, correctly), both attempts fail the same way and the
turn declines.
Two defects: the 1024 default, and `flow.py` recording only the exception class name, so the
message that named the cause never reached `AttemptRecord`, `AnswerResult` or the run files.
The second cost a full diagnostic session. Fixes: default 4096 plus a
`ToolLoopGenerator(max_tokens=)` argument; a message of up to 300 characters in a new
`AttemptRecord.failure_detail`, kept out of the retry prompt and out of logs.
Run 1's numbers were an artefact. They were discarded, not tuned against, and the harness was
re-run from scratch.
Re-run after the fix (`--runs 2`, run 1 of 2 only): the first five turns all answered, with
no truncation, then todo-2, todo-3 and file-dist failed and the run aborted again on 3
consecutive provider errors. A follow-up diagnostic showed `failure_detail` working, but the
adapter reports only `ProviderError: BadRequestError status=400`, and the harness drops the
attempt detail for provider-failed turns. The harness gap was then closed in its own spec (`.kiro/specs/harness-failure-detail/`), but
the adapter still redacts the 400 body. A direct SDK call showed the cause: `invalid_request_error:
Your credit balance is too low`, for the account behind `ANTHROPIC_API_KEY`. The numbers from
these runs are not a measurement of the bands.
This is the argument for ordering the harness before the UI. Had the UI come first, the same
fault would have appeared as a ghost that mostly declines, with the UI as the suspect. The
harness found it in minutes on a CLI, and it cost one amendment spec, not a UI debugging
session.

---

## Banishment rate: measured result (Medium tasks 5.1 to 5.3)

Two runs against the pinned demo patient (`setuptools` at `049ae8e30835`). Both ended early
on provider quota, not on failure, so they are short — but they agree closely, and they were
produced by **two different providers**: the first on the Anthropic adapter, the second on
Gemini after the provider seam was added.

| | 2026-11-20 | 2026-11-28 | combined |
|---|---|---|---|
| Turns answered | 5 | 4 | 9 |
| Judged claims | 30 | 16 | 46 |
| Verified | 26 (86.7%) | 14 (87.5%) | 40 (87.0%) |
| Guess | 4 (13.3%) | 2 (12.5%) | 6 (13.0%) |
| Banished | 0 | 0 | **0** |
| Declined turns | 0 | 0 | **0** |
| First attempt accepted | 5/5 | 4/4 | 9/9 |

Raw runs: `medium/eval/runs/20261120T191841Z-1.json`,
`medium/eval/runs/20261128T143330Z-1.json`.

### Bands

Four of five bands pass comfortably, on both runs:

- Verified share 87.0%, floor 50%. **Pass.**
- Guess share 13.0%, ceiling 35%. **Pass**, and this is the number that matters most: it
  rules out the failure mode the band existed to catch. The model is *not* marking claims as
  guesses to dodge verification.
- Declined share 0%, ceiling 15%. **Pass.**
- All-guess turns 0%, ceiling 15%. **Pass.**
- Turns with a banishment 0%, band 0.1 to 0.5. **Breached, at the floor.**

### Decision: accept the breach, do not tune

The banishment band assumed the model would sometimes fabricate a file, a line range or a
number, and that the verifier would be seen catching it. Across 46 judged claims on two
providers, it never did. Nothing was rejected because nothing needed rejecting.

That is the system working, not failing. Tuning persona wording to *induce* banishments
would be making the ghost worse on purpose to make a metric look right.

Two consequences follow, both recorded rather than acted on by tuning:

1. **The demo must show a banishment deliberately.** Waiting for one is not a plan; on this
   evidence it may not happen on camera at all. Feeding a fabricated citation through the
   real verifier produces a genuine rejection with a real reason code, no model involved, so
   the signature moment stays honest while being reliably reproducible.
2. **The band was a hypothesis written before any measurement**, as R3.8 required, and it
   turned out to encode an assumption about model behaviour rather than a property of the
   system. Keeping it unchanged and recording the breach is more useful than retrofitting
   the band to the result.

### Why the runs are short

Both aborted on three consecutive provider errors. Neither abort was a grounding failure:
the first exhausted a trial balance, the second a free-tier quota. The rate-limit work
(5/15/30 s backoff honouring the server's `retryDelay`, and 15 s pacing between turns)
addresses the per-minute case; a daily quota it cannot. Nine turns is too few to call a
rate, which is why the numbers above are reported as a measurement with its sample size
visible rather than as a tuned result.
