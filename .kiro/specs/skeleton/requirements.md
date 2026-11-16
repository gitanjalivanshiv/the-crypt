# Requirements: skeleton

Status: **reviewed; open questions resolved.** Ready for design. Resolutions are recorded at the end of this document.

## Introduction

`skeleton/` is the shared core of The Crypt. It reads a real open-source Python codebase, derives facts from it, and lets a persona talk about it without lying. It contains seven subsystems: Ingest, Signals, Personas, Verify, MCP, UI shell and API.

The skeleton contains nothing persona-specific. The Medium, the Debt Collector and any later persona consume it and must not require edits to it (`product.md` goal 2, `structure.md` rule 2).

Priority order when requirements conflict, from `product.md`: truthfulness, then skeleton proof, then legible spookiness, then the measured demo result.

## Scope

In scope: everything under `skeleton/`, plus the tests that prove it.

Out of scope for this spec:
- Anything under `medium/` or `debt-collector/`: interview loop, resurrection plan, interest formula, notices, boss fights, app-specific themes.
- Implementations of the `complexity`, `dependency_age` and `dead_code` analyzers (design only, see R2.8).
- Grammars other than Python.
- A concrete LLM provider adapter. Only the `LLMClient` interface and a test fake are in scope.
- Deployment, rate limiting, spend caps, and the cached demo runs.
- Executing, building or modifying the analysed code (non-goal in `product.md`).

## Glossary

- **Snapshot**: the analysed repo at one pinned commit SHA. Everything is verified against it, never against upstream.
- **Snapshot ID**: the commit SHA. For an archive with no git metadata, a SHA-256 of the archive contents (see Open Question 2).
- **Code graph**: files, symbols and imports extracted from a snapshot.
- **Finding**: the record every analyzer emits: `analyzer`, `file`, `line_start`, `line_end`, `evidence`, `severity`, `metrics`.
- **Citation**: `{file, line_start, line_end, quote?}` as defined in `grounding-rule.md`.
- **Claim**: one sentence of persona output. It has text, zero or more citations, zero or more quoted figures, and a flag marking it as an explicit guess.
- **Banishment**: the structured record of a rejected claim, which the UI renders struck through with the reason.
- **Line count of a file**: the number of lines after splitting on `\n`, `\r\n` or `\r`, where a single trailing line terminator does not start a new line. An empty file has 0 lines.
- **Normalised line**: a line with its terminator removed and trailing whitespace stripped. This is the only normalisation permitted when comparing quotes (`grounding-rule.md` rule 3).

---

## R1. Ingest

**User story:** As a persona app, I want to hand the skeleton a repo URL or an archive and get back a pinned, queryable snapshot, so that every later fact refers to one fixed body of code.

### Acceptance criteria

**Sources**

1. WHEN given a public git repo URL, THE Ingest SHALL clone it and produce a snapshot.
2. WHEN given an uploaded archive, THE Ingest SHALL unpack it and produce a snapshot. Supported formats are `.zip`, `.tar.gz` and `.tgz`. **Cuttable, position 2 in R8.5:** the demo patient is a pinned URL and never exercises this path, while the path carries its own security surface.
3. THE Ingest SHALL accept only `https://` repo URLs. IF the URL uses another scheme, is a local path, or resolves to a loopback, link-local or private address, THEN THE Ingest SHALL reject it with the failure code `invalid_source` before any network or filesystem access.
4. IF the archive is of an unsupported format, THEN THE Ingest SHALL reject it with `invalid_source`.

**Pinning**

5. THE Ingest SHALL resolve and record the exact commit SHA analysed. The SHA is part of the snapshot and is immutable for its lifetime.
6. WHEN a repo URL names a branch, tag or no ref, THE Ingest SHALL resolve it to a full 40-character SHA once, and every later read SHALL use that SHA, not the ref.
7. WHEN a repo URL or request supplies an explicit SHA, THE Ingest SHALL check out that SHA. IF it does not exist in the repo, THEN THE Ingest SHALL fail with `ref_not_found`.

**Limits**

