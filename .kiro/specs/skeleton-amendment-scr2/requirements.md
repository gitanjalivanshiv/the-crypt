# Requirements: skeleton-amendment-scr2

## Introduction

Skeleton change request SCR-2, filed by the Medium spec (`.kiro/specs/medium/design.md` §7), is taken pre-emptively, before Medium task 1.1.

Today `skeleton/api/app.py` builds `VerifyConfig()` inline inside the `ask` route. `VerifyConfig.allowed_numbers` is therefore always the empty frozenset and no caller can set it. `ApiConfig` has six fields and none is `verify`.

Why now rather than on breach: the digit scan is strict by design and `allowed_numbers` is empty, so `unbacked_number` over-rejection is the most likely band breach in the Medium's harness. Reactively, it would stall Medium task 5.2 with the UI group blocked behind gate 5.3, and fixing it then needs this same amendment, days later. The amendment defaults to exactly today's behaviour, so it changes nothing the harness measures.

## Scope

One change: make `VerifyConfig` injectable through `ApiConfig`.

Out of scope, explicitly:

- SCR-1, SCR-3 and SCR-4. They stay reactive as the Medium spec has them.
- Any other `ApiConfig` field.
- Any change under `skeleton/verify/`.
- Any change to `GROUNDING`.
- Any new route.
- Threading `VerifyConfig` anywhere other than the `ask` route.
- Renaming `run_grounded_turn`'s `cfg` parameter or any existing `cfg` variable.

## Requirements

### R1. Injectable verify configuration

**User story:** As a persona author, I want to set `VerifyConfig` when I build the app, so that numbers a persona legitimately says can be allowed without editing the skeleton.

Acceptance criteria:

1. `ApiConfig` has a field `verify: VerifyConfig` whose default equals `VerifyConfig()` (an empty `allowed_numbers`).
2. The `ask` route passes the configured `ApiConfig.verify` to `run_grounded_turn`, and no longer constructs a `VerifyConfig` itself.
3. When no caller sets `verify`, behaviour is identical to before. Every existing test passes unchanged.
4. `ApiConfig` has exactly seven fields. The six existing fields keep their names, types and defaults.

### R2. Proof of the change

Acceptance criteria:

1. One test builds an app with `ApiConfig(verify=VerifyConfig(allowed_numbers=frozenset({"42"})))` and asks a question whose scripted claim has a bare `42` in its prose. The response is `answered` and contains that claim.
2. The same test builds an app with the default `ApiConfig()` and the same scripted claim. The claim is banished with reason `unbacked_number`.
3. The test uses `FakeLLMClient`. It makes no network call.

### R3. Containment

Acceptance criteria:

1. No file under `skeleton/verify/` changes. `./scripts/check-verify.sh` passes with its 100% line and branch gate.
2. All four import-linter contracts pass.
3. The full suite stays green: 598 Python tests plus the one added here, and 74 UI tests.
4. The task list has at most three tasks. A longer list means the scope has drifted and the spec is cut before any task runs.
