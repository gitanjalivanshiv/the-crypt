# Design: medium
Status: **draft for review.** Tasks are not started. Requirement IDs (R1.2, R3.8, …) refer to `requirements.md`.

## Overview
The Medium is a thin layer on a finished skeleton. New code lives in two top-level folders:

```
providers/                 first real LLMClient (Anthropic); imported by both apps, never by skeleton/
  errors.py                ProviderError
  mapping.py               pure translation: LLMRequest -> SDK kwargs, SDK response -> LLMResponse
  anthropic_client.py      AnthropicClient (complete, from_env)
medium/
  personas/ghost.toml      the persona
  plan.py                  three section questions, PlanResult model
  api.py                   router + create_medium_app (wraps skeleton create_app)
  main.py                  process entry: env -> client -> app -> uvicorn
  eval/                    banishment-rate harness: questions.toml, metrics.py, __main__.py, runs/
  ui/                      Vite + React app: theme, state, App, optional PlanPanel
```

Three design rules:
1. **One path for every claim.** Interview answers and plan sections both come from the skeleton's `/ask`. The Medium never builds a prompt, parses model output or constructs a claim.
2. **Measure the path that ships.** The harness drives the same app, route and adapter the demo uses. A measurement taken through a side door would not predict the demo.
3. **When the skeleton is the problem, stop.** Four needs are already known to sit outside the app's reach (R9.3). The spec defines how to report them instead of working around them.

### Decisions that refine or depart from the requirements
| # | Decision | Where | Requirement |
|---|---|---|---|
| M1 | The plan route calls `/ask` through an in-process `httpx.ASGITransport` on the same app, not by importing skeleton internals. | §4 | R6.2, R9.4 |
| M2 | The three plan sections are independent questions. Nothing chains one section's output into the next. | §4 | R6.4 |
| M3 | The harness metrics use only `AnswerResult`. No skeleton change is needed to measure. Tuning, however, needs skeleton levers the app cannot reach. | §5, §7 | R3.6, R3.15, R9 |
| M4 | The tree's `files` come from findings plus citations, because the API has no file list. | §6 | R5.3 |
| M5 | A truncated response (`stop_reason = max_tokens`) raises `ProviderError`. | §2 | R1.8 |
| M6 | Bands are fixed in code before the first live run. | §5.3 | R3.8 |

---

## 1. Architecture
```mermaid
flowchart LR
  UI["medium/ui"] -->|POST /snapshots/{ref}/ask| SK["skeleton.api (create_app)"]
  UI -->|POST /medium/snapshots/{ref}/plan| MA["medium.api router"]
  MA -->|3x ASGI in-process /ask| SK
  SK -->|LLMClient by argument| PR["providers.AnthropicClient"]
  H["medium.eval harness"] -->|POST /ask via TestClient| SK
  PR -->|HTTPS| LLM[("Anthropic API")]
```
`create_medium_app(store, llm)` calls `skeleton.api.app.create_app(store=..., llm=..., persona_dir=medium/personas)` and includes the Medium router on the returned `FastAPI` object. `create_app` returns a normal `FastAPI`, so `include_router` is an ordinary extension, not a skeleton edit.

Import direction, enforced by import-linter: `medium -> providers -> skeleton.personas.llm` and `medium -> skeleton`. `skeleton -> providers` is forbidden by the fourth contract (§2.3).

## 2. Providers
### 2.1 Interface
```python
class AnthropicClient:                       # satisfies skeleton.personas.llm.LLMClient
    def __init__(self, api_key: str, model: str, *, timeout_s: float = 60.0, sdk: Any | None = None) -> None
    @classmethod
    def from_env(cls, model: str, **kw) -> "AnthropicClient"   # reads ANTHROPIC_API_KEY; the only env read
    async def complete(self, request: LLMRequest) -> LLMResponse
class ProviderError(Exception): ...
```
The default `sdk` is `anthropic.AsyncAnthropic(api_key=..., timeout=timeout_s, max_retries=0)`. **`max_retries=0` is load-bearing:** the SDK retries by default (twice), which would add a hidden retry layer under the flow's one regeneration and double the spend on a bad turn (R1.6).

