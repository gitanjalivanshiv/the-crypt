# Video plan

Hard constraints from the Official Rules: **under 3:00**, shows the project working on the
device it was built for, uploaded to **YouTube and set to public**, no copyrighted music, in
English. Submission closes **2026-12-04 14:00 PT**.

Budget: **2:48 of content**, leaving 12s of margin. The script below is **319 words** of
narration, pacing at 114 words per minute overall, with every shot between 90 and 135 —
unhurried enough to sound deliberate rather than breathless, which matters for this tone. Do not improvise past it; every second spent explaining is a second not
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

Tone: a séance held over a dying codebase, run by someone who does not trust the dead. Dry,
not camp. The jokes land because the engineering underneath is serious — never the other
way round. Say "banished" like it is a technical term, because it is.

| # | Time | On screen | Narration |
|---|---|---|---|
| 1 | 0:00–0:14 | Terminal, then the struck-through claim | Ask a machine about a codebase no living developer understands, and it will lie to you beautifully. It will name files that were never written. Watch what happens to one here. |
| 2 | 0:14–0:42 | The banishment, held still. Zoom the reason line. | The Crypt holds a séance over a real repository. Every claim the ghost makes drags a citation behind it — file, lines, quote — checked against the corpse before you ever see it. I have just fed it a file that does not exist. The verifier catches the lie in mid-air and strikes it down. We call that a banishment. Then it tries again, grounded. |
| 3 | 0:42–1:08 | Ask a question; citations resolve; the tree sweeps | Meet the Medium, the ghost of a legacy system, possessing one file at a time as it cites. It cannot invent a number. Commit counts, decay, severity — all computed in cold code and handed to the dead, who may quote them but never conjure them. |
| 4 | 1:08–1:16 | The resurrection plan panel | Keep asking and it writes you a resurrection plan. Every step cited. |
| 5 | 1:16–1:44 | The ledger, scrolling. Stop on a boss fight. | Second app, same skeleton. The Debt Collector reads your technical debt as a ledger, with interest. Three hundred debts ranked out of four hundred and ninety-five findings in real setuptools. The worst are boss fights. It needs no key and no model: the arithmetic of decay is entirely ours. |
| 6 | 1:44–2:18 | `.kiro/specs/`, a ticked tasks.md, then `git log` | All of it raised with Kiro, spec first. Seven specs — requirements, design, tasks — a hundred and thirty-nine of them, and one commit per task, so the git history is the grimoire. Hooks run the tests and guard the dot-kiro folder. Steering keeps the grounding rule in every request. Signals served over MCP. |
| 7 | 2:18–2:34 | `docs/KIRO-USAGE.md`, the measured section | I measured the haunting. Forty-six claims, eighty-seven per cent verified. One metric failed outright: the ghost never lied often enough to get banished. I left the failure in the report rather than teach it to lie. |
| 8 | 2:34–2:48 | Two folders side by side, then the strike-through again | Two apps. One skeleton. A test suite that screams if either reaches into the bones. A third haunting needs a config, a theme and a thin UI — and nothing underneath moves. |

## The script, to read aloud

Record this as one pass if you can; the pauses between shots are where you breathe.

> Ask a machine about a codebase no living developer understands, and it will lie to you
> beautifully. It will name files that were never written. Watch what happens to one here.
>
> The Crypt holds a séance over a real repository. Every claim the ghost makes drags a
> citation behind it — file, lines, quote — checked against the corpse before you ever see
> it. **I have just fed it a file that does not exist.** The verifier catches the lie in
> mid-air and strikes it down. We call that a banishment. Then it tries again, grounded.
>
> Meet the Medium, the ghost of a legacy system, possessing one file at a time as it cites.
> It cannot invent a number. Commit counts, decay, severity — all computed in cold code and
> handed to the dead, who may quote them but never conjure them.
>
> Keep asking and it writes you a resurrection plan. Every step cited.
>
> Second app, same skeleton. The Debt Collector reads your technical debt as a ledger, with
> interest. Three hundred debts ranked out of four hundred and ninety-five findings in real
> setuptools. The worst are boss fights. It needs no key and no model: the arithmetic of
> decay is entirely ours.
>
> All of it raised with Kiro, spec first. Seven specs — requirements, design, tasks — a
> hundred and thirty-nine of them, and one commit per task, so the git history is the
> grimoire. Hooks run the tests and guard the dot-kiro folder. Steering keeps the grounding
> rule in every request. Signals served over MCP.
>
> I measured the haunting. Forty-six claims, eighty-seven per cent verified. One metric
> failed outright: the ghost never lied often enough to get banished. I left the failure in
> the report rather than teach it to lie.
>
> Two apps. One skeleton. A test suite that screams if either reaches into the bones. A
> third haunting needs a config, a theme and a thin UI — and nothing underneath moves.

**The bolded line is not decoration.** It is the disclosure, and it has to be audible. Also
put `scripted reply · live verifier` on screen during shot 2. Saying it plainly costs you
nothing and buys the rest of the video its credibility; a judge who works out that the
reply was scripted *after* you implied otherwise discounts everything else.

Two lines carry the whole video, so land them: *"checked against the corpse before you ever
see it"* and *"I left the failure in the report rather than teach it to lie."* The second is
the one that distinguishes this from every other hackathon submission — it is an admission,
and nobody else will make one.

## Bringing it up

Every command, with the output each one actually prints, is in
[DEMO-RUNBOOK.md](DEMO-RUNBOOK.md) — including the pre-record checks that are easy to
forget, chiefly turning reduced motion OFF, without which the possession sweep does not
animate at all.

Have all four terminals up and warm **before** you hit record. `demo.banishment` re-clones
setuptools on every start, so bring it up once and leave it.

## Fallbacks

| If | Then |
|---|---|
| Quota is alive | Record shots 3 and 4 live. Do the interview once off-camera first so you know the answers resolve; a 429 mid-take costs you a retake. |
| Quota is dead | Shots 3 and 4 run on the scripted harness, same as shot 2. Say "scripted reply, real verifier" once, on camera. Do not hide it — a judge who spots it unannounced discounts everything else. |
| Short on time | Cut shot 4 (the plan panel, 8s) and tighten shot 5 to 20s. Never cut shot 2 or shot 6: one is the thesis, the other is the category. |
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