8. THE Ingest SHALL enforce these limits, all configurable, with these defaults: maximum snapshot size **500 MB**, clone timeout **180 seconds**, maximum file count **50,000**. The pinned demo patient is 49.7 MB, so the size default leaves roughly tenfold headroom.
9. IF the size limit or the file-count limit is exceeded during clone or unpack, THEN THE Ingest SHALL abort, delete partial output, and fail with `size_limit_exceeded` or `file_limit_exceeded` respectively.
10. IF the clone exceeds the timeout, THEN THE Ingest SHALL terminate the git process, delete partial output, and fail with `clone_timeout`.
11. WHILE unpacking an archive, THE Ingest SHALL measure decompressed size and abort on the size limit, so a small archive that expands enormously (decompression bomb) is rejected.
12. IF an archive entry resolves outside the unpack root (`../`, absolute path), or is a symlink or hard link pointing outside it, THEN THE Ingest SHALL fail with `unsafe_archive`.

**Safety**

13. THE Ingest SHALL NOT execute, import, build or install any code from the analysed repo, and SHALL disable git hooks and filters during clone.
14. THE Ingest SHALL detect the repo licence from its `LICENSE` file at ingest time and record the SPDX identifier in the snapshot.
15. THE licence gate SHALL depend on how the snapshot will be used:
    - **Retained** (the demo patient, anything cached under `demo/`, anything committed to this repo): IF the detected licence is not MIT, BSD-2/3-Clause or Apache-2.0, THEN THE Ingest SHALL fail with `licence_not_permitted`. A missing or unrecognised licence file counts as not permitted.
    - **Ephemeral** (a repo URL supplied by a user at runtime): THE Ingest SHALL record the detected licence, or `unknown`, and proceed. THE snapshot SHALL be marked `retainable = false`, SHALL NOT be cached, committed or reused across sessions, and SHALL be deleted when the session ends. THE UI SHALL display the detected licence.
15a. THE caller SHALL declare the intended use, `retained` or `ephemeral`, when requesting ingest. THE default SHALL be `ephemeral`, so the non-retaining path is the one reached by omission.
15b. Rationale: a hard gate on every path would reject a judge pasting their own repo URL, which is the interaction that carries the Potential Impact criterion. The licence concern is about retaining and redistributing code, so the gate binds where code is retained.

**Code graph**

16. THE Ingest SHALL parse every `.py` file with tree-sitter using the Python grammar only, and SHALL expose the grammar choice as a `SUPPORTED_GRAMMARS` list containing only `python`.
17. THE code graph SHALL contain, for every file in the snapshot: its path relative to repo root, its line count, and whether it was parsed. Non-Python files appear as files with `parsed = false`.
18. THE code graph SHALL contain, for every parsed file, its symbols (modules, classes, functions, methods) with name, kind, `line_start` and `line_end`.
19. THE code graph SHALL contain, for every parsed file, its imports with the imported module name, the imported names, and the line of the statement. Imports that resolve to a file inside the snapshot SHALL link to that file.
20. IF a file has a syntax error, THEN THE Ingest SHALL still return whatever symbols and imports tree-sitter recovered, mark the file `has_syntax_errors = true`, and continue with the other files.
21. IF a file cannot be decoded as UTF-8, THEN THE Ingest SHALL include it in the graph with `parsed = false` and `decodable = false`, and SHALL NOT fail the ingest.
22. THE Ingest SHALL NOT follow symlinks when walking the snapshot. Symlinks are recorded as entries with `is_symlink = true` and are never read as files.

**Git history metadata**

23. WHEN the snapshot has git history, THE Ingest SHALL attach to every file: commit count, last-modified date (committer date of the last commit touching it, as of the pinned SHA), and distinct author count. All three SHALL be computed only from commits reachable from the pinned SHA.
24. IF the snapshot has no git history (an archive without `.git`), THEN every file's history metadata SHALL be explicitly `unavailable`, never zero or a made-up date, and the snapshot SHALL carry `history_available = false`.
25. THE Ingest SHALL record, as snapshot metadata: Snapshot ID, source (URL or archive name), licence SPDX id, clone or unpack date, file count, and total size in bytes.

**Determinism**

26. GIVEN the same snapshot, THE Ingest SHALL produce an identical code graph and history metadata on every run, with files and symbols in a stable sorted order.

---

