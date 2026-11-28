# Requirements: debt-collector
Status: **draft for review.** Nothing here has been started.
## Introduction
The Debt Collector is app 2 of The Crypt: a menacing collector who itemises technical debt with "interest" (the estimated cost of leaving it), issues escalating notices, and offers a ranked repayment plan. It is the app that makes the submission valid (Skeleton Crew needs two separate application folders) and the app that proves the skeleton claim: a second persona is a TOML file, a theme and a thin UI.
The Debt Collector **consumes** the skeleton and adds no code under `skeleton/`. It does not import from `medium/`. `skeleton/api` already ingests snapshots, serves findings and runs the grounded turn at `POST /snapshots/{ref}/ask`, returning `AnswerResult`. The collector is a persona config, a pure interest module, three routes of its own, a theme and a thin UI. It does not re-implement verification, tool routing or prompt assembly.
The split that shapes this spec: **everything numeric is computed in code, and only the prose needs a model.** The ledger and the repayment plan are arithmetic over verified findings. If the provider is down, unfunded or unconfigured, both still render real, cited numbers. Only the notice needs a model.
Priority order when requirements conflict, from `product.md`: truthfulness, then skeleton proof, then legible spookiness, then the measured demo result.
## Scope
In scope: `debt-collector/` (Python and `ui/`), the `debt-collector` import-linter contracts, and the tests that prove them.
Out of scope:
- Anything under `skeleton/`. A need for a change there is a stop condition (R8), not a task.
- Anything under `medium/`. The collector does not import it, copy it or share state with it.
- Changes to `providers/`. The collector imports `providers.select` as it is.
- A banishment-rate harness for the collector. The Medium's harness measured the shared verifier path. A collector harness is a follow-up if the provider budget allows.
- Deployment, rate limiting, spend caps and the pre-cached demo runs under `demo/`.
- A CI job for `debt-collector/ui`. The UI tests run locally and per task.
- Running or modifying the analysed code (`product.md`, non-goals). "Settling" a debt in the UI is session state only.
## Glossary
- **Debt**: one `Finding` priced as one ledger line.
- **Ledger**: the ranked list of debts for one snapshot, with totals and an escalation level. The output of `GET /collector/snapshots/{ref}/ledger`.
- **Principal**: the size of a debt, in lines (R1.2).
- **Interest**: the yearly cost of leaving a debt unpaid, in lines per year (R1.2).
- **Effort**: the estimated cost of paying a debt, in effort points (R1.2).
- **Figure**: a number the collector is allowed to show. Either a value in `Finding.metrics[key]`, or a value `debt-collector/interest.py` computes and names in its `FIGURES` registry (R1.7).
- **Escalation level**: one of four words chosen in code from total severity (R4.2).
- **Notice**: one `AnswerResult` from the skeleton's `/ask` for persona `collector`.
- **Settled debt**: a debt the user marked as paid in the UI. Session state only.
- **Boss**: one of the largest debts by interest, flagged in the ledger payload (R1.8).
---
## R1. Interest, computed in code
**User story:** As the author, I want every debt priced by a deterministic formula in code, so that no number the collector shows ever came from a model.
### Acceptance criteria
1. THE module `debt-collector/interest.py` SHALL turn each `Finding` into a ledger line carrying `principal` and `interest`, derived only from the `Finding` (its `severity`, its line range and its `metrics`) and the snapshot ID. It SHALL read no clock, no random source, no file, no network and no model output.
2. THE formula SHALL be:
   - `principal = line_end - line_start + 1`. Unit: lines.
   - `interest = principal * severity ** 2`. Unit: lines per year. The rate `severity ** 2` is a yearly rate between 0 and 1, so interest never exceeds principal.
   - `effort = 1 + log2(1 + principal)`. Unit: effort points, at least 1. Effort grows with the size of the range, but slower than linearly.
   - `interest_per_effort = interest / effort`. Unit: lines per year per effort point.
   - Every output SHALL be rounded to 6 decimal places.
