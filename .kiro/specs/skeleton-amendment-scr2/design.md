# Design: skeleton-amendment-scr2

## Overview

`ApiConfig` (frozen pydantic model in `skeleton/api/app.py`) gains one field. The `ask` closure reads it instead of building a fresh `VerifyConfig()`.

`VerifyConfig` is already imported in `app.py` from `skeleton.verify.models`, and `skeleton.api` already depends on `skeleton.verify`, so no new import edge is created and no import-linter contract is affected.

## Change 1: `ApiConfig.verify`

```python
class ApiConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    allow_retained: bool = False
    ephemeral_ttl_s: int = 3600
    max_concurrent_ingests: int = 2
    allowed_hosts: frozenset[str] | None = None
    limits: IngestLimits = IngestLimits()
    ingest_timeout_s: float = 300.0
    verify: VerifyConfig = VerifyConfig()
```

The default follows the existing pattern (`limits: IngestLimits = IngestLimits()`). `VerifyConfig` is a frozen model with an empty frozenset default, so a shared default instance is safe and equals what `ask` builds today (R1.1, R1.3).

## Change 2: the `ask` route

In `create_app`, `cfg` is the `ApiConfig` (`cfg = cfg or ApiConfig()`), and `ask` closes over it. The call becomes:

```python
return await run_grounded_turn(
    snap, generator, decline_line=persona.decline_line, cfg=cfg.verify
)
```

`cfg=cfg.verify` reads oddly because `run_grounded_turn`'s keyword is also `cfg`. It is correct: the keyword is the callee's parameter name and the value is the closure's `ApiConfig`. Neither is renamed. No local alias is added, because the call is one line and the alias would add a name for no gain.

## Change 3: the test

File: `tests/api/test_ask.py`, reusing its `store`, `persona_dir` fixtures and `_reply` helper. The existing `_ask` helper hard-codes `ApiConfig()`, so it gets an optional `cfg` parameter defaulting to `ApiConfig()` (a one-line change, existing callers unaffected).

Scripted claim: prose `"It has 42 lines."` with citation `a.py` lines 1 to 1. Digit-scan allowance for the citation covers `1` only, so `42` is the unbacked token.

- Default config: script two replies of the claim (the flow retries once). Expect a `declined` turn whose first banishment reason is `unbacked_number`.
- `verify=VerifyConfig(allowed_numbers=frozenset({"42"}))`: script one reply. Expect `answered` with the claim text, and no banishments.

Both use `FakeLLMClient` through the existing helper.

## Why this cannot touch `skeleton/verify/`

`run_grounded_turn` already accepts `cfg: VerifyConfig` and `verify_claim` already reads `cfg.allowed_numbers` (`skeleton/verify/claim.py`). The only missing piece is the caller supplying a non-default value. All coverage-gated code is already reached by existing tests.

## Risks

- Import-linter: unchanged edges, so none expected. Verified by running the linter in the final task.
- OpenAPI/TS types: `ApiConfig` is not an HTTP model, so `types.generated.ts` does not change. Verified by the UI suite staying green.