## R2. Signals

**User story:** As a persona, I want facts about the code that were computed by code, so that every number and quote I use is real.

### Acceptance criteria

**Finding shape**

1. THE Signals subsystem SHALL define a `Finding` type with exactly these fields: `analyzer` (string), `file` (string), `line_start` (int), `line_end` (int), `evidence` (string), `severity` (float), `metrics` (mapping of string to number).
2. THE `evidence` of every finding SHALL equal the normalised lines `line_start` through `line_end` of `file` in the snapshot, joined by `\n`. It SHALL NOT be paraphrased, truncated mid-line or reformatted.
3. THE `file`, `line_start` and `line_end` of every finding SHALL satisfy the citation validity rule: the file exists in the snapshot and `1 <= line_start <= line_end <= line count`.
4. THE `severity` of every finding SHALL be a float in `[0.0, 1.0]`, computed by deterministic code in the analyzer from `metrics` and the snapshot. No model call is involved at any point.
5. THE `metrics` of every finding SHALL contain only JSON-serialisable numbers (int or float, no NaN or infinity). Metric keys and units are documented per analyzer, and these are the only numbers a persona may quote.
6. GIVEN the same snapshot, every analyzer SHALL return identical findings in a stable order on every run.

**Plugin protocol**

7. THE Signals subsystem SHALL define one analyzer protocol with: a unique `name`, a declared set of required inputs (`needs_history`), and a method taking a snapshot and returning findings.
8. THE design SHALL specify `complexity`, `dependency_age` and `dead_code` as implementations of the same protocol (name, inputs, metric keys, severity approach). THE skeleton SHALL NOT contain implementations of them, and the registry SHALL NOT list them.
9. THE registry in `skeleton/signals/__init__.py` SHALL list exactly the analyzers `churn`, `staleness` and `todo_age` for v1.
10. Each analyzer SHALL be one module under `skeleton/signals/`. Adding an analyzer SHALL require only a new module and one registry entry. No analyzer SHALL import or refer to a persona.
11. IF an analyzer with `needs_history = true` runs on a snapshot where `history_available = false`, THEN THE Signals subsystem SHALL skip it and report it as `skipped: history_unavailable`, and SHALL NOT return findings with fabricated numbers.
12. IF one analyzer raises an error, THEN THE Signals subsystem SHALL report that analyzer as `failed` with the error, and SHALL still return findings from the other analyzers.

**churn**

13. THE `churn` analyzer SHALL emit one finding per file whose commit count meets a configured threshold, with metrics `commit_count` and `author_count`.
14. THE `churn` severity SHALL increase monotonically with `commit_count` and SHALL be 0.0 for a file with one commit.

**staleness**

15. THE `staleness` analyzer SHALL compute `days_since_modified` as the whole days between the last-modified date of the file and the **date of the pinned commit**, not the wall-clock date. This makes results reproducible.
16. THE `staleness` analyzer SHALL emit one finding per file whose `days_since_modified` meets a configured threshold, with metrics `days_since_modified` and `commit_count`.
17. THE `staleness` severity SHALL increase monotonically with `days_since_modified`.

**todo_age**

18. THE `todo_age` analyzer SHALL find comments containing the markers `TODO`, `FIXME`, `HACK` or `XXX`, using tree-sitter comment nodes, so a marker inside a string literal is not reported.
19. FOR each marker, THE `todo_age` analyzer SHALL determine from `git blame`, as of the pinned SHA, the commit that **last changed** the marker's line, and emit a finding with metrics `age_days` (whole days between that commit and the pinned commit date) and `todo_count_in_file` (the number of markers in that file). The marker kind appears in `evidence`, not in `metrics`.
19d. `age_days` SHALL be documented, in the metric description the MCP contract returns, as "days since this line last changed" and NOT as "age of the TODO". `git blame` reports last modification, not introduction, so editing a marker's wording resets its age. The persona SHALL NOT be given wording that claims otherwise. An earlier draft of this requirement said "introduced"; the requirement was wrong and the design was right.
19a. THE `todo_age` analyzer SHALL invoke `git blame` **at most once per file**, only for files containing at least one marker, and SHALL derive every marker's age from that single result. Per-marker blame invocation is forbidden: at the scale of the demo patient it takes minutes, which breaches the 60-second analysis budget in `demo-patient.md` and would silently flip the patient decision rule for the wrong reason.
19b. THE `todo_age` analyzer SHALL cap markers processed per snapshot at a configurable maximum, default 2,000. IF the cap is reached, THEN the analyzer SHALL report `truncated = true` alongside the total count found, and SHALL NOT return a partial list that reads as complete.
20. THE `todo_age` severity SHALL increase monotonically with `age_days`.
21. THE `todo_age` analyzer SHALL declare `needs_history = true`.

