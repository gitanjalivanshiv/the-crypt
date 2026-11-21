# Implementation Plan: skeleton-amendment-scr5

Four tasks. If this list grows, the scope has drifted: cut the spec before running any task. No retry logic, adapter, harness, bands or question-set change in any task.

- [x] 1. Raise the output budget (Defect 1)
  - `skeleton/personas/llm.py`: `LLMRequest.max_tokens` default 4096.
  - `skeleton/personas/generator.py`: `ToolLoopGenerator.__init__(..., max_tokens: int = 4096)`, passed on the `LLMRequest`.
  - Tests: default request is 4096; the generator sends the default and an overridden value on every request, including tool rounds.
  - Check: `scripts/run-tests.sh tests/personas` and `tests/providers` green.
  - _Requirements: R1.1, R1.2, R1.3, R1.4_

- [x] 2. Record the failure message (Defect 2)
  - `skeleton/verify/flow.py`: detail is `f"{type(exc).__name__}: {exc}"[:300]`; `_record` fills `failure_detail`.
  - `skeleton/verify/models.py`: `AttemptRecord.failure_detail: str | None = None`.
  - `skeleton/personas/generator.py`: `render_feedback` omits the detail for `generator_error`.
  - Extend `tests/verify/test_flow.py` (short, over-300, and `None` paths) and `tests/personas/test_generator.py` (feedback omits the message). No `pragma: no cover`, no gate change.
  - Check: `./scripts/check-verify.sh` reports 100%. If it cannot without weakening the gate, stop and report, and ship task 1 alone.
  - _Requirements: R2.1, R2.2, R2.4, R2.5, R3.1, R3.2, R3.3_

- [x] 3. Propagate the field to the UI types and verify containment
  - Run `scripts/gen-ts-types.sh`; add `failure_detail?: string | null;` to `AttemptRecord` in `skeleton/ui-shell/src/types.ts`.
  - Run the full Python suite, the UI suite, the four import-linter contracts, `scripts/gen-ts-types.sh --check` and `./scripts/check-verify.sh`. Confirm `git diff --stat` shows only the files listed in R4.3.
  - _Requirements: R2.3, R2.6, R4.1, R4.2, R4.3, R4.4_

- [ ] 4. Re-run the harness and record SCR-5
  - Do not tune against run 1. Run `uv run python -m medium.eval --runs 2` from scratch and report the new run files. If it aborts, read `failure_detail` in the run file for the cause.
  - `docs/KIRO-USAGE.md`, under "Skeleton change requests": add SCR-5 to the table and a section stating it was found by the harness, not by review, that run 1's numbers were an artefact and were discarded, and that this is the argument for ordering the harness before the UI.
  - _Requirements: R5.1, R5.2_