The Gemini adapter has one narrow carve-out for HTTP 429 and 503 (a deferred generation); see `.kiro/specs/provider-gemini/` R4 and the amended R1.6. `AnthropicClient` has no retry logic.

### 2.2 Mapping (`mapping.py`, pure, unit-tested without an SDK)
| Skeleton | Anthropic Messages API |
|---|---|
| `request.system` | `system` |
| `Message(role="user")` | `{"role":"user","content":[{"type":"text",...}]}` |
| `Message(role="assistant", tool_calls=...)` | assistant message: optional text block, then one `tool_use` block per call (`id`, `name`, `input = arguments`) |
| consecutive `Message(role="tool")` | **one** user message of `tool_result` blocks (`tool_use_id = tool_call_id`, `content = message.content`); the API requires results for one assistant turn in a single user message |
| `ToolSpec(name, description, input_schema)` | `{"name","description","input_schema"}` |
| response `text` blocks | joined with `""` into `LLMResponse.text` |
| response `tool_use` blocks | `ToolCall(id, name, arguments=input)` |

Edge cases covered by tests: a tool message with no preceding assistant tool call is passed through (the provider rejects it, which surfaces as `ProviderError`); an empty `tools` tuple omits the `tools` key; a response with no text and no tool use returns an empty `LLMResponse`, which the flow treats as unparseable.

### 2.3 Errors and the import contract
`complete` wraps one `await sdk.messages.create(...)`. Any `anthropic.APIError`, `APITimeoutError` or `stop_reason == "max_tokens"` becomes `ProviderError(f"{type(exc).__name__} status={status}")`. The message is built from the class name and status only, never `str(exc)`, which can echo request content. `asyncio.CancelledError` is not caught.

`.importlinter` change:
- `root_package = skeleton` becomes `root_packages = skeleton`, `providers`, so the new package is part of the graph. The existing layers contract names only `skeleton.*` modules and is unaffected.
- New contract `skeleton-must-not-import-providers`: `forbidden`, source `skeleton`, forbidden `providers`, `allow_indirect_imports = True` (the same shape as the existing contracts).
- `tests/independence/test_contracts.py` gains a planted-violation test: write `skeleton/verify/_planted_providers.py` importing `providers`, assert `lint-imports` fails, delete it in `finally`.

The implementation must confirm that adding `root_packages` does not change the result of the existing three contracts. This is checked by running them unchanged before the edit and after.

## 3. Persona (`ghost.toml`)
Fields per `skeleton/personas/loader.py` (`extra="forbid"`, `strict=True`). Sketch:
```toml
name = "ghost"
display_name = "The Medium"
theme = "seance"
voice = "…dry, weary, techy horror-comedy; speaks of the code and of time passing, never of its maintainers… Quote figures only through the figures list, never in the sentence. A guess begins with 'I suspect'…"
goals = ["Answer only from findings and file lines the tools return.", "…"]
allowed_tools = ["list_findings", "get_file_facts", "read_lines"]   # exact names checked against TOOL_NAMES at task time
example_lines = ["The old bones of this file creak whenever someone touches them.", "…"]   # no digit in any line
decline_line = "The spirits are silent on that."
```
There are no digits anywhere in text fields (R2.3, R2.4), enforced by a test. The persona wording is the **only lever the app controls** over model behaviour: it asks for figures via the `figures` list and for guesses to be marked and phrased as guesses. It cannot alter `GROUNDING`.

## 4. Medium API
```python
# medium/plan.py
SECTIONS = ("requirements", "design", "tasks")
SECTION_QUESTIONS: dict[str, str]          # no digits; independent
class PlanSection(BaseModel):  section: Literal["requirements","design","tasks"]; result: AnswerResult
class PlanResult(BaseModel):   snapshot_id: str; sections: tuple[PlanSection, ...]
```
`AnswerResult` is imported from `skeleton.verify.models`, the one allowed `skeleton.verify` import (R8.4).