---

## R3. Personas

**User story:** As a persona author, I want to define a persona in a TOML file, so that adding a persona needs no change under `skeleton/`.

### Acceptance criteria

1. THE Personas subsystem SHALL define a TOML schema with these required fields: `name` (identifier), `display_name`, `voice` (prose), `goals` (non-empty list of strings), `allowed_tools` (list of MCP tool names), `example_lines` (non-empty list of strings), and `decline_line` (the in-character refusal used when verification fails twice, per `grounding-rule.md` rule 6).
2. THE schema MAY contain an optional `theme` field naming a UI theme. The skeleton SHALL treat it as an opaque identifier.
3. THE Personas subsystem SHALL provide a loader that reads a persona from a file path or a directory of TOML files supplied by the caller, and returns a validated persona object.
4. IF a file is invalid TOML, is missing a required field, has a field of the wrong type, has an empty required list, or contains an unknown key, THEN THE loader SHALL raise an error naming the file and the offending field. It SHALL NOT silently default or ignore.
5. IF `allowed_tools` names a tool that is not exposed by the MCP subsystem (R5), THEN THE loader SHALL reject the persona and name the unknown tool.
6. THE persona schema SHALL NOT contain any field that can disable, weaken or configure verification. Grounding is not persona-configurable.
7. THE Personas subsystem SHALL provide base prompt assembly that combines, in a fixed order: the grounding rules (citation format, guess marking, numbers only from `metrics`), the persona's voice, goals, example lines, and the snapshot ID. Persona text SHALL NOT be able to alter or precede the grounding section.
8. THE persona loader and prompt assembly SHALL work for a persona that did not exist when the skeleton was written. This is tested with a third fixture persona, loaded with no edit under `skeleton/`.

---

## R4. Verify

**User story:** As a user, I want any claim the persona cannot back up to be rejected and shown as rejected, so that I can trust what remains.

This is the component that must have no untested branch (`grounding-rule.md`). Its requirements are written to be enumerable: every reason code below needs at least one test, and every rejection path needs a property-based or fuzz test.

### Acceptance criteria

**Citation verification**

1. THE Verifier SHALL check each citation against the snapshot only, never the network and never upstream.
2. THE Verifier SHALL reject a citation with exactly one of the following reason codes, evaluated in this order, and SHALL stop at the first that applies:
   - `malformed`: a required field is missing, has the wrong type, or `line_start` or `line_end` is not an integer (booleans are not integers).
   - `path_unsafe`: the path is absolute, contains a `..` segment, contains a NUL byte, contains a backslash, or is empty, or after resolution lies outside the snapshot root.
   - `file_not_found`: the path does not name a regular file in the snapshot.
   - `symlink`: the path, or any parent segment of it, is a symlink.
   - `range_invalid`: `line_start < 1`, or `line_start > line_end`.
   - `range_out_of_bounds`: `line_end` is greater than the file's line count. A file with 0 lines therefore rejects every citation.
   - `file_unreadable`: the file cannot be decoded as UTF-8 and a `quote` is present.
   - `quote_mismatch`: `quote` is present and does not equal the file's lines `line_start` through `line_end`.
3. THE Verifier SHALL return `valid` only when no reason code applies.
4. WHEN comparing a quote, THE Verifier SHALL normalise only line terminators (`\r\n`, `\r`, `\n` all treated as one terminator) and trailing whitespace on each line, in both the quote and the file. It SHALL NOT normalise case, leading whitespace, interior whitespace, unicode form (NFC vs NFD), or tabs vs spaces. Therefore a quote that differs only by unicode normalisation form or by a homoglyph SHALL be rejected.
5. IF `quote` is absent, THEN THE Verifier SHALL still validate file and range (rules `malformed` through `range_out_of_bounds`).
6. THE Verifier SHALL be a pure function of its inputs and the snapshot. It SHALL NOT mutate the snapshot and SHALL NOT raise on any input. A bad input produces a rejection, never an exception.

