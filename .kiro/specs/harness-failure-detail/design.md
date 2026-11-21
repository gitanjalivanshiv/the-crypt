# Design: harness-failure-detail

`_provider_failed(r)` stays a boolean. In `_one_run`, the branch that builds the failure string becomes:

```python
if _provider_failed(answer):
    causes = dict.fromkeys(a.failure_detail or "" for a in answer.attempts)
    failure = "ProviderError: every attempt failed with generator_error: " + "; ".join(causes)
```
`dict.fromkeys` removes duplicates and keeps order. The prefix is unchanged up to the colon, so the existing text remains a prefix. After the `turn(s) failed` summary line, the console prints `  {id}: {error}` for each entry in `errors`.

The `errors` schema is unchanged, so old run files and any reader of them keep working.