`POST /medium/snapshots/{ref}/plan`:
1. For each section in order, `POST /snapshots/{ref}/ask` with `{"persona": "ghost", "question": SECTION_QUESTIONS[section]}` through `httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://medium")`.
2. A 200 response is parsed with `AnswerResult.model_validate` and wrapped. A non-200 response is returned as is, status and body unchanged (R6.6), and the loop stops.
3. Sections run **sequentially**, not concurrently: the harness and the demo share one provider rate limit, and sequential order keeps cost and failure behaviour predictable. Worst case is three turns, each at most two attempts of up to five model rounds.

Why in-process HTTP and not a direct call: the only direct route is through `ToolLoopGenerator`, `ToolRouter` and `assemble_system_prompt`, which are the pieces R8.4 says the app must not reuse. The ASGI hop costs microseconds and keeps the app on the public contract. If a judge reads the plan route, it is 25 lines and contains no verification code.

`medium/main.py` builds `AnthropicClient.from_env(model)` (model from `MEDIUM_MODEL`, default pinned in the file), a store path from `CRYPT_STORE`, and runs uvicorn. A missing key fails at startup with a message naming the variable and never printing a value.

## 5. Banishment-rate harness
### 5.1 Flow
`python -m medium.eval --runs 2 [--max-turns N] [--questions PATH]`:
1. Build `create_medium_app(store=tmp, llm=AnthropicClient.from_env(...))` with `ApiConfig(allow_retained=True)` inside a `TestClient`.
2. `POST /snapshots` with the patient's `clone_url`, `sha` and `intent = "retained"` (about 20 s on the demo host, per `demo/patient.json`). The ref is reused for every question and every run in the process.
3. For each question, `POST /snapshots/{ref}/ask` for `ghost`. Plan-section questions resolve from `medium.plan.SECTION_QUESTIONS` by id.
4. Collect `AnswerResult`s, compute the report, write `medium/eval/runs/<UTC timestamp>-<n>.json` (raw results plus report) and print a table.
5. Exit non-zero if a band is breached or the run aborted.

The harness uses `TestClient`, which runs the app in-process with real network egress from the adapter. That is the same code as production minus uvicorn.

### 5.2 Metrics (`metrics.py`, pure)
Input: `list[tuple[Question, AnswerResult]]`. Definitions, which implement R3.6 and R3.7:
```
judged(r)      = len(r.claims) + len(r.banishments)
verified       = sum(1 for c in r.claims if c.kind == "fact")
guess          = sum(1 for c in r.claims if c.kind == "guess")
banished[code] = sum(1 for b in r.banishments if b.reason == code)
declined       = r.status == "declined"
```
A decline has `claims = ()` by construction, so the claims of an answered-after-regeneration turn are the second attempt's and its `banishments` are the first attempt's. Each judged claim therefore appears exactly once. Shares are over `sum(judged)`; zero denominators yield `None`, rendered as `n/a`.

`first_attempt_accepted` is read from `attempts[0].outcome == "accepted"`. `all_guess_turn` is `status == "answered"` and `claims` non-empty and every `kind == "guess"`. An answered turn with zero claims is reported separately as `empty_answers` and counted in neither failure mode; if it is non-zero, it is a finding.

Reported per category as well as overall, because the failure modes differ by question type: number-seeking questions should banish, unanswerable ones should decline or guess.

### 5.3 Bands
Fixed in `metrics.py` as constants, with the reasoning for each beside it (R3.8):

| Metric | Band | Failure it guards |
|---|---|---|
| Guess share | ≤ 0.35 | Too lenient: the guess flag is a loophole |
| All-guess turns | ≤ 0.15 | Too lenient: this is the turn `classify_attempt` would route to decline |
| Turns with ≥ 1 banishment | 0.10 to 0.50 | Lower: no signature moment on camera. Upper: unreliable ghost |
| Declined share | ≤ 0.15 | Too strict: the demo looks broken |
| Verified share | ≥ 0.50 | Both: a ghost that mostly guesses or is mostly rejected has little to say |

With 20 turns a 0.10 band is two turns, so the bands are coarse. That is why R3.11 requires two runs, and why the report prints counts next to shares.

