---
inclusion: always
---

# Repo structure

```
the-crypt/
  .kiro/
    steering/        product, tech, structure, grounding-rule, credit-policy  (always)
                     demo-patient  (manual: loaded with #demo-patient)
    specs/           skeleton/ , medium/ , debt-collector/
    hooks/           command hooks only — see credit-policy.md
    settings/mcp.json
  skeleton/          shared core, imported by both apps
    ingest/          clone or unpack a repo -> code graph (files, symbols, imports)
    signals/         pluggable analyzers, one module per analyzer
    personas/        TOML loader + base prompt assembly
    verify/          citation verification (the grounding rule, in code)
    mcp/             MCP server exposing signals as tools
    ui-shell/        themeable React components (CRT terminal, file tree, chat, meter)
  medium/            APP 1 — The Medium
  debt-collector/    APP 2 — The Debt Collector
  demo/              cached runs + patient repo reference
  docs/              budget, plan, checklist, Kiro write-up
  scripts/           guard scripts (zero-credit hook targets)
  LICENSE  README.md  .gitignore
```

## Rules

1. Apps depend on `skeleton/`. **`skeleton/` never imports from an app.** A lint rule
   enforces this; it is the proof that the skeleton is real.
2. Adding a persona or app must require only: one TOML persona config, one theme, one thin
   UI entry. Zero edits under `skeleton/`. If a change forces a skeleton edit, that is a
   skeleton design bug — fix the skeleton, do not special-case the app.
3. `medium/` and `debt-collector/` stay **top-level**, not nested under `apps/`. The rules
   require two separate application folders; top-level removes any doubt for a judge
   scanning the repository root.
4. Every analyzer is one file under `skeleton/signals/` implementing the same protocol, and
   is registered in `skeleton/signals/__init__.py`. No analyzer knows about a persona.
