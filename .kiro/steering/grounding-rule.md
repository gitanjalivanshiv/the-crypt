---
inclusion: always
---

# Grounding rule: the ghost cannot lie

Every factual claim a persona makes about the analysed codebase carries a citation:

```json
{ "file": "path/from/repo/root", "line_start": 12, "line_end": 30, "quote": "..." }
```

## Rules

1. A claim with no citation is **not rendered as fact**. The persona either attaches a
   verified citation or marks the sentence as an explicit guess ("I suspect, but the bones
   are quiet here").
2. A citation is valid only if the file exists in the analysed snapshot **and**
   `1 <= line_start <= line_end <= file_line_count`.
3. If `quote` is present it must match the file bytes at those lines exactly, after
   normalising trailing whitespace and line endings. Nothing else is normalised.
4. **Numbers come from the signals layer, never from the model.** Days since change, commit
   counts, severity, complexity, interest, totals — all read from `Finding.metrics`. The
   model may not add, average, or round. If a number is not in `metrics`, it may not be
   said.
5. Verification runs against the **analysed snapshot** (a pinned commit SHA), not against
   the live upstream repo. Record the SHA in every response payload.
6. On failure: reject the response and regenerate **once**. On a second failure, the persona
   declines in character ("The spirits are silent on that"). Never regenerate more than
   once — see `credit-policy.md`.
7. A rejected claim is surfaced in the UI as a **banishment**: the claim is shown struck
   through with the reason it failed. This is the demo's signature moment; it is never
   silently swallowed.

## Required tests

- **Property-based (Hypothesis), mandatory.** For any generated answer, every citation
  resolves to a real file with in-range lines, and every quote matches the source bytes.
- **Fuzz the verifier** with fabricated paths, path traversal (`../`), symlinks,
  out-of-range and inverted line ranges, off-by-one ranges, altered quotes, unicode and
  CRLF variants, and empty files. Every one must be rejected.
- **The verifier is the one component that must have no untested branch.** If time is short,
  cut an analyzer, never a verifier test.
