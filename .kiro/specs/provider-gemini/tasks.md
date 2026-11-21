# Implementation Plan: provider-gemini

Six tasks. If this list grows, the scope has drifted: cut the spec before running any task. No edit under `skeleton/` in any task. If one seems needed, stop and record a skeleton change request (Medium R9). No retry logic in the Anthropic adapter.

- [ ] 1. Dependency and containment
  - `uv add google-genai` (updates `pyproject.toml` and `uv.lock`). Add `google` and `google.genai` to `forbidden_modules` in the `no-model-sdks` contract of `.importlinter`.
  - Extend the planted-violation test in `tests/independence/test_contracts.py` with a `google.genai` import that must fail the lint.
  - Before task 2 relies on it, check in a REPL that `generate_content` accepts dict `contents` and dict `config` including `system_instruction`, `tools=[{"function_declarations": [...]}]` and `http_options`. Record the answer in a comment at the top of `gemini_client.py`.
  - Check: `uv run lint-imports` passes with all contracts, and the planted test passes.
  - _Requirements: R7.1, R7.2_
- [ ] 2. Schema sanitiser and request mapping
  - `providers/gemini_mapping.py`: `sanitise_schema` and `to_sdk_kwargs` (roles, `system_instruction`, `max_output_tokens`, id resolution by lookup, the dummy signature on the first call of each model content, response ordering by call order, `{"result": ...}`, empty `tools` omitted).
  - `tests/providers/test_gemini_mapping.py`: mirror the request-side cases of `test_mapping.py`. Add sanitiser cases (each dropped key, nested `$ref`, cyclic `$ref` raises, `Optional` collapse, a property named `title` survives, input not mutated, every `INPUT_MODELS` schema clean) and a hypothesis test for GP3. Add the request half of GP1 and GP2.
  - Check: `scripts/run-tests.sh tests/providers` green.
  - _Requirements: R1.1, R1.3, R2.1, R2.2, R2.4 to R2.8, R3.1 to R3.6_
- [ ] 3. Response mapping and round trip
  - `from_sdk_response`: provider id or `name#index`, thought parts skipped, empty candidates, `MAX_TOKENS` raise (accepting enum and string). **Also capture each call's `thought_signature` and return it alongside the response (R2.5a).** `to_sdk_kwargs` takes the signature store and prefers the real signature, sentinel only as fallback (R2.5, R2.5d).
  - Tests: truncation with and without text, other finish reasons pass, and the round trip for two calls to the same tool in one turn with provider ids and without, results reversed. Hypothesis GP1 over the full cycle (response, then request, then ids and order).
  - Check: `scripts/run-tests.sh tests/providers` green.
  - _Requirements: R2.3, R2.9, R2.10, R2.11_
- [ ] 4. Client, retry carve-out and redaction
  - `providers/gemini_client.py` per design sections 3 and 7a, with the R4 carve-out in the module docstring. **Includes the bounded signature store (R2.5a, R2.5b) and the `thinking_budget` option with its unsupported-field guard (R8.1).**
  - `tests/providers/test_gemini_client.py`: port the Anthropic client tests; add the retry matrix from design section 7, the budget test, and the redaction tests of R5.4 (GP4, GP5). Include a `ToolLoopGenerator` run with two same-tool calls.
  - Amend Medium R1.6, R1.10 and R1.14 in `.kiro/specs/medium/requirements.md`, and add the pointer line in `design.md`.
  - Check: `scripts/run-tests.sh tests/providers` green. `git diff` shows no change to `anthropic_client.py` or `mapping.py`.
  - _Requirements: R1.2, R1.4 to R1.7, R4.1 to R4.7, R5.1 to R5.4_
- [ ] 5. Selection and entry points
  - `providers/select.py` per design sections 4 and 7a. Update `medium/main.py` and `medium/eval/__main__.py` to use it. Keep `build_app`'s signature. Remove `medium.main.DEFAULT_MODEL` and `medium.eval.DEFAULT_MODEL` (design section 4). **Add the per-provider `max_tokens` (8192 for Gemini) and pass it into `ToolLoopGenerator` (R8.2, R8.3).**
  - Tests: `tests/providers/test_select.py` (default is gemini, `anthropic`, invalid value names the variable and not the value, `MEDIUM_MODEL` override, per-provider defaults). Update `tests/medium/test_main.py` and `tests/medium/test_eval_runner.py` so each states its provider. No assertion weakened.
  - Check: `grep -rniE "gemini|google" skeleton --include='*.py'` is empty. `scripts/run-tests.sh tests/medium tests/providers` green.
  - _Requirements: R6.1 to R6.5_
- [ ] 6. Live test and full verification
  - One live test for Gemini mirroring `tests/providers/test_live.py`, skipped without `GEMINI_API_KEY`. Update the `live` marker text in `pyproject.toml`.
  - Run: the full Python suite, `uv run lint-imports`, `uv run ruff check`, `./scripts/check-verify.sh` (100%), and `git diff --stat` (no path under `skeleton/`).
  - If `GEMINI_API_KEY` is set, run `uv run pytest -m live tests/providers`. If it is not, say so in the report: the dummy signature and id echo are then unverified against the real API.
  - _Requirements: R7.3 to R7.6_