**Claim verification**

7. A claim SHALL be accepted as fact only if it has at least one citation and every one of its citations is valid.
8. IF a claim has no citation and is not flagged as a guess, THEN THE Verifier SHALL reject it with `uncited_claim`.
9. IF a claim is flagged as a guess, THEN THE Verifier SHALL accept it and mark it as a guess. A guess SHALL NOT carry figures (see 10). A claim that is a guess and has citations SHALL have its citations verified like any other.
10. Every figure in a claim SHALL be given as a reference to a finding and a metric key. THE Verifier SHALL reject, with `figure_not_in_metrics`, any figure whose value is not exactly equal to that finding's `metrics[key]`, or whose finding does not exist in the snapshot's findings, or whose key is absent. It SHALL NOT round, convert units or compute.
11. THE Verifier SHALL reject, with `figure_not_cited`, any claim whose figure refers to a finding whose file is not among the claim's own citations.
11a. THE Verifier SHALL additionally scan the rendered text of every claim for digit sequences, and SHALL reject with `unbacked_number` any digit sequence that is not one of: the value of a declared figure; text lying inside a verified `quote`; a line number matching a citation on the same claim; the Snapshot ID; or a member of a short documented allow-list.
11b. Rule 11a is a backstop, not the primary mechanism. Structured figures (rule 10) remain how a persona states a number. 11a exists because the product's premise is that numbers never originate from the model, and a number written straight into prose would otherwise pass unchecked. The `quote` exemption is what lets dates and version numbers inside cited source survive.
11c. THE test suite SHALL include a case where the generator writes a plausible but unbacked number into prose, and SHALL assert it is rejected with `unbacked_number`.

**Reject and regenerate once**

12. THE Verifier SHALL provide a flow that takes an answer generator (via the `LLMClient` interface), verifies the answer, and on any rejection asks the generator for exactly one replacement, passing the structured rejection reasons.
13. IF the replacement verifies fully, THEN THE flow SHALL return it. IF the replacement still has a rejected claim, THEN THE flow SHALL NOT call the generator again, and SHALL return a decline result containing the persona's `decline_line`.
14. THE flow SHALL call the generator at most twice per user turn. This SHALL be asserted by a test with a generator that always fails and counts its calls.
15. IF the generator raises or returns something that cannot be parsed into claims, THEN THE flow SHALL treat it as a failed attempt under the same one-regeneration limit, and SHALL NOT raise to the caller.
16. THE flow SHALL return only verified claims and guesses as renderable. A rejected claim SHALL NOT be present in any renderable list.
17. THE result of the flow SHALL always include the Snapshot ID (`grounding-rule.md` rule 5).

**Banishment**

18. THE Verifier SHALL emit, for each rejected claim, a structured banishment record containing: the claim text, the failing citation or figure, the reason code, a human-readable reason message, the attempt number (1 or 2), and the Snapshot ID.
19. Banishment records from the first attempt SHALL be preserved in the result even when the second attempt succeeds, so the UI can show them. They SHALL NOT be dropped silently.
20. THE reason codes SHALL be a closed, documented enumeration. The UI renders from the code and message, and SHALL NOT need to parse free text.

**Required tests**

