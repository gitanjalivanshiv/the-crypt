# Design: debt-collector
Status: **draft for review.** Tasks are not started. Requirement IDs (R1.2, R4.6, …) refer to `requirements.md`.
## Overview
The Debt Collector is a thin layer on a finished skeleton, shaped like `medium/` with different content. New code lives in one top-level folder:
```
debt-collector/            no __init__.py (namespace package, like medium/ and providers/)
  interest.py              pure: pricing, ranking, totals, escalation, plan, FIGURES, METRIC_UNITS, models
  notice.py                the notice question template (no digit), one function of the level word
  api.py                   router + create_collector_app (wraps skeleton create_app)
  main.py                  process entry: env -> client (or offline) -> app -> uvicorn
  personas/collector.toml  the persona
  ui/                      Vite + React app: theme, api, state, App, optional PlanPanel, useDrain, boss.css
```
Tests live in `tests/debt_collector/`, `tests/independence/` and `debt-collector/ui/test/`.
Four design rules:
1. **Numbers are code.** Every number on screen is a `Finding.metrics` value or a value `interest.py` computes and names in `FIGURES`. The model is never asked to add, rank or round (`grounding-rule.md` rule 4).
2. **Two routes need no model.** The ledger and the plan are arithmetic over verified findings. They are the demo's insurance against a provider outage.
3. **One path for every claim.** The notice comes from the skeleton's `/ask`. The collector never builds a prompt, parses model output or constructs a claim.
4. **When the skeleton is the problem, stop.** Two needs are already known (R8.3). The spec defines how to report them instead of working around them.
### Decisions that refine or depart from the requirements
| # | Decision | Where | Requirement |
|---|---|---|---|
| D1 | The folder name has a hyphen, so no `import` statement can name it. The package has no `__init__.py`, modules import each other with relative imports, and tests load modules with `importlib.import_module("debt-collector.interest")`. import-linter, `python -m debt-collector.main` and uvicorn's import string were all checked to accept the hyphenated name. | §1 | R7.6 |
| D2 | The formula reads severity and line span, not metric keys. Severity is already the analyzer's function of its metrics. | §2 | R1.2, R1.3 |
| D3 | Ledger and plan call the skeleton through an in-process `httpx.ASGITransport`, as the Medium's plan route does. | §4 | R3.2 |
| D4 | The notice returns the skeleton's response bytes unchanged, with no re-validation and no re-serialisation. | §5 | R4.1 |
| D5 | The escalation level is part of the ledger payload, so the UI can show what the notice will say without a model call. | §2, §4 | R1.9, R3.1 |
| D6 | With no provider the app starts and the notice declines. It does not fail at startup, unlike the Medium. | §6 | R4.6, R4.8 |
| D7 | Computed figures are shown by the UI from the ledger payload. They are never quoted by the model. | §5.3 | R4.7, R8.3 |
| D8 | The plan and the ledger share one pricing function and one findings reader. They cannot disagree. | §2, §4 | R5.1 |
| D9 | The cuttable UI tasks are built in the reverse of the cut order. | `tasks.md` | R9.3 |
| D10 | The task limit of twelve forced the three backend routes and the process entry into one task. | `tasks.md` | R9.1 |
---
## 1. Architecture and the hyphenated folder
```mermaid
flowchart LR
  UI["debt-collector/ui"] -->|GET ledger / plan| CA["debt-collector api router"]
  UI -->|POST notice| CA
  UI -->|GET /snapshots/{ref}| SK
  CA -->|in-process ASGI GET findings| SK["skeleton.api (create_app)"]
  CA -->|in-process ASGI POST /ask| SK
  SK -->|LLMClient by argument| PR["providers.select client or OfflineClient"]
  PR -->|HTTPS| LLM[("model provider")]
```
`create_collector_app(store, llm, cfg=None)` calls `skeleton.api.app.create_app(store=..., llm=..., persona_dir=debt-collector/personas, cfg=...)` and includes the router on the returned `FastAPI`. That is an ordinary extension, not a skeleton edit.
**Naming.** `debt-collector` is required by the submission and is not a valid Python identifier. The consequences, all checked on a scratch tree before this spec was written:
- Inside the folder, modules use relative imports (`from .interest import price`). They work because the folder is a namespace package, which is also how `medium/` and `providers/` work.
- Tests import with `importlib.import_module("debt-collector.interest")`. `pyproject.toml` already has `pythonpath = ["."]`.
- `python -m debt-collector.main` and uvicorn's `"debt-collector.main:build_app"` with `--factory` both resolve.
- import-linter accepts `debt-collector` as a root package and reports `debt-collector.a -> medium` as a violation. A static `import debt-collector` is a syntax error, so nothing under `skeleton/` or `medium/` can import this app by accident. The existing contract that forbids `debt_collector` stays as it is. The remaining route in is a dynamic import, which R7.2's string scan catches.
Allowed `skeleton` imports from `debt-collector/`: `skeleton.api.app` (`create_app`, `ApiConfig`), `skeleton.personas.llm` (`LLMClient`), `skeleton.verify.models` (`AnswerResult`), `skeleton.signals.models` (`Finding`), `skeleton.mcp.contract` (`ListFindingsOutput`, `MAX_LIMIT`). Everything else is forbidden by the contract in §8.
## 2. Interest (`interest.py`)
### 2.1 Formula and units
For a finding `f` with severity `s` in [0, 1] and range `[a, b]`:
```
principal           = b - a + 1                       lines
rate                = s ** 2                          per year, dimensionless, 0..1
interest            = principal * rate                lines per year
effort              = 1 + log2(1 + principal)         effort points, >= 1
interest_per_effort = interest / effort               lines per year per effort point
```
All outputs are `round(x, 6)`. Rounding is monotone, so the monotonicity property survives it.
**Why this shape.**
- Principal is a size the user can check: the range is the cited range. It is a number in the finding, not a guess about hours.
- `severity ** 2` is convex. A finding at 0.9 costs four times one at 0.45, so the few worst debts stand out and "boss fights" are real. A linear rate would flatten the ledger. The exponent is one constant with one test.
- Effort is logarithmic in size. A 40-line range is more work than a 4-line one, but not ten times more. Because effort differs from principal, `interest_per_effort` is not just `severity ** 2`, so the plan's order differs from the ledger's. Short, severe debts come first.
- **Metrics are not read by name (D2).** Each analyzer already turns `commit_count`, `days_since_modified` or `age_days` into a severity with its own saturation (`SignalsConfig`). Using them again would double count and would need a per-analyzer table, so adding an analyzer would mean editing this module. Metrics are carried through and given units instead.
These are starting values. They are constants at the top of the file, each with the reasoning beside it. Changing one is a one-line edit and a test update.
**Interpretation to confirm.** The brief says "derived only from `Finding.metrics` and the snapshot". This design reads that as "from the finding and the snapshot, never from a model": severity (the analyzer's output), the range, and the metrics echoed alongside.
### 2.2 Metric units (`METRIC_UNITS`)
| Key | Emitted by | Unit |
|---|---|---|
| `commit_count` | churn, staleness | commits (all time, up to the snapshot's pinned commit) |
| `author_count` | churn | distinct authors |
| `days_since_modified` | staleness | days |
| `age_days` | todo_age | days |
| `todo_count_in_file` | todo_age | markers in the file |
An unknown key maps to `unspecified`. A test reads the shipped analyzers' `metrics=` dict literals with `ast` and fails if a key is missing from the table, so a new analyzer forces a one-line edit here and not a silent gap.
### 2.3 Figures registry (`FIGURES`)
```python
FIGURES: dict[str, FigureDoc]   # FigureDoc(unit: str, meaning: str)
# principal, interest, effort, interest_per_effort           per line
# total_principal, total_interest, total_severity            per ledger
```
The completeness test (R1.7) serialises the ledger and the plan, walks every number, and allows: a key in `FIGURES`, a key under a line's `metrics` object, `severity` (the analyzer's own number, echoed), `rank`, `line_start`, `line_end`, and the coverage counts (`returned`, `matching`). Anything else fails.
### 2.4 Models and functions
```python
class LedgerLine(BaseModel):  rank:int; finding_id:str; analyzer:str; file:str; line_start:int; line_end:int
                              severity:float; principal:float; interest:float; boss:bool; metrics:dict[str,int|float]
class Coverage(BaseModel):    analyzer:str; returned:int; matching:int
class Totals(BaseModel):      principal:float; interest:float; severity:float
class Ledger(BaseModel):      snapshot_id:str; lines:tuple[LedgerLine,...]; totals:Totals
                              escalation:Literal["courtesy","reminder","demand","final"]
                              coverage:tuple[Coverage,...]; truncated:bool
class PlanSource(BaseModel):  file:str; line_start:int; line_end:int
class PlanEntry(BaseModel):   rank:int; finding_id:str; source:PlanSource; effort:float; interest:float
                              interest_per_effort:float; boss:bool
class PlanResult(BaseModel):  snapshot_id:str; entries:tuple[PlanEntry,...]
def price(finding, finding_id) -> Priced            # pure, one finding
def build_ledger(snapshot_id, items, coverage) -> Ledger     # items: (Finding, id) pairs; ranks, totals, boss, escalation
def build_plan(ledger_inputs) -> PlanResult          # same pricing, plan ordering
def escalation_level(total_severity: float) -> str
LEVELS: tuple[str, ...] = ("courtesy", "reminder", "demand", "final")
```
`build_ledger` and `build_plan` take the same `(Finding, finding_id)` pairs and call `price` once per finding, so the plan and the ledger share every number (D8). All models are frozen.
`BOSS_COUNT = 3`. A line is a boss when its rank by interest is at most `BOSS_COUNT` and its interest is above zero.
### 2.5 Escalation
`total_severity` is the sum of the severities of the ledger lines. The level is the last entry whose cut-off the total reaches:
```
ESCALATION_CUTOFFS = (("courtesy", 0.0), ("reminder", 3.0), ("demand", 15.0), ("final", 40.0))
```
The cut-offs are starting values and are tuned once, by hand, against the patient's real ledger after task 3, since the ledger needs no model. The sum is over the lines returned, at most 100 per analyzer (R3.4), so it depends on the coverage cap. That dependence is stated in the payload (`truncated`), not hidden.
The level is part of the ledger (D5). The notice route computes it from the same function and the same findings, so the UI can show "this notice will be a `demand`" before the model speaks.
## 3. Persona (`collector.toml`)
Fields per `skeleton/personas/loader.py` (`extra="forbid"`, `strict=True`). Sketch:
```toml
name = "collector"
display_name = "The Debt Collector"
theme = "ledger"
voice = "…a polite, patient, faintly menacing accounts clerk… speaks of the code and of time passing, never of its maintainers… describes the register of each notice word: courtesy, reminder, demand, final… Put figures only in the figures list… never state a principal, an interest or a total; those are in the ledger… A guess begins with 'I suspect' and is for when no tool result supports a statement…"
goals = ["Itemise debts only from findings the tools return, and cite them.", "…"]
allowed_tools = ["get_snapshot", "list_findings", "get_file_facts", "read_lines"]   # checked against TOOL_NAMES
example_lines = ["This file has been accruing quietly since before anyone here was keeping accounts.", "…"]   # no digit
decline_line = "The books are closed to that inquiry."
```
No digit appears in any text field (R2.3), enforced by a test over `voice`, `goals`, `example_lines` and `decline_line`, together with `warnings == []`. The persona wording is the only lever the app controls over model behaviour. It cannot alter `GROUNDING`.
A second test loads `LEVELS` from `interest.py` and fails if the voice omits one, so the persona and the escalation constants cannot drift apart (R2.6).
The humour targets the code and time (`demo-patient.md`). A debt is the file's, never a person's.
## 4. Routes (`api.py`)
```
GET  /collector/snapshots/{ref}/ledger   -> Ledger        no model
GET  /collector/snapshots/{ref}/plan     -> PlanResult    no model
POST /collector/snapshots/{ref}/notice   -> AnswerResult  one /ask call
```
All three use one helper that opens `httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://collector")` (D3). The same app serves both the skeleton routes and these, so the call is in process and goes through the public contract.
### 4.1 Reading findings (`_read_findings`)
1. `GET /snapshots/{ref}`. A non-200 is returned unchanged. The snapshot ID and the analyzer statuses come from here.
2. `GET /snapshots/{ref}/findings?limit=100`. A non-200 is returned unchanged. Parse with `ListFindingsOutput.model_validate`.
3. If `total_matching <= len(findings)`, the first call is complete. Coverage is one entry per analyzer seen.
4. Otherwise ask once per analyzer name (the union of analyzers seen in the findings and analyzers with state `ok`), `?analyzer=<name>&limit=100`, merge by `id`, and record `returned` and `matching` for each. `truncated` is true when any `returned < matching`.
Why not the analyzer list alone: the skeleton test fixture lists a finding for an analyzer whose status says `skipped`. Using the union costs nothing and does not depend on the status list being tidy.
Worst case is `1 + 1 + analyzers` calls, all in process, with no model. For the patient (3 analyzers), at most 300 of its 495 findings are reachable. That is SCR-7 and is shown in `coverage`, not hidden.
The route calls no other skeleton function, never opens the store and never imports the tool router (R3.2).
### 4.2 Ledger and plan
`ledger` calls `_read_findings`, then `build_ledger`. `plan` calls `_read_findings`, then `build_plan`. A structured error from the skeleton is returned with its status and body (R3.6), and the handler returns nothing partial. Neither route touches `app.state.llm`. A test passes a client that raises on any call and asserts zero calls.
A plan entry's `source` is the finding's own range (R5.2). The plan test resolves every entry through `GET /snapshots/{ref}/files/{path}?line_start=&line_end=` with status 200 (R5.4). The skeleton's finding gate already guarantees the range exists and that the evidence matches the file bytes.
## 5. Notice
### 5.1 Flow
1. `_read_findings`, `build_ledger`, take `ledger.escalation`. (This is the only reason the notice route reads findings. It sends none of them to the model.)
2. `question = notice_question(level)`.
3. `POST /snapshots/{ref}/ask` with `{"persona": "collector", "question": question}`.
4. Return `Response(content=resp.content, status_code=resp.status_code, media_type=...)` (D4). A 200 is the skeleton's `AnswerResult` JSON untouched. A structured error is returned as it came.
The route is about 25 lines and contains no verification code. A grep test fails on `AnswerResult(`, `VerifiedClaim(`, `Citation(`, `LLMRequest` and `assemble_system_prompt` in `api.py`.
### 5.2 The question (`notice.py`)
```python
NOTICE_TEMPLATE = (
    "Issue a {level} notice on the accounts of this codebase. Itemise the largest debts, "
    "one claim for each, and cite the code that shows each one. Match the register of a "
    "{level} notice. Use only figures that the findings supply."
)
def notice_question(level: str) -> str: ...      # raises ValueError for a word not in LEVELS
```
No digit (R4.3), tested for each level. The only variable is the level word, so the question does not grow with the ledger and carries no number the model could copy.
### 5.3 What the collector cannot say, and why that is acceptable
The verifier checks a `figure` against `Finding.metrics[key]` for a finding whose file the same claim cites. Principal, interest and totals are not in `Finding.metrics`. `VerifyConfig.allowed_numbers` is set when the app is built, so it cannot hold a number that depends on the snapshot. A claim that repeats an interest is therefore banished as `unbacked_number`. That is the grounding rule working: the model may not say a number that no verified source backs.
The product consequence is a split of labour (D7):
- The **ledger** shows principal, interest and totals, with units, from the payload.
- The **collector's prose** speaks about files, lines and metrics figures ("untouched for N days", through a verified figure), and points at the ledger for the money.
- A test (R4.7) scripts a claim that repeats a computed interest and asserts it is banished, so the limit is documented by a test and not discovered on camera.
This is SCR-6. It is not opened, because the demo is legible without it. If the user decides the collector must say its own interest, the smallest skeleton change is on record (R8.3).
## 6. Process entry (`main.py`)
```python
def build_app(env=None, client_factory=None) -> FastAPI
```
1. Translate `COLLECTOR_PROVIDER` and `COLLECTOR_MODEL` into the variable names `providers.select` reads, in a copy of the environment. `providers/` is not edited.
2. Try `with_max_tokens(client_factory(model), max_tokens_from_env(env))`. On `ProviderError` (a missing key), log one line naming the variable and use `OfflineClient`.
3. `OfflineClient.complete` raises `ProviderError("no provider configured")`. The flow treats any generator exception as a failed attempt and declines with the persona's `decline_line` (skeleton R4.15), so `POST …/notice` returns a declined `AnswerResult` and does not crash (R4.6).
4. `create_collector_app(store=Path(CRYPT_STORE or "crypt-store"), llm=...)`.
`main()` runs uvicorn. The default port differs from the Medium's by an environment default only, so both apps can run side by side.
A test builds the app with an empty environment and asserts: the ledger and plan return 200, and the notice returns `status == "declined"` with the collector's decline line.
## 7. UI
`debt-collector/ui` is a Vite + React 18 + TypeScript package. It depends on `@kiroween/ui-shell` by relative link (`link:../../skeleton/ui-shell`) and proxies `/snapshots` and `/collector` to the API in dev.
```
index.html                  mounts App (inline module script)
src/
  theme/ledger.ts           Theme data
  api.ts                    fetch wrappers: getSnapshot, getLedger, postNotice, getPlan; ApiError
  state.ts                  pure: outstanding(), meterValue(), settle(), format helpers
  App.tsx                   ThemeProvider > SoundProvider > CrtFrame > Meter + ledger list + notice + ChatPanel
  PlanPanel.tsx             (cuttable 4) plan table
  useDrain.ts               (cuttable 2) stepped count-down
  boss.css                  (cuttable 1) boss treatment
test/
```
**Composition only (R6.4).** `App.tsx` imports `CrtFrame`, `ChatPanel`, `Meter`, `ThemeProvider`, `SoundProvider` and `useSound` from `@kiroween/ui-shell` and passes props. The ledger list is the app's own markup inside `App.tsx` (the shell has no list component). A test greps `src/` for a declaration named `CrtFrame`, `ChatPanel` or `Meter`.
**Theme.** `ledger` is data only. It starts from the shell's reference palette of the same name (ink on paper) and sets its own `effects` so `CrtFrame` has a visible bezel and faint scanlines, and `sounds: {}` until the cuttable sound task. A test runs `REQUIRED_PAIRS` against `MIN_CONTRAST_RATIO` on the final object (R6.2). A grep test fails if any file under `skeleton/ui-shell/src/` or `debt-collector/ui/src/` contains `theme.id` or a comparison with a theme name (R6.3).
**State (pure, tested without React).**
```
outstanding(ledger, settled) = sum(line.interest for line in ledger.lines if line.finding_id not in settled)
meterValue(ledger, settled)  = ledger.totals.interest > 0 ? outstanding / ledger.totals.interest : 0
```
These are arithmetic over numbers the ledger returned, done in the UI, with no model. `settled` is a `Set` of finding IDs held in component state. Nothing is sent or stored (R6.6). The label says "marked settled", not "refactored", because nothing in this app touches the code.
**Flow.** On load the UI calls `GET /snapshots/{ref}` (licence) and the ledger route, and renders the list and the meter. "Serve notice" calls the notice route and hands the `AnswerResult` object to `ChatPanel` as received. A failed notice shows the structured error in an `aria-live` region and leaves the ledger on screen (R6.8). If the provider is offline the notice comes back as a declined `AnswerResult`, which `ChatPanel` already renders as the decline line.
**Accessibility.** Labelled controls, keyboard operation, an `aria-live` region for pending and error states. Axe runs on the rendered `App` with `vitest-axe`, as the shell's tests do. Reduced motion goes through the shell's `useReducedMotion`.
**Cuttable pieces.**
1. *Boss fights:* `boss.css` selects `[data-boss="true"]`. The row carries `data-boss` from the base screen, so the hook exists whether or not the styling does. The treatment is a heavy rule and a "largest debt" label drawn from theme variables, with any pulse disabled under reduced motion.
2. *Meter animation:* `useDrain` tweens the displayed outstanding-interest readout down to its new value in steps. The bar's own motion is the shell's `Meter` transition, which stays. Cut: the readout jumps.
3. *Sound cues:* the theme gains `settle`, `notice` and `banish` specs and `App` calls `useSound().play(...)`. The shell emits no sound itself, so the app names the events. Cut: the collector is silent.
4. *Plan screen:* `PlanPanel` renders the plan route's entries with rank, `file:lines`, effort, interest and interest per effort. Cut: the route stays, and its tests stay.
## 8. Independence (import-linter and tests)
`.importlinter` changes, all additive:
- `root_packages` gains `debt-collector` and `medium`, so both are in the graph. `medium` is needed so a collector import of it is seen as an internal edge.
- `debt-collector must not import medium`: `forbidden`, source `debt-collector`, forbidden `medium`.
- `debt-collector must not import a model SDK`: source `debt-collector`, forbidden `anthropic`, `openai`, `boto3`, `google`, with `allow_indirect_imports = True`, so `providers.select`'s lazy SDK import does not count.
- `debt-collector uses only the skeleton's public surface`: source `debt-collector`, forbidden `skeleton.verify.citation`, `.claim`, `.parse`, `.textnorm`, `.flow`, `.codes`, `skeleton.personas.generator`, `.prompt`, `.grounding`, `skeleton.mcp.router`, `.tools`, `skeleton.signals.store`, `skeleton.ingest`, `skeleton.api.retention`.
The existing four contracts are run before and after the edit and must give the same result (R7.7). Each new contract has a planted-violation test in `tests/independence/test_contracts.py`: write `debt-collector/_planted_<name>.py`, assert `lint-imports` fails, delete the file in `finally`.
`tests/independence/test_debt_collector.py` adds:
- The SHA-256 manifest of `skeleton/` is equal before and after one ledger, one notice and one plan through `create_collector_app` with `FakeLLMClient` (R7.1).
- `skeleton/` contains none of `debt-collector`, `debt_collector`, the persona's name in quotes, its display name, its example lines or its decline line, with the existing guard files and `skeleton/ingest/history.py` allow-listed after checking what the word means there (R7.2).
- `debt-collector/` exists at the repository root, has no `__init__.py`, and `ui/` is inside it (R7.6).
## 9. Correctness properties
| ID | Property | Test |
|---|---|---|
| CP1 | Interest is finite and not negative for any valid `Finding` | Hypothesis over findings |
| CP2 | Interest is monotone in severity, other inputs equal | Hypothesis over severity pairs |
| CP3 | Pricing twice gives identical output, and shuffling the input does not change the ranked output | Hypothesis over lists |
| CP4 | The escalation level never falls as total severity rises, and each cut-off lands on its own level | Hypothesis plus table |
| CP5 | Every number in the ledger and plan payloads is a metric, a registered figure, a position or a coverage count | payload walk |
| CP6 | The plan is ordered by `interest_per_effort` and holds the same findings as the ledger | Hypothesis over lists |
| CP7 | Every plan entry's `source` resolves through the skeleton's file route | route test |
| CP8 | Ledger and plan make zero model calls, and work with an offline client | exploding client; empty environment |
| CP9 | The notice response equals the skeleton's own `/ask` response for the same script | two apps, one script |
| CP10 | A claim that repeats a computed interest is banished as `unbacked_number` | scripted `FakeLLMClient` |
| CP11 | The notice question has no digit and names the level the ledger reports | per level, plus route test on the recorded request |
| CP12 | The skeleton manifest is unchanged by a full ledger, notice and plan | hash before and after |
| CP13 | The settled meter value is in [0, 1], falls as debts are settled, and is 0 when the total is 0 | property test in `state.test.ts` |
## 10. Testing strategy
- **Everything runs by default with no network and no key.** Interest, persona, routes (ledger, plan, notice with `FakeLLMClient`), the offline entry, independence, and the UI unit and a11y tests.
- No task has a `live` test. The collector adds no verifier tests. The verifier's coverage gate is the skeleton's.
- Route tests build a snapshot store the way `tests/api/test_read_routes.py` does, and add a larger `findings.json` with several analyzers and more than 100 findings for one of them, to exercise coverage and truncation.
- `scripts/run-tests.sh tests/debt_collector` and `tests/independence` are the per-task checks. UI tests run with `pnpm test` in `debt-collector/ui`.
## 11. Requirement traceability
| Req | Design |
|---|---|
| R1 | §2, §9 CP1 to CP6 |
| R2 | §3 |
| R3 | §4.1, §4.2 |
| R4 | §5, §6 |
| R5 | §2.4, §4.2 |
| R6 | §7, §9 CP13 |
| R7 | §1, §8, §9 CP12 |
| R8 | §5.3, `requirements.md` R8.3 |
| R9 | `tasks.md` |
## 12. Cut order and what it costs
1. **Boss fights.** The largest debts are listed like the others. The `boss` flag stays in the payload and the row keeps its `data-boss` hook.
2. **Meter animation.** The readout jumps to its new value. The bar still falls, by the shell's transition.
3. **Sound cues.** The collector is silent.
4. **Plan screen.** The route and its tests stay. A judge cannot see the plan in the UI. This is the last cut because it removes the "ranked repayment plan" from the demo.
## 13. Watch items
1. **The collector cannot say its own interest** (SCR-6). If the demo reads flat without it, the choice is a skeleton change request, not a workaround.
2. **Truncation distorts totals.** On the patient the ledger covers at most 300 of 495 findings, and escalation depends on a sum over the returned lines. If the cut-offs feel wrong on camera, SCR-7 is the fix.
3. **One patient shows one level.** The demo patient has one ledger and so one escalation level. The levels are proven by unit tests and by a short script that serves the four levels from fixtures. The demo should not pretend otherwise.
4. **The question is the only steering.** The model sees the level word, the persona and the tools. If notices ignore the level, strengthen the persona's description of each register, which is the one lever in reach.
5. **`providers.select` reads `MEDIUM_*` variable names.** `main.py` translates its own variables into them. If a third app appears, the names belong in `providers/`, and that is an edit outside this spec.
6. **Maintainers.** The persona and the question must not describe the patient's maintainers as negligent. Checked by reading the persona wording and a sample of notices, not by a test.
7. **No CI job for the UI** is in this spec. The Python side is covered by the existing `pytest`, `ruff` and `import-contracts` jobs.
