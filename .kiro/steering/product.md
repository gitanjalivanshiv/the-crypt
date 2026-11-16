---
inclusion: always
---

# Product: The Crypt

A reusable skeleton that reads a real codebase and lets a haunted persona talk about it
**truthfully**. Two distinct apps ship from the same skeleton.

Hackathon: Kiroween 2026, category **Skeleton Crew**. Submission closes
**2026-12-04 14:00 PT** (2026-12-05 03:30 IST).

## The two apps

1. **The Medium** (`medium/`) — a conversational ghost of a legacy system. The user
   interviews it ("why do you break on the 31st?"). Every answer cites real files and line
   ranges. It ends by emitting a resurrection plan (requirements, design, tasks).
2. **The Debt Collector** (`debt-collector/`) — a menacing collector who itemises technical
   debt with "interest" (estimated cost of leaving it), issues escalating notices, and offers
   a ranked repayment plan.

## Goals, in priority order

1. **Truthfulness.** The persona never invents a file, line number, or quote. See
   `grounding-rule.md`. This is the differentiator; everything else is decoration.
2. **Skeleton proof.** A third persona/app must be addable with a config file and a thin UI,
   with zero edits to `skeleton/`. The judging criterion is versatility, not volume.
3. **A spooky experience that stays legible.** CRT terminal look, dry techy humour, sound,
   escalation on high-risk files.
4. **A measured result on a real open-source repo** (the demo "patient").

## Tone

Dry techy horror-comedy. Developers should laugh in recognition ("It has been 847 days since
anyone touched this file"). Humour wraps verified facts; it never substitutes for them. A
number in a joke is still a number that must come from the signals layer.

## Signature interactions

- The Medium "possesses" the file tree: each cited file highlights as the ghost speaks it.
- The Debt Collector shows a debt meter that falls as refactors are accepted; the largest
  debts are "boss fights".
- A failed citation is **banished** on screen. Rejection is a feature, shown not hidden.

## Non-goals

- Running, executing, or modifying the analysed code.
- Proprietary, employer, or client code anywhere in this repo or in the demo.
- Accounts, payments, or persisted user data beyond the session.
- Analysing anything but permissively licensed open-source repos.