21. THE test suite SHALL include a Hypothesis property test: for any generated answer, every claim marked as fact has citations that resolve to a real file with in-range lines, and every quote matches the source after the allowed normalisation.
22. THE test suite SHALL include a Hypothesis property test for the converse: any citation built by mutating a valid one (shifting a line number out of range, inverting the range, altering a quote by one character) is rejected with the expected reason code.
23. THE test suite SHALL fuzz the verifier with: fabricated paths, `../` traversal, absolute paths, NUL bytes, backslashes, symlinks (file and parent directory), out-of-range and inverted ranges, off-by-one ranges at both ends, altered quotes, unicode and CRLF variants, and empty files. Every case that must be rejected SHALL be rejected with the specific reason code in 2.
24. THE test suite SHALL achieve 100% line and branch coverage of `skeleton/verify/`, enforced in CI by a coverage threshold that fails the **test job** below 100%.
24a. THE coverage gate SHALL NOT sit in the deploy path. Deployment SHALL remain possible while the gate is red. The gate exists to protect the verifier's correctness; it must never be able to prevent a submission before 2026-12-04 14:00 PT. A red gate is a reason to stop and fix the verifier, not a reason to be unable to ship.
25. THE verify tests SHALL exist, and pass, before any persona-dependent code is implemented (task ordering requirement, R8.3).

---

## R5. MCP

**User story:** As a persona, I want to query the signals through tools, so that I get facts instead of guessing them.

### Acceptance criteria

1. THE MCP subsystem SHALL provide an MCP server that exposes the signals for one snapshot.
2. THE server SHALL expose these tools, all read-only:
   - `get_snapshot`: Snapshot ID, source, licence, `history_available`, file count.
   - `list_findings`: filter by `analyzer`, `file` and `min_severity`, with a `limit`. Returns full `Finding` objects, ordered by severity descending, then file, then `line_start`.
   - `get_file_facts`: for one file, its line count, symbols, imports, and history metadata.
   - `read_lines`: for one file, return the normalised lines `line_start` through `line_end`, so a persona can quote exactly.
3. THE server SHALL tag every tool response with the Snapshot ID.
4. THE tools SHALL apply the same path and range validation as R4.2 and SHALL return a structured error with the same reason codes, not an exception or a crash, when given a bad path or range.
5. IF `limit` is absent, THEN THE server SHALL apply a default; IF `limit` exceeds a maximum, THEN THE server SHALL clamp it and say so in the response.
6. WHEN a persona's `allowed_tools` is supplied, THE server (or its session wrapper) SHALL expose only those tools and SHALL reject calls to others with `tool_not_allowed`.
7. THE server SHALL NOT expose any tool that writes, executes, or fetches from the network.
8. THE tool names, input schemas and error codes SHALL be documented in one machine-readable contract, and the test suite SHALL check the running server against it.
9. THE tool result for an analyzer that was skipped or failed SHALL say so (R2.11, R2.12), and SHALL NOT return an empty list that looks like "no problems found".
10. THE server SHALL be registerable in `.kiro/settings/mcp.json` without changes to the skeleton.

---

## R6. UI shell

**User story:** As an app author, I want themeable React components, so that a new app needs a theme and a thin entry point, not new components.

### Acceptance criteria

**Components**

1. THE UI shell SHALL provide these components, written in TypeScript for React 18: `CrtFrame` (terminal frame), `FileTree`, `ChatPanel`, `Meter` and sound hooks.
2. THE `FileTree` SHALL render the snapshot's file paths as a collapsible tree, and SHALL accept a set of cited paths. WHEN a path is cited, THE `FileTree` SHALL expand its ancestors, highlight it, and scroll it into view.
3. THE `FileTree` highlight SHALL be driven only by props, so any app can drive it from its own state.
4. THE `ChatPanel` SHALL render a list of messages made of verified claims, guesses, banishments and declines. A verified claim shows its citations. A guess is visibly marked as a guess. A banishment shows the claim struck through with its reason message. A decline shows the persona's `decline_line`.
5. THE `ChatPanel` SHALL render from the structured result in R4 and SHALL NOT render any claim that is not in the renderable list.
6. THE `ChatPanel` SHALL display the Snapshot ID.
7. THE `Meter` SHALL render a value from 0 to 1 with a label, and SHALL animate between values. It SHALL make no assumption about what it measures, so a debt meter or a risk meter are both possible.
8. THE sound hooks SHALL let an app register named sounds and play them on events (for example `cite`, `banish`, `escalate`). The sound hooks SHALL NOT play audio before a user gesture, and SHALL provide a mute toggle that defaults to muted until the user opts in.

**Theming**

