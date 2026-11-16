# Hooks

Every hook here is a **`command`** hook.

A `command` action runs a shell command and costs **zero Kiro credits**. An `agent` action
injects a prompt into the conversation and costs **at least one credit every time it
fires**. A `PostFileSave` agent hook over 18 days of normal editing can exceed the entire
4,000-credit hackathon allotment on test runs that `pytest` does for free.

No hook in this project needs to write code, so no hook in this project is an agent hook.
See `.kiro/steering/credit-policy.md`.

| Hook | Fires on | Runs |
|---|---|---|
| `test-signals-on-save` | saving `skeleton/signals/**.py` | analyzer tests |
| `verify-on-persona-change` | saving any persona TOML | citation verifier tests |
| `guard-kiro-committed` | saving `.gitignore` | the disqualification guard |

The `.kiro` guard also runs as a git `pre-commit` hook and in CI, because a Kiro hook fires
only while Kiro is open. Install it with `./scripts/install-git-hooks.sh`.

Trigger names and JSON shape follow Kiro's current hooks documentation; verify against your
installed Kiro version before relying on them.
