# The Crypt

> A skeleton that reads a real codebase and lets a haunted persona talk about it —
> **truthfully**.

Kiroween 2026 · category: **Skeleton Crew** · [hackathon](https://kiroween.devpost.com/)

**Status: in development.** Submission closes 2026-12-04 14:00 PT. This README describes the
intended system; sections marked _planned_ are not yet built.

---

## The problem

Ask a language model about a legacy codebase and it answers with confidence and invention.
It names files that do not exist, quotes lines that were never written, and produces
plausible numbers. For a system nobody alive fully understands, a confident wrong answer is
worse than no answer.

## The approach

Every factual claim a persona makes carries a citation — file, line range, and quote — which
is **verified against the analysed snapshot before it reaches the screen**. A claim that
fails is not quietly dropped. It is *banished*: struck down on screen, with the reason it
failed.

Numbers never come from the model. Days since last change, commit counts, severity, and
interest are all computed in code and handed to the persona as facts it may quote but not
calculate.

## Two apps, one skeleton

| App | What it is |
|---|---|
| **[The Medium](medium/)** | A conversational ghost of a legacy system. Interview it — "why do you break on the 31st?" — and it answers from the code, possessing the file tree as it cites. It ends by producing a resurrection plan for modernising the system. |
| **[The Debt Collector](debt-collector/)** | A menacing collector who itemises technical debt with *interest*, issues escalating notices, and offers a ranked repayment plan. The largest debts are boss fights. |

Both are thin. The work lives in [`skeleton/`](skeleton/):

```
skeleton/
  ingest/    repo -> code graph (tree-sitter) + git history
  signals/   pluggable analyzers: churn, staleness, todo age
  personas/  TOML persona configs and loader
  verify/    the citation verifier
  mcp/       MCP server exposing signals as tools
  ui-shell/  themeable React components
```

A third persona needs one TOML config, one theme, and a thin UI — and **no change under
`skeleton/`**. That constraint is the point of the category.

## Built with Kiro

`/.kiro` is committed at the root and is part of the submission:

- `steering/` — five always-on files plus one loaded on demand
- `specs/` — three specs, each with requirements, design, and tasks
- `hooks/` — command hooks for tests and the `.kiro` guard
- `settings/mcp.json` — the signals MCP server

The write-up is in [`docs/KIRO-USAGE.md`](docs/KIRO-USAGE.md).

## Running it — _planned_

```bash
uv sync
pnpm install
uv run uvicorn skeleton.api:app --reload
pnpm --filter medium dev
```

## Repo map

| Path | What |
|---|---|
| [`docs/CREDIT-BUDGET.md`](docs/CREDIT-BUDGET.md) | Kiro credit budget and model routing |
| [`docs/EXECUTION-PLAN.md`](docs/EXECUTION-PLAN.md) | Day plan to 2026-12-04 |
| [`docs/SUBMISSION-CHECKLIST.md`](docs/SUBMISSION-CHECKLIST.md) | Rules compliance |
| [`kickoff-prompts.md`](kickoff-prompts.md) | The prompts that drive the build |
| `demo/` | Cached runs and the pinned patient repo |

## Licence

MIT — see [LICENSE](LICENSE). The analysed demo repo keeps its own licence, recorded in
`demo/patient.json`.