9. THE UI shell SHALL ship two themes, applied through one component set. A theme is data (design tokens such as colours, fonts, glow, scanline strength, sound map) and SHALL NOT fork or replace any component.
10. Adding a third theme SHALL need only a new theme definition and no edit to any component. This is tested by rendering all components with a fixture third theme.
11. THE two shipped themes SHALL be reference themes. Final app-specific theming belongs to later specs.

**Legibility and accessibility**

12. THE text in both shipped themes SHALL meet WCAG AA contrast (4.5:1) against its background, checked by an automated test of the tokens. Atmosphere SHALL NOT cost legibility (`product.md` goal 3).
13. WHEN the user's system has `prefers-reduced-motion`, THE UI shell SHALL disable flicker, scanline movement and meter animation.
14. THE `FileTree` and `ChatPanel` SHALL be operable by keyboard and expose roles and labels to screen readers. A banished claim SHALL be conveyed by text, not only by strikethrough styling.
15. THE UI shell SHALL NOT import from `medium/` or `debt-collector/`, and SHALL NOT contain persona names or persona-specific copy.

---

## R7. Skeleton independence (cross-cutting)

**User story:** As the author, I want the skeleton proven reusable, so that the judging criterion of versatility is demonstrated by a test and not by a claim.

### Acceptance criteria

1. NOTHING under `skeleton/` SHALL import from `medium/` or `debt-collector/`. A lint rule in CI SHALL fail the build on a violation, for Python and for TypeScript.
2. A test SHALL load a third fixture persona (R3.8) and a fixture theme (R6.10), run the verify flow with a fake `LLMClient`, and pass without any file under `skeleton/` being modified. The test SHALL fail if a file under `skeleton/` is referenced by name for that persona.
3. THE skeleton SHALL define one `LLMClient` interface, with a fake implementation for tests. The provider is swappable behind it (`tech.md`). No provider SDK SHALL be imported by `skeleton/` outside a single adapter module, and no adapter is in this spec.
4. NO secrets or API keys SHALL be read, logged or stored by the skeleton.

---

## R8. Delivery constraints on the plan

These are requirements on the tasks phase, from the user's brief and `credit-policy.md`.

1. EACH task SHALL touch exactly one subsystem and at most three files.
2. EACH task SHALL be runnable on its own in a fresh session, with its acceptance criteria listed by ID.
3. THE ordering SHALL place all Verify tasks, including the Hypothesis property tests (R4.21, R4.22), the fuzz tests (R4.23) and the coverage gate (R4.24), before any task that implements or depends on Personas. The Personas loader and persona-dependent prompt assembly come after.
4. THE task list SHALL be executed one task at a time. It SHALL NOT be run as a batch.
5. IF time is short, THEN work SHALL be cut in exactly this order and never out of it:
   1. OpenAPI-to-TypeScript codegen and its CI diff gate (hand-write the UI types)
   2. R1.2 archive ingest (the demo patient is a pinned URL)
   3. The job and polling API (R9.2 becomes synchronous with a timeout)
   4. R6.10 third-theme fixture test
   5. R6.8 sound hooks
   6. R6.7 meter animation (the meter still renders, it just stops animating)
   7. R2 `todo_age` analyzer
   8. R2 `staleness` analyzer
   THE task list SHALL mark each of these as cuttable, and everything else as not cuttable. Positions 1 to 3 cost the demo nothing and are therefore cut first; 7 and 8 each cost a visible signal and are cut last.
5a. THE following SHALL NOT be cut under any circumstances: all of R4 (Verify), including its property-based tests, fuzz tests and coverage gate; R6.12 contrast and R6.14 keyboard and screen-reader operability; and all of R7. The verifier is the product's differentiator, and R6.12 and R6.14 carry Design-criterion points at judging.
5b. R6 is the largest block of discretionary work in this spec. Before R6 begins, the remaining credit balance and day count SHALL be checked against `docs/CREDIT-BUDGET.md`.

---

## R9. API

**User story:** As an app, I want one HTTP surface over the skeleton, so that both apps share it instead of each building their own.

This subsystem was absent from the original brief, which named six subsystems while `tech.md` specifies FastAPI. Without it, each app builds its own service layer, the same work is done twice, and the skeleton-versatility claim (`product.md` goal 2) weakens at precisely the point judges examine.

### Acceptance criteria

