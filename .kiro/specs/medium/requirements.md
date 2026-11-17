# Requirements: medium
Status: **draft for review.** Nothing here has been started.

## Introduction
The Medium is app 1 of The Crypt: a ghost of a legacy system that the user interviews. Every answer cites real files and lines, and the session ends with a resurrection plan for modernising the system. This spec also delivers the first real `LLMClient` (a new top-level `providers/` package) and the first measurement of the banishment rate against a real model (skeleton design watch item 1).

The Medium **consumes** the skeleton and adds no code under `skeleton/`. `skeleton/api` already ingests snapshots, serves findings and file facts, and runs the grounded turn at `POST /snapshots/{ref}/ask`, returning `AnswerResult`. The Medium is a persona config, a theme, a thin UI, a few routes of its own and an evaluation harness. It does not re-implement verification, tool routing or prompt assembly.

Priority order when requirements conflict, from `product.md`: truthfulness, then skeleton proof, then legible spookiness, then the measured demo result.

## Scope
In scope: `providers/`, `medium/`, the fourth import-linter contract, and the tests that prove them.

Out of scope:
- Anything under `skeleton/`. A need for a change there is a stop condition (R9), not a task.
- Anything under `debt-collector/`. It will import `providers/` in its own spec.
- Deployment, rate limiting, spend caps and the pre-cached demo runs under `demo/`.
- Providers other than Anthropic. The `LLMClient` seam keeps them possible.
- Streaming responses. The skeleton's `LLMClient` is a single awaited call.

## Glossary
- **Ghost**: the Medium's persona, `medium/personas/ghost.toml`.
- **Turn**: one `POST /snapshots/{ref}/ask`, which runs at most two attempts (`grounding-rule.md` rule 6).
- **Judged claim**: a claim that reached the verifier, counted once as it appears in an `AnswerResult`: a verified fact or guess in `claims`, or an entry in `banishments`.
- **Verified**: a judged claim with `kind = "fact"` in `claims`.
- **Guess**: a judged claim with `kind = "guess"` in `claims`.
- **Banished**: a judged claim in `banishments`, with its reason code.
- **Declined turn**: an `AnswerResult` with `status = "declined"`.
- **Patient**: the pinned demo repo in `demo/patient.json` (setuptools at its recorded SHA).
- **Band**: a numeric acceptance range for a harness metric (R3.8).

---

## R1. Provider adapter
**User story:** As the system, I want one real `LLMClient`, so that the ghost can talk to a model without the skeleton learning the provider's name.

