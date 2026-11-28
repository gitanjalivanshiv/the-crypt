# Demo runbook

Exact steps to bring both apps up, confirm they work, and record. Every command here has
been run; the expected output is what it actually printed, not what it ought to print.

Nothing in this runbook needs an API key.

---

## Once, before anything else

Both UIs consume the shell as `link:../../skeleton/ui-shell`, and it resolves to `dist/`,
which is not committed. Build it first or both UIs fail to resolve the module.

```bash
cd skeleton/ui-shell && pnpm install && pnpm build
```

Expect `dist/index.js` and `dist/style.css` to be written. Then, from the repo root:

```bash
uv sync
```

---

## Terminal 1 — the Medium (scripted ghost, no key)

```bash
uv run python -m demo.banishment
```

First line is `cloning https://github.com/pypa/setuptools.git at 049ae8e30835 (about 20s)...`
— **this happens on every start**, so bring it up once and leave it running. When it is
ready it prints:

```
  ready. the ghost is scripted; the verifier is not.
  UI    http://127.0.0.1:5173/?ref=049ae8e3083514378aedb352a2017fbc306bd126
  API   http://127.0.0.1:8000/snapshots/049ae8e3083514378aedb352a2017fbc306bd126
```

## Terminal 2 — the Medium's UI

```bash
cd medium/ui && pnpm install && pnpm dev
```

Expect `Local: http://localhost:5173/`.

## Terminal 3 — the Debt Collector (no key, reuses the clone)

Point it at the store the first terminal just built, so it does not clone setuptools again:

```bash
CRYPT_STORE=demo/crypt-store uv run python -m debt-collector.main
```

Expect, as the first line, `collector starting without a model provider: environment
variable GEMINI_API_KEY is not set`. **That line is the demo, not a warning.** It then
serves on `http://127.0.0.1:8001`.

## Terminal 4 — the Debt Collector's UI

```bash
cd debt-collector/ui && pnpm install && pnpm dev
```

Vite takes the next free port, so with the Medium already on 5173 this prints
`Local: http://localhost:5174/`. **Read the port it prints** rather than assuming.

---

## Test it

### 1. The Medium, bare URL

Open **http://localhost:5173/** with no query string. You should land on the séance: the
setuptools file tree on the left, "The Medium", an "Ask the spirit" box, and a
"Resurrection plan" panel. If you see `missing_ref`, the UI was built before the default
ref landed — rebuild the shell and restart vite.

### 2. The banishment

Type any question and press Enter. Every turn gives the same shape:

- the verified claim, cited `[setuptools/discovery.py:1-20]`
- below it, in bold, **BANISHED**, with the fabricated claim struck through
- the reason: `File not found: setuptools/midnight.py`
- the snapshot id and `Licence: MIT` underneath

The file tree expands and highlights `discovery.py` — that is the possession sweep. It
steps every 1.2s and stops on the last cited file.

### 3. The Debt Collector, bare URL

Open the port from terminal 4 (likely **http://localhost:5174/**). Expect a ranked ledger:
`Escalation level: final`, a coverage note reading `churn: 100 of 136 findings listed;
staleness: 100 of 240; todo_age: 100 of 119`, and rows marked **LARGEST DEBT** — those are
the boss fights, three of them. Rank 1 is `setuptools/discovery.py:1-38`.

It is cream and serif on purpose: the `ledger` theme is ink-on-paper, deliberately set
against the Medium's phosphor. It is not an unstyled page.

### 4. The notice declines, and that is the point

Press **Serve notice**. With no provider it answers `200` with the collector's own line —
*"The books are closed to that inquiry."* A missing model is a decline, never a crash and
never a guess.

### 5. Without the browser, if you want to be sure

```bash
curl -s http://127.0.0.1:8001/collector/snapshots/049ae8e3083514378aedb352a2017fbc306bd126/ledger | head -c 300
```

---

## Before you hit record

- [ ] **Turn off reduced motion.** macOS: System Settings → Accessibility → Display →
      Reduce Motion, off. With it on, the possession sweep does not animate and the best
      visual in the project silently vanishes.
- [ ] **Zoom the terminal and browser fonts.** Reason codes and cited line numbers are the
      whole point, and they are small.
- [ ] **Keep system audio in the capture.** The séance theme plays `send` 330 Hz, `receive`
      247 Hz and `banish` 110 Hz sawtooth. The banish tone does real work. Add no music —
      no track at all is safer than any track.
- [ ] Ask one question off-camera first, so the first take is not the first run.
- [ ] Close any tab showing `missing_ref` or an old build.

## Afterwards

The snapshot store is gitignored but it is 58 MB, and it is written read-only, so a plain
`rm -rf` fails:

```bash
chmod -R u+w demo/crypt-store && rm -rf demo/crypt-store
```