### 5.4 What a breached band means
| Symptom | Likely cause | First lever | Reachable by the app? |
|---|---|---|---|
| Many `unbacked_number` banishments, high decline | Model writes numbers the scan rejects (years, version numbers, counts) | `cfg.allowed_numbers`, then persona wording | No for the config; yes for wording |
| High guess share, all-guess turns | Model hides behind `guess` | `GROUNDING` wording, then `classify_attempt` | No; persona wording only |
| Many `quote_mismatch`, `range_out_of_bounds` | Model quotes from memory instead of `read_lines` | Persona wording ("read the lines before quoting") | Yes |
| Many `uncited_claim` | Model states facts without citing | Persona wording | Yes |
| Zero banishments, low guess share | Questions too easy or model too careful | Question set, not the system | Yes, but a new question-set version |

So the loop is: persona wording first (R3.15a). If that cannot bring the run into band after two iterations, the evidence is in `medium/eval/runs/` and the next step is a skeleton change request (R9.2), not a code change. The report's per-reason counts and the `unbacked_number` messages in the raw files are the evidence for `allowed_numbers` candidates.

### 5.5 Cost
Per run: 20 turns × up to 2 attempts × up to 5 model rounds, with `max_tokens` the adapter's per-call limit. The expected case is roughly 3 calls per turn. Two runs plus up to four tuning re-runs is about 6 runs. The actual spend is read from the provider dashboard and recorded beside the numbers. No cap is set by the harness beyond `--max-turns` and the 3-consecutive-error abort. A hard monthly cap is set at the provider (`tech.md`).

## 6. UI
`medium/ui` is a Vite + React 18 + TypeScript package depending on `@kiroween/ui-shell` by relative link (`link:../../skeleton/ui-shell`), and proxying `/snapshots` and `/medium` to the API in dev.

```
src/
  theme/seance.ts      Theme data: colours, font, effects, sounds
  api.ts               fetch wrappers: createSnapshot (not needed in demo), getSnapshot, getFindings, ask, plan
  types.ts             PlanResult, ApiError; AnswerResult is re-exported from the shell
  state.ts             reducer: { ref, licence, turns, filesFromFindings, pending, error }
  App.tsx              ThemeProvider > SoundProvider > CrtFrame > FileTree + ChatPanel(s) + input
  useSweep.ts          (cuttable) steps `active` through cited files
  PlanPanel.tsx        (cuttable) three ChatPanels, one per section
```
**State derivation (pure, in `state.ts`, tested without React):**
- `cited(result) = unique(result.claims.flatMap(c => c.citations.map(x => x.file)))`, in order of first appearance. Banished claims are excluded (R5.1).
- `files = sorted(unique(findingFiles ∪ cited))` (R5.3).
- `active`: the first cited file, or the user's last selection.
- Each submitted turn is stored with its question and its `AnswerResult` object, unmodified, and handed to `ChatPanel` as `result` (R4.2). A test asserts referential equality of what the reducer stores and what `ChatPanel` receives.

**Theme.** `seance` is data only. A test runs `REQUIRED_PAIRS` against `MIN_CONTRAST_RATIO` and a grep test fails if any file under `skeleton/ui-shell/src/` or `medium/ui/src/` contains `theme.id` or a comparison with a theme name (R7.3).

**Accessibility.** The question field has a visible label and an `aria-live` region announces the pending and error states. Axe runs on the rendered App with `vitest-axe`, as the shell's tests do.

**Known limitation (R5.3).** The tree shows files with findings plus cited files. The patient has 564 files and 495 findings (`demo/patient.json`), so the share of files shown is unmeasured. The limitation is recorded as skeleton change request SCR-1 (§7).

## 7. Skeleton change requests (known at design time)
Recorded in `docs/KIRO-USAGE.md` under "Skeleton change requests" when the first task starts, so they exist before they are needed. None is acted on in this spec.