### Acceptance criteria
1. THE adapter SHALL live in a new top-level package `providers/`. It SHALL NOT live under `skeleton/` (R7.3 of the skeleton spec forbids it) and SHALL NOT live under `medium/` (a sibling app would otherwise import from it).
2. THE adapter SHALL implement `skeleton.personas.llm.LLMClient`: `async def complete(self, request: LLMRequest) -> LLMResponse`.
3. THE adapter SHALL translate `LLMRequest` into one provider call: `system`, `messages`, `tools` (`ToolSpec` to the provider's tool schema) and `max_tokens`.
4. WHEN a `Message` has `role = "assistant"` and `tool_calls`, THE adapter SHALL emit the provider's tool-use blocks. WHEN consecutive `Message`s have `role = "tool"`, THE adapter SHALL merge them into one provider message of tool results, keyed by `tool_call_id`.
5. THE adapter SHALL map the provider's response to `LLMResponse`: text blocks joined into `text`, tool-use blocks into `ToolCall` with the provider's call id preserved in `id`.
6. THE adapter SHALL contain no retry logic. THE provider SDK's own automatic retries SHALL be disabled (zero), so the flow's one-regeneration rule (skeleton R4.12) is the only retry in the system.
7. THE adapter SHALL set an explicit per-call timeout. A call that exceeds it SHALL raise.
8. WHEN the provider returns an error, a timeout, or a response truncated by `max_tokens`, THE adapter SHALL raise `providers.errors.ProviderError`. The flow already treats any exception from the generator as a failed attempt (skeleton R4.15), so the adapter SHALL NOT catch it further.
9. THE text of a `ProviderError` SHALL contain the provider's error class name and HTTP status, if any, and SHALL NOT contain the API key, request headers, the prompt or the model's output.
10. THE adapter SHALL read its API key only from the environment variable `ANTHROPIC_API_KEY`, in one named constructor (`from_env`). Its default constructor SHALL take the key as an argument. Nothing under `skeleton/` reads a key (skeleton R9.7).
11. THE adapter SHALL accept an injected SDK client, so tests run with no network and no key.
12. THE API SHALL still receive the client by argument. Tests under `tests/` SHALL keep using `FakeLLMClient`. No file under `skeleton/` SHALL contain the adapter's module name or the provider's name.
13. THE repo SHALL gain a **fourth** import-linter contract: `skeleton` must not import `providers`. The three existing contracts SHALL keep passing. A planted violation SHALL fail the lint, as the existing contracts are tested.
14. ONE live test, marked `live` and excluded from the default run, SHALL make a real call with a one-tool request and assert a well-formed `LLMResponse`.

---

## R2. Persona
**User story:** As the product, I want the ghost defined as one TOML file, so that the persona is configuration and not code.

### Acceptance criteria
1. THE ghost SHALL be `medium/personas/ghost.toml` with the fields the skeleton loader requires: `name`, `display_name`, `voice`, `goals`, `allowed_tools`, `example_lines`, `decline_line`, and `theme`.
2. `allowed_tools` SHALL be a subset of the skeleton's `TOOL_NAMES` and SHALL include enough tools to answer questions about findings, file facts and line ranges.
3. NO `example_lines` entry SHALL contain a digit. The loader's `warnings` list for the ghost SHALL be empty. The loader only warns, so a test SHALL enforce this.
4. NO other text field (`voice`, `goals`, `decline_line`) SHALL contain a digit either. Models copy persona text, and the digit scan rejects copied numbers.
5. `decline_line` SHALL be in character and SHALL NOT claim a fact about the code.
6. THE persona SHALL tell the ghost to quote figures only through the structured `figures` mechanism, never by typing a number, and to say "I suspect" in the text of a guess. These instructions SHALL be in persona wording (`voice`, `goals`), because the app cannot change the shared grounding prompt.
7. THE persona's humour SHALL target the code and the passage of time, never the maintainers (`demo-patient.md`, obligations).
8. THE ghost SHALL load through `load_personas` in a directory containing only `ghost.toml`, and the API SHALL list no other persona for the Medium.

---

## R3. Banishment-rate harness
**User story:** As the builder, I want to know the banishment rate against a real model before I build the UI, so that if the rate is wrong the fix is cheap prompt and config work.

Both failure modes kill the demo, in opposite directions. **Too lenient:** the model learns that marking a claim as a guess avoids rejection, everything is a guess, no banishment fires, and the signature moment never happens. **Too strict:** the digit scan or the citation rules reject nearly everything, every answer declines, and the demo looks broken, not principled.

### Acceptance criteria
**Question set**
1. THE harness SHALL run a fixed set of 20 questions, stored in `medium/eval/questions.toml`, each with an `id` and a `category`.
2. THE set SHALL contain at least: 4 questions about churn or staleness, 3 about TODO markers, 3 about one named file, 4 that ask for an exact number, 3 that the tools cannot answer (opinions, history outside the snapshot, a file that does not exist), and the 3 resurrection-plan section questions of R6 (requirements, design, tasks), referenced by id from `medium/plan.py` so the wording has one source.
3. THE question set SHALL NOT change between runs that are compared. A change SHALL be a new file version with the old results kept.

**Path under test**
4. THE harness SHALL ask every question through `POST /snapshots/{ref}/ask` of the real skeleton app, with the real adapter, against a retained snapshot of the patient at its pinned SHA. It SHALL NOT call `run_grounded_turn`, `verify_claim` or any generator directly.
5. THE harness SHALL construct the app with `ApiConfig(allow_retained=True)` and ingest the patient through `POST /snapshots` with `intent = "retained"` and the SHA from `demo/patient.json`.

**Metrics** (all computed from `AnswerResult` alone, so they need no skeleton change)
6. THE harness SHALL report, per run and per question category:
   - **Verified share**: verified claims divided by judged claims.
   - **Guess share**: guesses divided by judged claims.
   - **Banished share by reason code**: for each `ReasonCode`, banished claims with that code divided by judged claims.
   - **Declined share**: declined turns divided by turns.
   Also reported, because they decide the two failure modes directly: **turns with at least one banishment** (share of turns), **all-guess turns** (answered turns where every claim is a guess, as a share of answered turns), **first-attempt acceptance** (share of turns whose first attempt was `accepted`), and the model id, patient SHA, date and token usage if the adapter exposes it.
7. A turn with zero judged claims (a decline) SHALL contribute to the declined share and SHALL NOT enter any claim-share denominator. A run with zero judged claims SHALL report claim shares as `n/a`, never 0 or 1.
8. THE bands below SHALL be written into `medium/eval/metrics.py` **before the first live run**, so the measurement cannot rationalise itself. They are starting hypotheses. Changing one SHALL require a recorded reason in `docs/KIRO-USAGE.md`.
   - Guess share ≤ 0.35 of judged claims. (Too lenient above this.)
   - All-guess turns ≤ 0.15 of answered turns.
   - Turns with at least one banishment ≥ 0.10 and ≤ 0.50. (Below 0.10 the signature moment rarely appears on camera; above 0.50 the ghost looks unreliable.)
   - Declined share ≤ 0.15. (Too strict above this.)
   - Verified share ≥ 0.50 of judged claims.
9. THE harness SHALL print each breached band by name, with the measured value and the band, and SHALL exit non-zero when any band is breached.

**Runs and cost**
10. THE harness SHALL write each run's raw per-turn `AnswerResult` JSON and the computed report to `medium/eval/runs/`, so any number in `docs/KIRO-USAGE.md` can be traced to a file.
11. THE harness SHALL be run **at least twice** against the same question set, and both reports SHALL be recorded, because one run of 20 turns is too small to read as a rate. The two reports SHALL NOT be averaged into one figure.
12. THE harness SHALL accept `--max-turns` and SHALL abort after 3 consecutive `ProviderError` turns, so a bad key or an outage does not spend the budget on failures.
13. THE harness SHALL be excluded from the default test run and from CI. Its unit tests SHALL use `FakeLLMClient` and run by default.

**Recording and levers**
14. THE numbers of every run SHALL be recorded in `docs/KIRO-USAGE.md`, with the file path of the raw run.
15. IF a band is breached, THEN the levers SHALL be tried in this order: `cfg.allowed_numbers`, the `GROUNDING` prompt wording, the `classify_attempt` seam in `skeleton/verify/flow.py`. THE app can reach none of them (see R9). THE only lever inside `medium/` is the persona wording of R2.6. THE spec therefore SHALL (a) tune persona wording first, at most two tuning iterations and one re-run per iteration, and (b) if a band is still breached, stop and file a skeleton change request (R9.2) with the run files as evidence. It SHALL NOT edit `skeleton/`.
16. THE harness and its recording SHALL be completed **before any UI task begins** (R10.3).

---

## R4. Interview loop
**User story:** As a user, I want to ask the ghost a question and see its answer with citations, guesses and banishments, so that I can tell what is true.

### Acceptance criteria
1. WHEN the user submits a question, THE UI SHALL send `POST /snapshots/{ref}/ask` with `persona = "ghost"` and the question, and SHALL render the returned `AnswerResult` with the shell's `ChatPanel`.
2. THE UI SHALL NOT reshape, filter, reorder, summarise or re-word the payload. Claims, guesses, banishments, the decline line and the Snapshot ID SHALL reach `ChatPanel` as received.
3. THE UI SHALL display the snapshot's detected licence, taken from `GET /snapshots/{ref}`, through `ChatPanel`'s `licence` prop.
4. WHILE a request is pending, THE UI SHALL show a pending state and SHALL prevent a second submission.
5. IF the request fails (network error, structured API error), THEN THE UI SHALL show the structured error code and message and SHALL NOT render an answer.
6. THE question input SHALL be labelled, operable by keyboard alone, and SHALL submit on Enter.
7. THE Medium SHALL add no route that answers a question. Questions use the skeleton route only.

---

## R5. File-tree possession
**User story:** As a user, I want the file tree to light up where the ghost is speaking, so that I can see which code each claim stands on.

### Acceptance criteria
1. THE UI SHALL derive `cited` for `FileTree` from the citations of the **verified claims** of the latest `AnswerResult`. Citations of banished claims SHALL NOT be marked as cited, because they failed verification and may name no real file.
2. THE UI SHALL pass `cited` and `active` to the shell's `FileTree` props and SHALL NOT fork or wrap its expansion logic. The shell already expands ancestors of cited paths.
3. THE UI SHALL build `FileTree`'s `files` from `GET /snapshots/{ref}/findings` (the set of files with findings) united with the cited files. This is a stated limitation: the skeleton API exposes no file listing, so files with no finding and no citation are absent from the tree. The union guarantees that every cited file is shown.
4. WHERE the user has not asked for reduced motion, THE UI MAY step `active` through the cited files in the order the claims appear, as the ghost "speaks" them. WHERE reduced motion is requested, THE UI SHALL set `active` to the first cited file with no timer. (This sweep is cuttable, R10.5.)
5. WHEN the user selects a file in the tree, THE UI SHALL set `active` to it and SHALL NOT send a request.

---

## R6. Resurrection plan
**User story:** As a user, I want the ghost to end the interview with a plan for modernising the system, so that the session produces something I can act on.

### Acceptance criteria
1. THE Medium SHALL expose `POST /medium/snapshots/{ref}/plan`, returning a `PlanResult`: the Snapshot ID and three sections in fixed order, `requirements`, `design` and `tasks`, each carrying one `AnswerResult` unchanged.
2. EACH section SHALL be produced by one call to the skeleton's `POST /snapshots/{ref}/ask` for persona `ghost`, dispatched in process to the same FastAPI app. THE plan route SHALL NOT call a model, build a prompt, parse model output or construct a claim, citation or `AnswerResult` itself.
3. THEREFORE every claim in a plan section SHALL have passed the same verifier path as an interview answer. A plan that bypasses the verifier SHALL be treated as a defect.
4. THE three section questions SHALL be constants in `medium/plan.py`, SHALL contain no digit, and SHALL be independent of one another. A section's question SHALL NOT embed another section's output, so a banishment in one section cannot corrupt another.
5. IF a section declines, THEN the plan SHALL carry that section's declined `AnswerResult` and the other sections SHALL still be returned. THE route SHALL NOT fill a declined section with generated text.
6. IF the skeleton `ask` returns a structured error for a section (for example `snapshot_not_found`), THEN THE route SHALL return that error unchanged and SHALL NOT return a partial plan.
7. THE UI SHALL render each section with `ChatPanel`, so banishments in a plan are visible exactly as in an interview. (The panel is cuttable, R10.5.)
8. THE plan questions SHALL be among the 20 harness questions (R3.2), so the plan's banishment rate is measured before the plan UI is built.

---

## R7. CRT theme
**User story:** As a judge, I want the Medium to look like a haunted terminal, and I want the skeleton's theme claim to be true.

### Acceptance criteria
1. THE Medium theme SHALL be one `Theme` data object (`id = "seance"`) built from the shared `ThemeProvider` tokens: colours, font, effects and sounds.
2. THE theme SHALL pass the shell's contrast test: every pair in `REQUIRED_PAIRS` SHALL meet `MIN_CONTRAST_RATIO`.
3. NO component, in `skeleton/ui-shell/src/` or `medium/ui/src/`, SHALL branch on `theme.id` or any theme name. A test SHALL grep for it.
4. THE Medium UI SHALL NOT fork, copy or wrap-and-modify a shell component. Layout composition of shell components is allowed.
5. WHERE reduced motion is requested, THE theme's flicker and any animation SHALL be disabled through the shell's existing `useReducedMotion` handling, not through new per-app code.
6. THE theme MAY define sound cues for the events the shell emits. (Cuttable, R10.5.)

---

## R8. Independence
**User story:** As the author, I want the skeleton claim proven by tests, because it is the judging criterion.

### Acceptance criteria
1. A SHA-256 manifest of every file under `skeleton/` SHALL be identical before and after a full Medium turn and a full plan, run through `create_medium_app` with `FakeLLMClient`.
2. NO file under `skeleton/` SHALL contain the strings `medium`, `ghost`, `providers` or `anthropic`, apart from the existing import-linter configuration of skeleton R7.3 and the grep guards of the skeleton tests that name them in order to ban them.
3. NO file under `medium/` SHALL import `anthropic`, `openai` or `boto3` directly, nor `debt_collector`. THE only provider import in `medium/` SHALL be from `providers`.
4. NO file under `medium/` SHALL import the verifier's functions (`skeleton.verify.citation`, `.claim`, `.parse`, `.textnorm`, `.flow`), the generator, the router or the prompt assembler. Importing the result models (`skeleton.verify.models`) is allowed, and nothing else from `skeleton.verify`.
5. THE `medium/` and `providers/` folders SHALL be at the repository root.

---

## R9. Stop conditions
**User story:** As the author, I want a defined way to fail, so that a pressure to special-case the app is routed to the skeleton instead.

### Acceptance criteria
1. IF a task in this spec appears to need an edit under `skeleton/`, THEN THE task SHALL stop, make no edit there, and record the need under "Skeleton change requests" in `docs/KIRO-USAGE.md`.
2. A skeleton change request SHALL state: the requirement or lever that needs it, the evidence (run files or a failing test), the smallest proposed change, and which Medium task is blocked.
3. At the time of writing, three levers named by R3.15 and one UI need are already known to be outside the app's reach. They are recorded here so the stop is not a surprise:
   - `cfg.allowed_numbers`: `skeleton/api/app.py` builds `VerifyConfig()` inline in the `ask` route, with an empty `allowed_numbers`. There is no injection point.
   - `GROUNDING` prompt wording: a module constant in `skeleton/personas/grounding.py`, assembled by `assemble_system_prompt`. The persona's `voice` and `goals` are the only text the app controls.
   - `classify_attempt`: a module-level function in `skeleton/verify/flow.py`. It is not injectable.
   - File listing: the API has no route returning the code graph's file list (R5.3 works around it for now).
4. THIS spec SHALL NOT work around a stop by monkeypatching, by forking a skeleton module into `medium/`, or by calling skeleton internals (`_resolve_dir`, `_open`, `VerifyConfig`). Each of those would make the measured behaviour differ from the deployed behaviour.

---

## R10. Delivery constraints on the plan
These are requirements on the tasks phase, from the user's brief, `credit-policy.md` and skeleton R8.

1. EACH task SHALL touch exactly one subsystem and at most three files (skeleton R8.1). Lockfiles are not counted; hand-edited config is.
2. EACH task SHALL be runnable on its own in a fresh session, with acceptance criteria listed by ID, and SHALL be run one at a time.
3. THE ordering SHALL place providers, the persona and the whole harness (R3), including the recorded live run and its tuning, **before any UI task**. IF the rate is wrong, the fix is in persona wording or a skeleton change request, and that must be learned while there is time to act.
4. THE live harness runs SHALL be tasks of their own, because they spend the separate provider budget (`tech.md`), not Kiro credits.
5. IF time is short, THEN work SHALL be cut in exactly this order and never out of it:
   1. Theme sound cues (R7.6).
   2. The possession sweep animation (R5.4); the static cited set stays.
   3. The plan panel in the UI (R6.7). The plan route stays and is measured. This cut costs a visible feature, so it is last.
   THE task list SHALL mark each as cuttable and everything else as not cuttable.
6. THE following SHALL NOT be cut: R1, R2, R3, R4, R6.1 to R6.6, R7.2, R7.3, R8 and R9, and the accessibility criteria R4.6 and R7.5.
7. THE tasks SHALL log actual credits per phase in `docs/CREDIT-BUDGET.md` and SHALL use Auto by default, Haiku for boilerplate. No Opus prompt is planned for this spec.
