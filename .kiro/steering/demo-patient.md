---
inclusion: manual
name: demo-patient
description: Selection criteria and candidates for the open-source repo the personas analyse. Load with #demo-patient when choosing or changing the demo patient.
---

# The demo patient

The open-source repo both apps analyse in the demo. One patient, pinned to one commit SHA.

## Selection criteria (all must hold)

1. **Permissive licence** — MIT, BSD, or Apache-2.0. Verify the `LICENSE` file at clone
   time; do not trust the GitHub badge alone. Copyleft is out.
2. **Mostly Python** — v1 ships the Python grammar only.
3. **Genuinely old**, with a long, messy git history. Churn and staleness signals need real
   history to say anything.
4. **Small enough to analyse in under ~60 seconds** on the demo host. Judges will not wait.
   Under roughly 100k lines.
5. **Recognisable** to a developer audience. "I know that one" is half the joke.
6. Pinned to a **specific commit SHA**, recorded in `demo/patient.json`. All citations and
   cached runs verify against that snapshot, never against moving `main`.

## Candidates

| Repo | Licence | Why | Risk |
|---|---|---|---|
| `pypa/setuptools` | MIT | Best debt story: two decades of accreted packaging cruft, deep history, instantly recognisable | Largest of the three; check analysis time |
| `psf/requests` | Apache-2.0 | Small, fast, famously stable — a strong *staleness* narrative | Clean code, so less debt to collect |
| `pallets/itsdangerous` | BSD-3 | Tiny, analyses in seconds | Too small to be impressive alone |

**Decision rule:** `setuptools` is the primary patient if a full analysis finishes under
60s; otherwise `requests`. Keep `itsdangerous` as the smoke-test fixture in CI — small
enough to run on every commit for free.

## Obligations

- Honour the patient's licence. Quote only what a citation needs, attribute it, and link to
  the source at the pinned SHA.
- Never present the patient's maintainers as negligent. The humour targets the code and the
  passage of time, never the people. A funny project that insults real maintainers is a
  liability at judging.
- Record the patient, SHA, licence, and clone date in `demo/patient.json`.
