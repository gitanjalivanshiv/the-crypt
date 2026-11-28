# Video plan

Hard constraints from the Official Rules: **under 3:00**, shows the project working on the
device it was built for, uploaded to **YouTube and set to public**, no copyrighted music, in
English. Submission closes **2026-12-04 14:00 PT**.

Budget: **2:48 of content**, leaving 12s of margin. The script below is **335 words** of
narration, which paces at 118 words per minute overall — comfortable, with the fastest shot
(the close) at 150. Do not improvise past it; every second spent explaining is a second not
spent showing. Each shot's own pacing is checked, so if you cut words, cut time with them.

---

## The one thing that must land

Not "a spooky chatbot". This:

> The ghost is not trusted. Every claim it makes is checked against the real snapshot
> before you ever see it, and the ones that fail are shown to you being struck down.

Everything else — the themes, the interest calculation, the boss fights — is dressing on
that. Lead with it and close on it.

## The staged banishment

The banishment is the signature moment and **no live run has ever produced one.** Across
ten recorded runs and 46 judged claims, the model fabricated nothing: 87.0% verified, 13.0%
self-declared guesses, **zero banishments**. Waiting for one on camera is not a plan.

So stage it deliberately, and say so out loud. Feed the real verifier a citation that
cannot resolve. Verified working against the pinned setuptools snapshot with **no API key
of any kind**:

```
attempts: ['banished', 'accepted']
banishment: file_not_found — "File not found: setuptools/midnight.py"
claims:     ['Discovery is where the layout is decided.']
```

That is the full arc in one turn: it lied, the verifier caught it, it was told why, and the
retry was grounded. `tests/api/test_ask.py::test_banished_then_answered` is the same path
under test, so it is a property of the system, not a stunt.

**This is built.** `demo/banishment.py` serves the Medium on :8000 with a scripted ghost
instead of a provider:

```bash
uv run python -m demo.banishment
```

It clones the pinned patient (about 20s), then prints the UI URL with the ref already in
it. Open that, ask anything, and every turn is banished once and then answered. Confirmed
on screen: the fabricated claim struck through, a bold `BANISHED`, the reason
`File not found: setuptools/midnight.py`, the grounded claim with
`[setuptools/discovery.py:1-20]`, the snapshot ID and `Licence: MIT` beneath — and the file
tree auto-expanding to possess `discovery.py`.

It is keyed on the request rather than a call counter, because `FakeLLMClient` replays a
fixed list and raises once exhausted, which would kill a UI session after one turn.
`tests/demo/test_banishment.py` pins its retry markers to the real
`generator.render_feedback`; without that, a reworded prompt would make the harness
fabricate forever, declining every turn with no error and no banishment to film.

**Say this on camera:** "I'm feeding it a citation that doesn't exist on purpose." Framing
it as a deliberate probe of the guard is stronger than implying the model misbehaved, and
it is the truth.

## Shot list

