# The Crypt

> A skeleton that reads a real codebase and lets a haunted persona talk about it —
> **truthfully**.

Kiroween 2026 · category: **Skeleton Crew** · [hackathon](https://kiroween.devpost.com/)

**Status: built.** Seven specs, 141 task checkboxes, 139 ticked — both open ones are live
runs against a real provider, blocked on API quota rather than unfinished code. CI runs ten
jobs on every push: 853 Python tests, 163 UI tests across three packages, 100% line *and*
branch coverage on the verifier, and seven import-linter contracts.

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

The verifier is the load-bearing part, so it is the most heavily tested: 244 tests, 100%
line and branch coverage, and `pragma: no cover` is banned under `skeleton/verify/`.

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
`skeleton/`**. That constraint is the point of the category, and
`tests/independence/` enforces it rather than trusting it.

## Running it

```bash
uv sync
```

The **Debt Collector needs no API key at all.** With no provider configured it still
ingests, analyses, ranks and serves — only the persona's prose declines:

```bash
CRYPT_STORE=crypt-store uv run python -m debt-collector.main   # http://127.0.0.1:8001
```

```bash
curl -X POST http://127.0.0.1:8001/snapshots -H 'content-type: application/json' \
  -d '{"url":"https://github.com/pypa/setuptools.git","sha":"049ae8e3083514378aedb352a2017fbc306bd126","intent":"ephemeral"}'
```

That returns a `ref`. Then `GET /collector/snapshots/{ref}/ledger` answers `200` with a
ranked ledger — on the pinned demo snapshot, 300 lines drawn from 495 matching findings
(churn 136, staleness 240, todo age 119), principal 826.0, interest 450.4, escalation
`final`, boss fights flagged. `POST /collector/snapshots/{ref}/notice` also answers `200`,
with `status: "declined"` and the persona's own line — *"The books are closed to that
inquiry."* — because a missing provider is a decline, never a crash and never a guess.

The **Medium** needs a provider, since its whole surface is conversation:

```bash
GEMINI_API_KEY=... CRYPT_STORE=crypt-store uv run python -m medium.main   # http://127.0.0.1:8000
```

`MEDIUM_PROVIDER` and `MEDIUM_MODEL` select the provider and model; the default is Gemini.

Either UI needs the shell built first — it is consumed as `link:../../skeleton/ui-shell`
and resolves to `dist/`, which is not committed:

```bash
cd skeleton/ui-shell && pnpm install && pnpm build
```

```bash
cd medium/ui && pnpm install && pnpm dev          # proxies to :8000
```

```bash
cd debt-collector/ui && pnpm install && pnpm dev  # proxies to :8001
```

## Built with Kiro

`/.kiro` is committed at the root and is part of the submission:

- `steering/` — five always-on files plus one loaded on demand
- `specs/` — seven specs, each with requirements, design, and tasks
- `hooks/` — command hooks for tests and the `.kiro` guard
- `settings/mcp.json` — the signals MCP server

Every hook is a `command` hook rather than an agent hook, which is why the whole build cost
a fraction of the credits budgeted for it. The write-up is in
[`docs/KIRO-USAGE.md`](docs/KIRO-USAGE.md), including the measured banishment rate and the
one metric band that was breached and deliberately not tuned.

## Repo map

| Path | What |
|---|---|
| [`docs/KIRO-USAGE.md`](docs/KIRO-USAGE.md) | How Kiro drove the build, and what was measured |
| [`docs/CREDIT-BUDGET.md`](docs/CREDIT-BUDGET.md) | Kiro credit budget and model routing |
| [`docs/EXECUTION-PLAN.md`](docs/EXECUTION-PLAN.md) | Day plan to 2026-12-04 |
| [`docs/SUBMISSION-CHECKLIST.md`](docs/SUBMISSION-CHECKLIST.md) | Rules compliance |
| [`kickoff-prompts.md`](kickoff-prompts.md) | The prompts that drive the build |
| `demo/` | Cached runs and the pinned patient repo |

## Licence

MIT — see [LICENSE](LICENSE). The analysed demo repo keeps its own licence, recorded in
`demo/patient.json`.