1. THE API SHALL be a FastAPI application under `skeleton/api/`, persona-agnostic. It SHALL NOT contain persona names, persona copy, or app-specific routes.
2. THE API SHALL expose: `POST /snapshots` (ingest a URL or archive; returns **202 with a job identifier**, since the commit SHA is not known until the ref resolves, which can take the whole clone), `GET /jobs/{job_id}` (job status, stage, and the Snapshot ID once resolved), `GET /snapshots/{id}` (metadata per R1.25), `GET /snapshots/{id}/findings` (the filters of R5.2 `list_findings`), `GET /snapshots/{id}/files/{path}` (file facts per R5.2 `get_file_facts`), and `POST /snapshots/{id}/ask` (run the verify flow of R4.12 for a named persona).
3. THE persona SHALL be selected by name in the request. THE API SHALL hold no default persona, and SHALL reject an unknown name with `persona_not_found`.
4. THE `ask` response SHALL carry the renderable claims, the guesses, the banishments from every attempt (R4.19), the decline if any, and the Snapshot ID. It SHALL be exactly the structure the R6 UI shell renders, with no app-specific reshaping.
5. THE API SHALL surface the reason codes of R4.2 and R5 unchanged, as structured JSON errors with appropriate HTTP status codes. It SHALL NOT flatten them into free text.
6. THE API SHALL expose no route that executes, writes to or modifies the analysed code, and SHALL NOT proxy arbitrary outbound requests.
7. THE API SHALL read no secret or API key directly. The `LLMClient` of R7.3 is its only path to a provider.
8. Ingest SHALL NOT block a request beyond the configured timeout. THE design SHALL state whether ingest is synchronous with a timeout, or returns a job to poll.
9. THE API SHALL enforce the `retained` / `ephemeral` declaration of R1.15a, and SHALL default to `ephemeral` for any request originating from an end user.

---

## Resolved questions

The six questions raised in review, and the decisions taken. Recorded so the design does not reopen them.

1. **Size limit and clone timeout.** Fixed in R1.8 rather than deferred to design: 500 MB, 180 s, 50,000 files. The demo patient is 49.7 MB.

2. **Archives without git history.** Confirmed as drafted. History analyzers skip with an explicit status (R2.11), the Snapshot ID is a content hash, and `history_available = false`. Requiring a `.git` directory inside archives was rejected: it would break the upload path entirely.

3. **Licence gate.** Split by retention, see R1.15. Hard gate for retained snapshots; record-and-proceed, never cached, for ephemeral user-supplied URLs. A gate on every path would reject a judge pasting their own repository, which is the interaction carrying the Potential Impact criterion.

4. **How figures are detected.** Both mechanisms, not one. Structured figures stay primary (R4.10); the prose digit scan is added as a backstop (R4.11a) with an exemption for text inside a verified quote, which answers the dates-and-version-numbers objection. The acknowledged hole — a number written into prose passing unchecked — is the one a judge could find on camera, and the product's whole premise is that numbers never originate from the model.

5. **`todo_age` metrics.** `todo_count_in_file` added (R2.19). One extra metric, and it enables the strongest line available in the demo: this file has N markers, the oldest is M days old.

6. **The API layer.** Added as R9. The brief named six subsystems while `tech.md` specified FastAPI; the omission was in the brief. The API belongs in the skeleton because both apps need the identical surface, and duplicating it would weaken the versatility claim that the category is judged on.

---

## Watch items

Not requirements. Things to observe once the system runs.

1. **Guess escape hatch.** R4.9 permits an explicitly flagged guess to render without citations. If the generator discovers that flagging everything as a guess avoids rejection, the banishment — the signature moment of the demo — stops firing. Watch the first live runs. If it happens, cap the proportion of a response that may be guesses, or route an all-guess answer to the decline path.

2. **R6 scope.** Fifteen acceptance criteria including contrast testing, reduced-motion, and screen-reader support. The largest discretionary block in the spec; see R8.5 and R8.5b.

3. **Blame performance.** R2.19a forbids per-marker blame. Measure actual analysis time on the demo patient as soon as `todo_age` runs, and record it in `demo/patient.json` under `measured_analysis_seconds`. The patient decision rule in `demo-patient.md` depends on it.