| # | Time | On screen | Narration |
|---|---|---|---|
| 1 | 0:00–0:12 | A terminal, then the struck-through claim with its reason | Ask any model about a codebase nobody understands and it will name files that don't exist. Confident, fluent, wrong. **This** is what my project does with that. |
| 2 | 0:12–0:40 | The banishment, held still. Zoom the reason line. | The Crypt is a skeleton that reads a real repository and lets a haunted persona talk about it — truthfully. Every factual claim carries a citation: file, lines, quote. It's checked against the snapshot before it reaches the screen. I just fed it a citation that doesn't exist, on purpose. It's struck down, with the reason, and the retry is grounded. |
| 3 | 0:40–1:06 | The Medium: ask a question, citations resolve, file tree sweeps | This is The Medium — the ghost of a legacy system. It answers from the code and possesses each file as it cites it. Numbers never come from the model: commit counts, staleness, severity are all computed in code and handed over as facts it may quote but not invent. |
| 4 | 1:06–1:16 | The resurrection plan panel | Interview it long enough and it writes you a modernisation plan, every step cited. |
| 5 | 1:16–1:44 | The Debt Collector ledger, scrolling. Highlight a boss fight. | Second app, same skeleton. A collector who itemises technical debt with interest. Three hundred lines ranked out of four hundred and ninety-five findings on real setuptools. The worst are boss fights. And this one needs no API key at all — with no provider configured it still ingests, analyses and ranks. Only the prose declines. |
| 6 | 1:44–2:18 | `.kiro/specs/` tree, then a tasks.md with ticked boxes, then `git log` | All of it was built with Kiro, spec-first. Seven specs — requirements, design, tasks — a hundred and thirty-nine tasks, and a commit per task, so the history is the spec. Hooks run the tests and guard the `.kiro` folder. Five always-on steering files keep the grounding rule in every request. Signals are exposed over MCP. |
| 7 | 2:18–2:34 | `docs/KIRO-USAGE.md` on the banishment-rate section | I also measured it. Forty-six claims, eighty-seven per cent verified. One metric band failed: it never fabricated enough to banish. I left the breach in rather than make the ghost worse so a number would read better. |
| 8 | 2:34–2:48 | Two folders side by side, then the strike-through again | Two apps, one skeleton, and a test suite that fails if either app reaches inside it. A third persona needs a config, a theme, and a thin UI — and no change to the bones. |

## Commands, in recording order

Have all of this running and warm **before** you hit record. The setuptools clone takes
about 20 seconds and you do not want it on camera.

```bash
cd skeleton/ui-shell && pnpm install && pnpm build
```

The scripted Medium, for shots 2 to 4 (no key needed):

```bash
uv run python -m demo.banishment
```

```bash
cd medium/ui && pnpm dev
```

```bash
CRYPT_STORE=crypt-store uv run python -m debt-collector.main
```

```bash
cd debt-collector/ui && pnpm dev
```

The Medium, if quota is alive:

```bash
GEMINI_API_KEY=... CRYPT_STORE=crypt-store uv run python -m medium.main
```

Check quota before you plan on it:

```bash
./scripts/gemini-quota.sh
```

## Fallbacks

| If | Then |
|---|---|
| Quota is alive | Record shots 3 and 4 live. Do the interview once off-camera first so you know the answers resolve; a 429 mid-take costs you a retake. |
| Quota is dead | Shots 3 and 4 run on the scripted harness, same as shot 2. Say "scripted reply, real verifier" once, on camera. Do not hide it — a judge who spots it unannounced discounts everything else. |
| Short on time | Cut shot 4 (the plan panel, 10s) and tighten shot 5 to 20s. Never cut shot 2 or shot 6: one is the thesis, the other is the category. |
| A take runs long | Shot 6's narration compresses to "Seven specs, a commit per task, hooks, steering, MCP." Saves 12s. |

## Recording notes

- Record at 1920×1080 or higher and **zoom the editor and terminal fonts before you start.**
  Reason codes and cited line numbers are the whole point and they are small.
- The seance theme emits `send` 330 Hz, `receive` 247 Hz and `banish` 110 Hz sawtooth for
  300 ms. Keep the system audio in the capture — the banish tone does real work and costs
  you nothing in licensing. No music track at all is safer than any music track.
- The possession sweep steps every 1200 ms and stops on the last cited file, so give shot 3
  at least four seconds of stillness after the answer lands or the sweep gets clipped.
- Reduced-motion is respected: the sweep does not animate. If your OS has it on, the best
  visual in the project silently disappears. Check it before recording.
- Shot 1 and shot 8 are the same frame. Returning to it is what makes a 3-minute video feel
  finished rather than merely stopped.

## Checklist before upload

- [ ] Runtime under 3:00.
- [ ] Both apps appear, and the shared skeleton is named as the point.
- [ ] A real banishment is on screen, with its reason legible.
- [ ] Any scripted reply is disclosed out loud.
- [ ] No third-party logos, trademarks or music.
- [ ] Uploaded to YouTube, **public** — not unlisted.
- [ ] URL pasted into the Devpost form, and the form **submitted**, not saved as a draft.