3. `Finding.metrics` SHALL be carried onto the ledger line unchanged, so every number the analyzers produced is reachable. THE formula SHALL NOT read a metric by name. Severity is already computed from the metrics by each analyzer, so reading them again would double count them and would force this module to change for every new analyzer.
4. THE module SHALL document the unit of every metric key the shipped analyzers emit, in a `METRIC_UNITS` table. A key not in the table SHALL be reported with the unit `unspecified`, never dropped. A test SHALL read the keys the shipped analyzers emit from their source and fail if one is missing from the table.
5. ONE `Finding` SHALL produce exactly one ledger line. Ranking SHALL be by `interest` descending, then `severity` descending, then `finding_id` ascending, so the order is total and does not depend on input order.
6. PROPERTY (Hypothesis): for any valid `Finding`, interest is finite and not negative. For two findings that differ only in severity, the higher severity SHALL NOT have the lower interest. Pricing the same findings twice SHALL give identical output, and shuffling the input SHALL NOT change the ranked output.
7. THE module SHALL expose a `FIGURES` registry naming every value it computes (`principal`, `interest`, `effort`, `interest_per_effort`, `total_principal`, `total_interest`, `total_severity`), each with a unit and a one-line meaning. A test SHALL walk every numeric field of the ledger and plan payloads and fail on a number that is neither in `metrics`, nor in `FIGURES`, nor an integer position (`rank`, `line_start`, `line_end`).
8. THE module SHALL flag the `BOSS_COUNT` debts with the highest interest as `boss = true`, provided their interest is above zero. THE flag SHALL be in the payload from the first release. The visual treatment is cuttable (R9.3).
9. THE module SHALL choose the escalation level (R4.2) from total severity. THE level SHALL NOT decrease when total severity increases.
10. THE ledger and the plan SHALL be pydantic models with frozen configuration, defined in `interest.py`, so the routes return them as they are.
---
## R2. Persona
**User story:** As the product, I want the collector defined as one TOML file, so that the persona is configuration and not code.
### Acceptance criteria
1. THE collector SHALL be `debt-collector/personas/collector.toml` with the fields the skeleton loader requires: `name`, `display_name`, `voice`, `goals`, `allowed_tools`, `example_lines`, `decline_line`, and `theme`. `name` SHALL be `collector` and `theme` SHALL be `ledger`.
2. `allowed_tools` SHALL be a subset of the skeleton's `TOOL_NAMES` and SHALL include `list_findings`, `get_file_facts` and `read_lines`.
3. NO text field (`voice`, `goals`, `example_lines`, `decline_line`) SHALL contain a digit. Models copy persona text, and the digit scan banishes it. THE loader's `warnings` list for the collector SHALL be empty. The loader only warns, so a test SHALL enforce both.
4. `decline_line` SHALL be in character and SHALL NOT claim a fact about the code.
5. THE persona SHALL tell the collector to put every figure only in the structured `figures` list, never to type a number, and to say "I suspect" in the text of a guess, tied to "no tool result supports this". It SHALL also tell the collector **never to state a principal, an interest or a total**, which are shown in the ledger and cannot be quoted by the verifier (R8.3), and to speak only about the findings, the files and the figures the tools return. These instructions SHALL be in persona wording, because the app cannot change the shared grounding prompt.
6. THE persona SHALL describe the register of each escalation level by its word. A test SHALL fail if the voice omits a level word defined in `interest.py`.
7. THE persona's menace SHALL target the code and the passage of time, never the maintainers (`demo-patient.md`, obligations).
8. THE collector SHALL load through `load_personas` in a directory containing only `collector.toml`, and the API SHALL list no other persona for the Debt Collector.
---
## R3. Ledger route
**User story:** As a user, I want the itemised debts, ranked, with real numbers even when the model is down, so that the demo always has something true to show.
### Acceptance criteria
1. THE route SHALL be `GET /collector/snapshots/{ref}/ledger`. It SHALL return the `Ledger` of R1.10: the snapshot ID, the ranked lines (each with `rank`, `finding_id`, `analyzer`, `file`, `line_start`, `line_end`, `severity`, `principal`, `interest`, `boss` and `metrics`), the totals, the escalation level and a coverage note (R3.4).
2. THE route SHALL read findings only through the skeleton API (`GET /snapshots/{ref}` and `GET /snapshots/{ref}/findings`), dispatched in process to the same FastAPI app. It SHALL NOT open the store, call `_open` or `_resolve_dir`, or import the tool router.
3. THE `finding_id` SHALL be the `id` the skeleton returns for the finding. It is the same id the verifier accepts in a figure, so a ledger line and a verified claim can name the same finding.
4. THE skeleton's findings route returns at most 100 findings per call and has no offset. THE route SHALL therefore ask once unfiltered, and when the response reports more matches than it returned, ask once per analyzer and merge by id. THE `Ledger` SHALL carry, per analyzer, the number returned and the number matching, and a `truncated` flag that is true when any analyzer has more matches than returned. THE ledger SHALL NOT claim to be complete when it is not.
5. THE route SHALL make **no model call**. THE app SHALL start and THE route SHALL return 200 with a client that raises on any call, and with no provider configured at all (R4.6).
6. IF the skeleton returns a structured error (for example `snapshot_not_found`), THEN THE route SHALL return it unchanged, with the same status, and SHALL NOT return a partial ledger.
7. A snapshot with no findings SHALL give an empty ledger with zero totals and the lowest escalation level, not an error.
---
## R4. Notice route
**User story:** As a user, I want the collector to issue a notice whose tone matches how much I owe, so that the escalation is earned by the numbers and not improvised by a model.
### Acceptance criteria
1. THE route SHALL be `POST /collector/snapshots/{ref}/notice`. It SHALL make one call to the skeleton's `POST /snapshots/{ref}/ask` for persona `collector`, dispatched in process to the same FastAPI app, and SHALL return the response, status and body, unchanged.
2. THE escalation level SHALL be one of `courtesy`, `reminder`, `demand` and `final`, chosen in code from the ledger's total severity by fixed cut-offs defined as named constants in `interest.py`. THE route SHALL pass the level word to the question text. THE model SHALL NOT decide how angry to be.
3. THE question SHALL be built from one constant template in `debt-collector/notice.py`, SHALL contain no digit, and SHALL depend only on the level word.
4. THE route SHALL NOT call a model, build a prompt, parse model output, or construct a claim, a citation or an `AnswerResult`. A test SHALL grep the route source for `AnswerResult(`, `VerifiedClaim(`, `Citation(`, `LLMRequest` and `assemble_system_prompt`.
5. THEREFORE every claim in a notice has passed the same verifier path as a Medium interview answer. A notice that bypasses the verifier is a defect.
6. WHEN no provider is configured, THE app SHALL still start. THE notice SHALL then come back as the skeleton's own declined `AnswerResult` carrying the collector's `decline_line`, because the flow treats any exception from the model client as a failed attempt. THE ledger and the plan SHALL be unaffected.
7. THE collector SHALL NOT be able to say a computed value in prose: the verifier accepts a figure only if it equals a value in `Finding.metrics`. A test SHALL show that a claim whose text repeats a computed interest is banished as `unbacked_number`. This documents the limit and its workaround (R8.3), and does not work around it.
8. THE process entry SHALL read the provider and model from `COLLECTOR_PROVIDER` and `COLLECTOR_MODEL`, the store path from `CRYPT_STORE`, and SHALL build the client through `providers.select`. IF the provider key is missing, THEN THE entry SHALL log one line naming the variable (never a value) and SHALL fall back to a client that raises `ProviderError`, so R4.6 holds.
---
## R5. Repayment plan
**User story:** As a user, I want a ranked plan that pays the best debts first, so that I know where to start.
### Acceptance criteria
1. THE route SHALL be `GET /collector/snapshots/{ref}/plan`. It SHALL make no model call. It SHALL read findings exactly as the ledger does (R3.2, R3.4, R3.6).
2. EACH plan entry SHALL carry `rank`, `finding_id`, `source` (the finding's `file`, `line_start` and `line_end`), `effort`, `interest`, `interest_per_effort` and `boss`.
3. ENTRIES SHALL be ranked by `interest_per_effort` descending, then `interest` descending, then `finding_id` ascending. Debts with zero interest SHALL be listed last, not omitted, so the plan and the ledger have the same entries.
4. EVERY entry's `source` SHALL resolve through the skeleton's `GET /snapshots/{ref}/files/{path}?line_start=&line_end=` with status 200. The ledger gate in the skeleton guarantees the finding's range exists in the snapshot. A test SHALL check each entry through that route.
5. THE route SHALL NOT construct a `Citation` or a claim. The `source` field names the finding the entry came from and is not a model claim.
---
## R6. UI
**User story:** As a judge, I want the collector to look like an accounts office and to show the debt falling, and I want the skeleton's theme claim to be true.
### Acceptance criteria
1. THE UI SHALL be `debt-collector/ui`, a Vite + React 18 + TypeScript package depending on `@kiroween/ui-shell` by relative link, in the same shape as the shell's own package.
2. THE theme SHALL be one `Theme` data object (`id = "ledger"`) built from the shared `ThemeProvider` tokens. IT SHALL pass the shell's contrast test: every pair in `REQUIRED_PAIRS` SHALL meet `MIN_CONTRAST_RATIO`. This test is not cuttable.
3. NO component, in `skeleton/ui-shell/src/` or `debt-collector/ui/src/`, SHALL branch on `theme.id` or any theme name. A test SHALL grep for it.
4. THE UI SHALL compose the shell's existing `CrtFrame`, `ChatPanel` and `Meter`, and its own ledger list. IT SHALL NOT fork, copy, re-implement or wrap-and-modify a shell component. A test SHALL fail if a file under `debt-collector/ui/src/` declares a component with a shell component's name.
5. THE ledger list SHALL render every ledger line with its rank, `file:line_start-line_end`, severity, principal, interest and its `finding_id`, with the numbers exactly as the ledger returned them and their units labelled. IT SHALL show the escalation level and, when `truncated` is true, the coverage note.
6. THE debt meter SHALL be `Meter` with `value = outstanding_interest / total_interest` (0 when the total is 0), where outstanding interest is the sum of interest over the debts not settled. THE user SHALL settle a debt from the ledger list, and the meter SHALL fall. Settling SHALL send no request and change nothing outside the session.
7. THE collector's prose SHALL be rendered with `ChatPanel`, from the `AnswerResult` of the notice, without reshaping, filtering or re-wording it, so banishments are visible as they are in the Medium. THE UI SHALL display the snapshot's licence through `ChatPanel`'s `licence` prop, taken from `GET /snapshots/{ref}`.
8. WHILE a request is pending, THE UI SHALL show a pending state and SHALL prevent a second submission. IF a request fails, THEN THE UI SHALL show the structured error code and message and SHALL NOT render a partial result. A failed notice SHALL NOT hide the ledger.
9. THE controls SHALL be labelled and operable by keyboard alone. WHERE reduced motion is requested, THE UI SHALL add no animation of its own, through the shell's `useReducedMotion`.
10. THE UI SHALL work with the model down: the ledger, the meter and settling SHALL render from the ledger route alone.
---
## R7. Independence
**User story:** As the author, I want the skeleton claim proven by tests, because it is the judging criterion.
### Acceptance criteria
1. A SHA-256 manifest of every file under `skeleton/` SHALL be identical before and after a full ledger, a full notice and a full plan, run through `create_collector_app` with `FakeLLMClient`.
2. NO file under `skeleton/` SHALL contain `debt-collector`, `debt_collector`, or the collector persona's name, display name, example lines or decline line, apart from the existing grep guards of the skeleton tests that name them in order to ban them. THE existing mention of the word "collector" in `skeleton/ingest/history.py` SHALL be checked and, if it is not a reference to this app, allow-listed with a recorded reason.
3. NO file under `debt-collector/` SHALL import `medium`. THE import-linter configuration SHALL gain a contract that forbids it, and a planted violation SHALL fail the lint, as the existing contracts are tested.
4. NO file under `debt-collector/` SHALL import `anthropic`, `openai`, `boto3` or `google` directly. THE only provider import SHALL be `providers.select`, in `main.py`. A contract SHALL enforce the SDK ban, with a planted violation.
5. NO file under `debt-collector/` SHALL import the verifier's functions (`skeleton.verify.citation`, `.claim`, `.parse`, `.textnorm`, `.flow`), the generator, the prompt assembler, the grounding text, the tool router, the tool implementations, the analysed-snapshot store or the ingest package. Importing result models is allowed: `skeleton.verify.models`, `skeleton.signals.models` and `skeleton.mcp.contract`. A contract SHALL enforce this, with a planted violation.
6. THE `debt-collector/` folder SHALL be at the repository root and SHALL have no `__init__.py`, like `medium/` and `providers/`. THE `ui/` folder SHALL be inside it.
7. THE existing four contracts SHALL keep passing unchanged.
---
## R8. Stop conditions
**User story:** As the author, I want a defined way to fail, so that a pressure to special-case the app is routed to the skeleton instead.
### Acceptance criteria
1. IF a task in this spec appears to need an edit under `skeleton/`, THEN THE task SHALL stop, make no edit there, and record the need under "Skeleton change requests" in `docs/KIRO-USAGE.md`, as the Medium spec's R9 requires.
2. A skeleton change request SHALL state: the requirement or lever that needs it, the evidence (a failing test), the smallest proposed change, and which collector task is blocked.
3. At the time of writing, two needs are known to sit outside the app's reach. Neither blocks a task, because each has a workaround inside the app. They are recorded in `docs/KIRO-USAGE.md` by task 1 so the stop is not a surprise:
   - **SCR-6, computed figures cannot be spoken.** `Figure` in `skeleton/verify` is checked against `Finding.metrics` and `VerifyConfig.allowed_numbers` is fixed when the app is built, not per snapshot. THE collector therefore cannot say a principal, an interest or a total in prose and have it verified. Workaround: the UI shows computed numbers from the ledger payload, and the persona is told to refer to the ledger. Smallest change if wanted: a per-request or per-snapshot source of allowed numbers, or a second figure kind for values the app computes. Opened only if the demo needs interest in the collector's own sentences.
   - **SCR-7, findings have no pagination.** `list_findings` clamps at 100 and has no offset or cursor, while the patient has 495 findings. Workaround: R3.4 asks per analyzer, and the ledger reports `truncated`. Smallest change: an `offset` argument, or a `total_severity` in the response. Opened only if truncation visibly distorts the ledger on the patient.
4. THIS spec SHALL NOT work around a stop by monkeypatching, by forking a skeleton module into `debt-collector/`, or by calling skeleton internals (`_resolve_dir`, `_open`, `VerifyConfig`).
---
## R9. Delivery constraints on the plan
These are requirements on the tasks phase, from the user's brief, `credit-policy.md` and skeleton R8.
1. THE plan SHALL have at most twelve tasks. EACH task SHALL touch one subsystem and at most three files (skeleton R8.1). Lockfiles are not counted; hand-edited config is.
2. EACH task SHALL be runnable on its own in a fresh session, with acceptance criteria listed by ID, and SHALL be run one at a time.
3. IF time is short, THEN work SHALL be cut in exactly this order and never out of it:
   1. Boss fights, the visual treatment for the largest debts. The `boss` flag stays in the payload.
   2. Meter animation, the stepped count-down. The meter still falls, through the shell's own transition.
   3. Sound cues.
   4. The repayment-plan screen. The plan route stays and is tested.
   THE task list SHALL mark each as cuttable and everything else as not cuttable. The cuttable tasks SHALL be built in the reverse of the cut order, so that the last thing cut is the first thing built.
4. THE following SHALL NOT be cut: R1 to R5, R6.2 to R6.10, R7 and R8.
5. EVERYTHING except the notice route SHALL be testable with no provider key. THE notice route SHALL also be tested with `FakeLLMClient`. No task needs a key, so a model outage cannot block the build.
6. THE tasks SHALL use Auto by default and Haiku for boilerplate. No Opus prompt is planned for this spec. Actual credits per phase SHALL be logged in `docs/CREDIT-BUDGET.md`.
