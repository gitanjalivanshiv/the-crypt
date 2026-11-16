# Credit budget

**Allotment: 4,000 Kiro credits.** One-time, per the Official Rules: *"No additional usage
benefits will be provided."*

| Date | Deadline |
|---|---|
| 2026-12-01 12:00 PT (12-02 01:30 IST) | Last moment to *request* credits |
| 2026-12-04 (same day as submission) | Unredeemed credit codes expire, unreplaceable |
| 2026-12-31 23:59 PT | Redeemed credits expire |
| 2026-12-04 14:00 PT (12-05 03:30 IST) | Submission closes |
| 2027-01-29 13:00 PT | Judging ends — demo must stay live and free until here |

**Redeem the codes today.** A code that expires unredeemed is not replaced.

---

## 1. How Kiro bills

Officially published:

- A **credit** is a unit of work for answering a prompt, metered to two decimals (minimum
  charge 0.01).
- A simple prompt costs **less than 1 credit**; complex work such as executing a spec task
  **"typically costs more than 1 credit."**
- Credits are consumed by: any prompt in vibe or spec mode, spec refinement, task execution,
  and **agent hook execution**.
- Cost scales with tokens generated, thinking depth, and reasoning effort — two models on the
  same multiplier can cost differently for the same task.
- Model multiplier applies on top, with `Auto` as the 1.0x baseline.

Kiro does **not** publish a credits-per-task figure. Everything below is a derived planning
estimate. Replace it with measurements (§6).

### Derivation of the planning rates

From Kiro's legacy request-based overage pricing — $0.04 per vibe request, $0.20 per spec
request — against add-on credits at $0.04 each:

| Unit | Legacy price | Planning rate on Auto |
|---|---|---|
| One chat turn (vibe) | $0.04 | **≈ 1 credit** |
| One spec task execution | $0.20 | **≈ 5 credits** |
| One agent hook firing | ≥ $0.04 | **≥ 1 credit** |

Generating a spec document (requirements / design / tasks) is a large-context operation:
estimate **8–12 credits** each. Treat all of these as ±100% until measured.

---

## 2. Model multipliers

Auto = 1.0x baseline.

| Model | Multiplier | Verdict for this project |
|---|---|---|
| Qwen3 Coder Next | 0.05x | Bulk mechanical edits |
| **Claude Haiku 5.5** | **0.06x** (0.3x above 100K tokens) | **Boilerplate workhorse** |
| MiniMax M2.1 | 0.15x | Alternative bulk option |
| DeepSeek 3.2 / MiniMax M2.5 | 0.25x | — |
| Claude Haiku 4.5 | 0.4x | Superseded by 5.5 |
| GLM-5 | 0.5x | — |
| GPT-5.6 Luna | 0.6x (1.2x > 272K) | — |
| **Auto** | **1.0x** | **Default for everything** |
| Claude Sonnet 5.5 | 1.3x | Stalled tasks, focused fixes |
| **Claude Opus 5.5** | **2.0x** | **Capped at 15 prompts total** |
| Claude Opus 5 / 4.x | 2.2x | Use 5.5 instead — cheaper and newer |
| GPT-5.6 Terra | 2.2x (4.4x > 272K) | No |
| Kimi K3 | 2.4x | No |
| Grok 4.7 | 2.7x (5.4x > 200K) | No |
| GPT-5.6 Sol | 4.4x (8.8x > 272K) | No |
| Claude Fable 5.1 | 6x | No |

**The lever:** Haiku 5.5 at 0.06x is ~16x cheaper than Auto and ~33x cheaper than Opus 5.5.
Routing the mechanical half of the build to Haiku is worth more than any other saving
available — provided its sessions stay under 100K tokens, past which it costs 0.3x (a 5x
jump) and the advantage largely evaporates.

---

## 3. Planned spend

Baseline: every line on Auto unless marked.

| Phase | Work | Est. credits |
|---|---|---|
| Setup | Repo, steering, LICENCE, scaffolding — written by hand | **0** |
| Spec: skeleton | requirements + design + tasks, 2 review rounds (~6 generations) | 60 |
| Spec: medium | 4 generations | 40 |
| Spec: debt-collector | 4 generations | 40 |
| Build: skeleton | ~35 tasks × 5 | 175 |
| Build: medium | ~20 tasks × 5 | 100 |
| Build: debt-collector | ~18 tasks × 5 | 90 |
| Boilerplate pass | ~40 prompts on **Haiku 5.5** @ 0.06x | 3 |
| Debugging and iteration | ~150 chat turns × 1 | 150 |
| Hard problems | 15 prompts on **Opus 5.5** @ 2.0x | 60 |
| Agent hooks | capped at 60 fires × 1.5 | 90 |
| **Subtotal** | | **~810** |
| Rework at 50% | Specs that miss, tasks re-run once | ~405 |
| **Planned total** | | **~1,215** |
| **Reserve** | unallocated | **~2,785** |