| ID | Need | Today | Smallest change | Blocks |
|---|---|---|---|---|
| SCR-1 | File listing for the tree | No route exposes the code graph's files | `GET /snapshots/{ref}/files` listing paths | Nothing (workaround R5.3) |
| SCR-2 | `allowed_numbers` per app | `VerifyConfig()` built inline in `ask` | `ApiConfig.verify: VerifyConfig`, passed to `ask` | Only if the harness shows `unbacked_number` over-rejection |
| SCR-3 | Grounding wording | `GROUNDING` is a constant | Optional persona-level addendum field, or a documented edit to the constant | Only if persona wording cannot fix the guess share |
| SCR-4 | Acceptance rule | `classify_attempt` not injectable | Accept `classify` as an argument to `run_grounded_turn` with the current function as default | Only if all-guess turns breach their band |

Each of SCR-2 to SCR-4 is opened only if the measured breach points at it. SCR-1 is a nice-to-have.

## 8. Correctness properties
| ID | Property | Test |
|---|---|---|
| MP1 | `AnthropicClient` makes at most one SDK call per `complete`, with `max_retries = 0` | fake SDK counting calls; assertion on constructor kwargs |
| MP2 | Every `ToolCall` the adapter returns carries the provider's call id, and every tool result it sends carries the matching id | mapping round-trip, Hypothesis over tool-call lists |
| MP3 | No `ProviderError` text contains the key, the system prompt or the response text | fake SDK raising errors that embed all three |
| MP4 | Every plan section's `AnswerResult` equals the skeleton `/ask` result for the same question | `FakeLLMClient` scripted; compare plan section with a direct `/ask` |
| MP5 | The plan route introduces no claim that `/ask` did not return | a script whose first answer contains a fabricated citation: the plan shows it banished or the turn declined, never as a verified claim |
| MP6 | Metrics partition: for any list of `AnswerResult`s, verified + guess + banished equals judged, and shares of the reason codes sum to the banished share | Hypothesis over generated results |
| MP7 | Metrics are `n/a`, not 0, with zero judged claims | unit |
| MP8 | `cited` derivation never includes a banished citation | Hypothesis over generated results |
| MP9 | The skeleton manifest is unchanged by a full turn and a full plan | hash before and after |

## 9. Testing strategy
- **Default run (no network, no key):** providers (fake SDK), persona, plan route, harness metrics and runner with `FakeLLMClient`, independence, UI unit and a11y tests.
- **`live` marker:** one provider call test (R1.14) and the harness itself. Excluded from CI.
- Existing hooks run `scripts/run-tests.sh` on save per subsystem; tests live under `tests/providers/`, `tests/medium/` and `tests/independence/` so they fire. UI tests live in `medium/ui/test/`.
- The Medium adds no verifier tests. The verifier's coverage gate is the skeleton's.

## 10. Requirement traceability
| Req | Design |
|---|---|
| R1 | §2 |
| R2 | §3 |
| R3 | §5, §7 |
| R4 | §6 |
| R5 | §6 |
| R6 | §4, §6 |
| R7 | §6 |
| R8 | §2.3, §8 MP9 |
| R9 | §7 |
| R10 | `tasks.md` |

## 11. Cut order and what it costs
1. **Theme sound cues.** The Medium is silent. Nothing breaks.
2. **Possession sweep.** The tree still highlights all cited files at once and `active` is the first. The "speaking" effect is lost, the possession itself is not.
3. **Plan panel.** The plan route and its measured banishment rate stay, but a judge cannot see the plan in the UI. This is the last cut because it removes the interview's ending.

## 12. Watch items
1. **The two runs may disagree.** A model is sampled; 20 turns is small. Record both, do not average, and tune on the worse.
2. **The guess flag is an incentive.** If the persona wording says "say I suspect when unsure", the model may over-use it. The wording must tie guesses to "no tool result supports this", not to uncertainty in general.
3. **Plan questions are the likeliest to be all-guess**, since "what should be rewritten" is a recommendation. They are in the 20 so this shows up early.
4. **The 20-second ingest** is inside every harness process, not every question. Keep the process alive across runs.
5. **Maintainers.** The persona and the plan questions must not describe the patient's maintainers as negligent (`demo-patient.md`). Checked by reading the persona wording and a sample of run output, not by a test.
