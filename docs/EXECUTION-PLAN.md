# Execution plan — 2026-11-16 to 2026-12-04

**Hard stop: 2026-12-04 14:00 PT = 2026-12-05 03:30 IST.** No extensions; late submissions
are not accepted.

For an India-based team that cutoff lands in the small hours. **Treat the evening of
2026-12-03 IST as the real deadline** and keep 2026-12-04 IST as pure contingency.

Only work created inside the submission period (from 2026-10-30) is eligible. This repo
starts now, so that holds — but nothing may be copied in from earlier projects without
disclosure.

---

## Day plan

| Dates (IST) | Phase | Done when |
|---|---|---|
| **Nov 16** | Setup | Repo public on GitHub with MIT licence visible in About; `.kiro/` committed; credits redeemed; patient repo chosen and pinned; provider account created with spend cap |
| **Nov 17–18** | Skeleton spec | `.kiro/specs/skeleton/` has requirements, design, tasks — reviewed and edited by hand, not accepted as generated |
| **Nov 19–23** | Skeleton build | ingest → signals (3 analyzers) → verify → persona loader → MCP server, each committed separately, Hypothesis tests green |
| **Nov 24–26** | The Medium | Interview loop works end to end against the patient; file tree highlights on cite; resurrection plan emits |
| **Nov 27–29** | The Debt Collector | Debt itemisation with interest, escalating notices, debt meter, ranked repayment plan |
| **Nov 30–Dec 1** | Polish + deploy | Both apps live on public URLs; cached demo runs committed; banishment moment visibly working |
| **Dec 2** | Presentation | Video recorded and uploaded to YouTube (public, under 3:00); Kiro write-up finished; blog post published; social post up |
| **Dec 3** | Submit | Devpost submission complete and **submitted**, not drafted |
| **Dec 4** | Contingency | Spare |

Analyzers 4–6 (`complexity`, `dependency_age`, `dead_code`) are explicitly optional. Cut
them without discussion if Nov 23 arrives with the skeleton incomplete.

---

## Day one checklist (Nov 16)

1. **Redeem the credit codes.** Unredeemed codes expire on 2026-12-04 and are not replaced.
2. Create the repo:
   ```
   gh repo create gitanjalivanshiv/the-crypt --public \
     --description "The Crypt — a skeleton that reads a real codebase and lets a haunted persona talk about it truthfully. Kiroween 2026, Skeleton Crew." \
     --license mit
   ```
3. Confirm **MIT appears in the GitHub About panel**. The rules require the licence to be
   detectable there, not merely present as a file.
4. Commit `.kiro/` and confirm `.gitignore` does **not** mention `.kiro` — this is an
   explicit disqualification risk. `scripts/check-kiro-committed.sh` enforces it.
5. Choose the patient repo per `#demo-patient`, pin its SHA into `demo/patient.json`.
6. Confirm whether anyone on the team registered for **Kiroween 2025** — if so, the Best
   Ghost of Kiroween Past bonus ($2,000) costs one checkbox.

---

## Bonus prizes worth claiming

Each is independent of the category prize; a submission can win one category prize plus any
number of bonuses.

| Bonus | Cost to claim | Worth it? |
|---|---|---|
| **Best Demo** ($1,000) | Nothing — all submissions considered | Automatic. Requires top-10% overall plus the best Presentation score, so the video is doing double duty |
| **Bonus Blog Prize** (2,000 Kiro credits, 100 winners) | ~2 hours writing | **Yes.** Must mention it is written for the Kiroween 2026 hackathon, published to a third-party platform during the submission period |
| **Social Blitz** (3-month Pro+, 5 winners) | ~20 minutes | Yes. `#KiroweenHackathon26` must be the **first thing in the post**, before any other content |
| **Best Ghost of Kiroween Past** ($2,000) | One checkbox, if eligible | Yes if anyone registered in 2025 |
| **Best Student Project** ($1,500 + Pro Max, per category) | LinkedIn, student email, year, degree, school for **every** member | Only if all members are students |
| **Best Startup Project** ($10,000) | Founder confirmation, LinkedIn, startup site | Only if genuinely applicable |
| **Best Kiro Crew App** ($1,000) | A **separate** new GitHub repo containing a Kiro Crew app | Stretch goal. Only after both apps are deployed — do not let it eat skeleton time |

---

## Mapping the work to the judging criteria

Five equally weighted criteria, 10 points each.

| Criterion | What wins it here | Risk |
|---|---|---|
| **Potential Impact** | "Would someone use this?" — the honest answer is a real developer pointing it at a real repo and getting citations they can click | Reads as a toy if the only repo it ever analyses is the demo patient. Let judges paste their own URL |
| **Technological Implementation** | Specs, command hooks, five steering files, an MCP server, property-based tests, custom agents, Kiro powers — and a write-up that explains *why* each was used | Breadth without depth. Three deeply used features beat eight name-dropped ones |
| **Design** | "A complete, coherent product experience, not just a technical proof of concept" — two themes, consistent CRT language, sound, the banishment animation | Spooky styling bolted onto a bare React form |
| **Innovation/Idea** | Verified citation as a *mechanic*, and rejection shown on screen rather than hidden | Chat-over-your-codebase is crowded. The banishment is the thing that is not already on the market |
| **Presentation** | Under three minutes, project working end to end on the device it was built for, problem stated before the demo | Spending 90 seconds on atmosphere and never showing it working |

---

## Video plan (under 3:00, judges need not watch past it)

| Time | Content |
|---|---|
| 0:00–0:20 | The problem, stated plainly: nobody knows why the legacy system breaks, and asking an LLM gets confident fiction |
| 0:20–1:10 | The Medium: ask a question, watch the file tree possess itself, click a citation, land on the real line |
| 1:10–1:30 | **The banishment** — a claim fails verification and is struck down on screen. The single most important shot in the video |
| 1:30–2:15 | The Debt Collector on the same skeleton: debt with interest, escalating notice, meter falling |
| 2:15–2:45 | The skeleton itself: one TOML config and a theme produce a third persona, with no change under `skeleton/` |
| 2:45–3:00 | What was built with Kiro, and where to find `/.kiro` |

Record it on Dec 2. Not on Dec 3, and never on Dec 4.

---

## Provider setup — deploy day, not day one

The deployed demo calls an LLM provider at runtime, billed to a **separate account**. Kiro
credits do not cover it; they pay for building in the IDE and expire 2026-12-31 anyway,
four weeks before judging ends.

Build against a **stub `LLMClient`** locally. No key is needed until deploy day
(~Nov 30), which also defers the Bedrock-vs-Anthropic decision until it actually matters.

Before the demo goes public, and not after:

1. Hard monthly spend cap at the provider.
2. Per-session and per-IP rate limits.
3. Cached runs as the **default** path, so the common judge journey costs nothing live.

The risk being managed is not your own usage — a few hundred judge queries is pennies. It
is that the rules require the demo to be free, unrestricted and login-free until
**2027-01-29**: a public endpoint holding your key, reachable by anyone with the URL, for
ten unattended weeks. The cap is abuse insurance, not a budget.
