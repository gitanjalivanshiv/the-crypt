---
inclusion: always
---

# Tech decisions

Decided. Do not reopen without editing this file first.

## Stack

| Layer | Choice | Note |
|---|---|---|
| Backend | Python 3.12 + FastAPI | one service, no microservices |
| Parsing | `tree-sitter` + `tree-sitter-languages` | **Python grammar only for v1** |
| Git facts | `pygit2` or `git` subprocess | churn, staleness, author counts |
| Frontend | TypeScript + React 18 + Vite | one themeable shell, two themes |
| Tests | `pytest` + `hypothesis` | Hypothesis is required for the verifier |
| Package mgmt | `uv` (Python), `pnpm` (JS) | fast, lockfiles committed |
| Persona | TOML config, not code | voice, goals, tools, example lines |
| LLM access | one `LLMClient` interface | provider swappable behind it |

**Scope discipline:** one language grammar (Python) ships in v1. Multi-language is a
`SUPPORTED_GRAMMARS` list and a follow-up, not v1 work. Adding grammars late is the classic
way this build overruns.

## Signals (pluggable analyzers)

Every analyzer returns findings of the same shape:

```python
Finding(analyzer, file, line_start, line_end, evidence, severity, metrics)
```

- `evidence` is a verbatim slice of the file, never a paraphrase.
- `severity` is 0.0–1.0, computed by the analyzer, never by the model.
- `metrics` carries the raw numbers the persona is allowed to quote.

v1 analyzers, in build order: `churn` → `staleness` → `todo_age` → `complexity` →
`dependency_age` → `dead_code`. The first three carry the demo; the last three are
nice-to-have and are cut first if time runs short.

## Runtime LLM budget — separate from Kiro credits

Kiro credits pay for **building**. They do not pay for the deployed demo. The demo bills a
separate provider account and must stay free and unrestricted for judges until
**2027-01-29 13:00 PT**, which is after Kiro credits expire on 2026-12-31.

- Provider: **Anthropic API** direct (simplest from India; no Bedrock region gating).
  Amazon Bedrock only if existing AWS credits cover the judging window.
- Hard monthly spend cap set at the provider, plus per-session and per-IP rate limits.
- **Pre-cached demo runs on the patient repo are mandatory.** If the live budget is gone, a
  judge still gets a complete, labelled run. A dead demo scores zero on Presentation.

## Hard constraints

- Public GitHub repo at `github.com/gitanjalivanshiv/the-crypt`, MIT licence, visible in the
  About panel.
- `/.kiro` is committed at the repo root and **must never** appear in `.gitignore`.
- Two separate top-level application folders (`medium/`, `debt-collector/`) — a
  Skeleton Crew submission requirement.
- English only in all materials.
- Only analyse permissively licensed open-source repos; honour their licences.