### Reading this honestly

The build is not credit-constrained. At ~1,215 planned against 4,000 there is roughly **3x
headroom** — even if every estimate above is off by 100%, the project finishes with credits
to spare.

That is only true if none of §4 happens. Each item in §4 can exceed the entire allotment on
its own. **The budget is not a spending limit to respect; it is a list of four accidents to
avoid.** Having avoided them, spend freely — an unused credit on 2026-12-05 bought nothing,
because the submission can no longer be changed.

---

## 4. The four ways to lose 4,000 credits

### 4.1 Agent hooks on file save — up to 5,400 credits

Kiro hooks take one of two action types:

- `"action": { "type": "command", ... }` — runs a shell command. **Zero credits.**
- `"action": { "type": "agent", ... }` — injects a prompt into the conversation. **≥1 credit
  per firing.**

A `PostFileSave` agent hook fires on every save. At ~200 saves a day over 18 days at ~1.5
credits that is **~5,400 credits — more than the entire allotment**, spent on test runs that
`pytest` does for free.

The earlier draft of `kickoff-prompt.md` proposed exactly this ("on file save in
`skeleton/signals/`, run the analyzer tests"). It is now a command hook. See
`.kiro/hooks/`.

**Rule: every hook in this project is a `command` hook.** A hook needs an agent only if it
must *write code*, and no hook in this project does.

### 4.2 Expensive models by default — 2x to 6x on everything

Running the whole build on Opus 5.5 turns ~1,215 into ~2,430. On Fable 5.1 it is ~7,290 —
over budget before any rework. Model choice is set per request and is easy to leave on the
wrong value for days. Check it at the start of each session.

### 4.3 "Run all tasks" — unbounded, unsupervised

Kiro builds a dependency graph and runs independent tasks **concurrently in waves**. One
flawed design document becomes a whole wave of wrong implementations, billed in full, with
no moment to intervene. One task at a time, read the diff, commit, next.

### 4.4 Context creep across long sessions

Every turn re-bills the accumulated context, and the cheap models have hard thresholds —
Haiku 5.5 at 100K tokens (0.06x → 0.3x), GPT-5.6 at 272K (2x). A session that runs all day
costs several times what the same work costs across fresh per-task sessions.

---

## 5. Where credits must *not* be spent

Zero-credit work, done by hand or by a non-Kiro assistant:

README, LICENCE, `.gitignore`, Devpost submission copy, the demo video script, the blog post
for the Bonus Blog Prize, the social post, commit messages, CI YAML, deployment config,
dependency pinning, and the Kiro write-up itself.

Judging scores **Technological Implementation** on the depth of Kiro usage evidenced in
`/.kiro` and in the write-up — specs, hooks, steering, MCP, custom agents, property-based
testing. It does not score credits consumed. Rich `/.kiro` artefacts and a disciplined
transcript score better than a large bill.

---

## 6. Measure, then replace these numbers

The dashboard updates at least every five minutes. After the **first three spec task
executions**, record actuals here and recompute §3.

| Date | Phase | Model | Est. | Actual | Running total |
|---|---|---|---|---|---|
| | skeleton spec: requirements | Auto | 10 | | |
| | skeleton spec: design | Auto | 10 | | |
| | skeleton task 1 | Auto | 5 | | |

### Opus 5.5 log (cap: 15)

| # | Date | What it was needed for | Credits |
|---|---|---|---|
| 1 | | | |

### Checkpoints

- **1,000 consumed** — compare against plan. If the skeleton is not complete, cut analyzers
  4–6 now rather than later.
- **2,000 consumed** — both apps must be running locally. If not, freeze features and ship
  what works.
- **3,000 consumed** — stop generating. Hand-finish, deploy, record the video. A rough demo
  submitted beats a polished one that misses 14:00 PT.

---

## 7. Runtime LLM budget — a different budget

Kiro credits build the project. They do **not** run the deployed demo, and they expire on
2026-12-31, four weeks before judging ends on 2027-01-29.

The demo must be free and unrestricted for judges for that whole window:

- Separate provider account (Anthropic API) with a **hard monthly spend cap**.
- Per-session and per-IP rate limits.
- **Cached runs of the patient repo committed under `demo/`**, served when the live budget
  is exhausted or the provider errors. The cached path must be the default for the
  "Show me" button so a judge never waits on a cold model call.
- Monitor it the week of 2027-01-20; a demo that dies mid-judging loses Presentation and
  Potential Impact together.
