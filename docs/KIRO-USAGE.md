# How Kiro was used

Working draft for the Devpost write-up. Fill each section **as the work happens**, not from
memory on Dec 2. Keep concrete specifics: file paths, prompts, what failed.

Judges score Technological Implementation (20%) largely on this document. "We used specs and
hooks" scores nothing; "this hook caught this class of bug, here is the file" scores.

---

## Kiro surfaces — IDE / CLI / Web / Crew

Which were used, for what, and how they differed in practice.

> _TODO_

## Spec-driven development

How the three specs were structured, what was edited by hand before approving, where the
spec caught a design problem that vibe coding would have discovered only in code, and where
the spec got in the way.

> _TODO_

## Steering

Six files. Five always-on and deliberately lean, because always-on steering is injected into
every request; `demo-patient.md` is `inclusion: manual` and pulled in with `#demo-patient`
only when the patient is under discussion. Note which steering file changed Kiro's output
most visibly.

> _TODO_

## Agent hooks

Every hook is a `command` hook. Record the workflows automated and the cost reasoning —
command hooks run shell commands for zero credits, where agent hooks bill per firing.

> _TODO_

## MCP

The signals MCP server exposes analyzer findings as tools, so the persona *queries* facts
instead of guessing them. This is the mechanism behind the grounding rule. Record what
became possible that would otherwise have been impractical.

> _TODO_

## Property-based testing

Hypothesis against the citation verifier. Record the specific bugs PBT found that
example-based unit tests missed — fabricated paths, inverted ranges, off-by-one line ends,
CRLF and unicode mismatches.

> _TODO_

## Custom agents and Kiro powers

Which were used, in which surface, and what they changed.

> _TODO_

## Credit discipline

4,000 credits, no top-up. Model routing (Auto by default, Haiku 5.5 at 0.06x for mechanical
work, Opus 5.5 capped at 15 prompts), command hooks over agent hooks, one task at a time
rather than concurrent waves. Final actuals from `docs/CREDIT-BUDGET.md`.

> _TODO_
