# Deploy plan

## What the rules actually require

Quoted from the [Official Rules](https://kiroween.devpost.com/rules), Submission
Requirements:

> Provide a URL to your functional application(s).

And from Testing:

> Access must be provided to an Entrant's working Project for judging and testing by
> providing a link to **a website, functioning demo, or a test build**. [...] The Entrant
> must make the Project available free of charge and without any restriction, for testing,
> evaluation and use by the Sponsor, Administrator and Judges **until the Judging Period
> ends**. **Judges are not required to test the Project** and may choose to judge based
> solely on the text description, images, and video provided in the Submission.

Three things follow, and they set the whole shape of this plan.

1. A URL is **required**. This is not optional polish.
2. The accepted forms are broader than a hosted app: a test build counts.
3. It must stay up until **2027-01-29 13:00 PT** — eight weeks *after* submission closes.
   That uptime obligation, not the deploy itself, is the real liability.

One more clause binds the design. Under Functionality: the Project "must function as
depicted in the video." Whatever the video shows, the URL must do.

## The decision: ship no provider in production

The Medium needs a model; the Debt Collector does not. A public URL backed by a free-tier
provider key is the worst option available:

- the free tier is a per-day quota, so a handful of judges exhausts it
- an exhausted quota shows a judge a broken app, which is worse than a limited one
- the endpoint is public, so the quota is also anyone's to burn
- it is the only part of this system that can cost money

So **production runs the scripted path**, the same one the video uses — `demo/banishment.py`
for the Medium, no provider at all for the Debt Collector. This satisfies "must function as
depicted in the video" exactly, because it *is* what the video depicts. Say so in the
Devpost description, in one line: the hosted demo is a recorded séance; the verifier,
snapshot and reason codes are live.

## What makes this cheap: the snapshot can be baked

Measured, not estimated:

| | size |
|---|---|
| Snapshot store as ingested | 59 M |
| …with `repo/.git` deleted | **7.0 M** |

`.git` is 52 M of the 59 M, and nothing serving needs it. Findings and the code graph are
computed once at ingest and stored as `findings.json` and `graph.json`; only the working
tree is read afterwards, to resolve citations. Verified against a stripped store:

```
GET  /snapshots/{ref}            200
GET  /snapshots/{ref}/findings   200   100 findings
POST /snapshots/{ref}/ask        200   answered  ['banished', 'accepted']
                                       file_not_found: setuptools/midnight.py
POST /medium/snapshots/{ref}/plan 200
GET  /collector/.../ledger       200   300 lines, escalation final
POST /collector/.../notice       200   declined
```

So the deployable artefact is **7 MB of snapshot plus two static UI bundles**. There is no
clone at boot, no cold-start penalty from ingest, and no `git` binary needed at runtime.

## Option A — static, and recommended

Because the demo path is fully deterministic, every response can be captured to JSON at
build time and served as files. No server, no cold start, nothing to keep alive, nothing
to exhaust, and no uptime liability through to January.

- The **Debt Collector is lossless this way.** Ledger and plan are `GET`s over precomputed
  findings. Only the notice is a `POST`, and with no provider its response is a fixed
  decline.
- The **Medium loses only free-text questions.** Replace the input with the fixed question
  set the eval harness already defines (`medium/eval/questions.toml`) as a row of buttons.
  For a judge with two minutes, a set of good questions is a better experience than an
  empty box, and it is honest about what it is.

Hosts, all free for static: GitHub Pages (same account as the repo, no new service),
Cloudflare Pages, Netlify, or a Hugging Face **Static** Space. Verified today on the HF
docs: *"Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and
require a paid plan to create: PRO for personal accounts."* So HF is viable only as static.

GitHub Pages is the recommendation: the repo is already there and public, and there is no
second account to keep alive for two months.

## Option B — a real container, if a free host is confirmed

Keep this as an upgrade, not the plan of record. Each app becomes one container serving its
own UI from the same origin, so there is no CORS and no proxy:

- Medium: UI at `/`, API already at `/snapshots/*` and `/medium/*`
- Collector: UI at `/`, API already at `/snapshots/*` and `/collector/*`

Two services, two URLs, which also reads well against the Skeleton Crew requirement for two
distinct applications.

**I have not verified current free-tier terms for Render, Fly.io, Koyeb or Cloud Run, and
they change often.** Before choosing one, confirm exactly three things: that it needs no
credit card, that it will still be serving on 2027-01-29 without intervention, and what the
cold-start delay is after idle. A free tier that sleeps for 50 seconds is survivable; one
that needs a card is not, given the no-spend constraint.

## Option C — the floor

If both fail, the rules still permit "a test build". A `Dockerfile` plus one command in the
README, with the 7 MB snapshot baked in, is a legitimate submission. Weakest of the three,
but it is a real fallback and not a disqualification.

## Work required

Small, and mostly not deployment work at all:

1. **A judge must not land on an error.** `medium/ui` reads `?ref=` from the URL and, when
   it is missing, renders `missing_ref: add ?ref=<snapshot id> to the URL`. Both UIs need a
   baked-in default ref. This is the single highest-value fix here; everything else is
   plumbing.
2. **Lock down ingest** if Option B ships. `ApiConfig.allowed_hosts` already exists — set it
   to `github.com`, or disable the route. A public `POST /snapshots` lets anyone make the
   server clone arbitrary repositories: an abuse vector and a disk filler.
3. **A build step that bakes the snapshot**: ingest once, delete `repo/.git`, commit or ship
   the 7 MB result. Note `crypt-store/` is gitignored, so a baked store needs an explicit
   path or a force-add.
4. **Capture the API responses** (Option A only), driven by `demo/banishment.py` and the
   collector with no provider.
5. **A `Dockerfile`** (Options B and C). None exists yet.

## Risks

| Risk | Handling |
|---|---|
| Free host disappears or starts charging before 2027-01-29 | Option A has no host to lose. This is the main argument for it. |
| Judge opens the bare URL and sees `missing_ref` | Work item 1. Do it first. |
| Hosted app behaves differently from the video | Production runs the same scripted path the video records. |
| Someone burns the provider quota | No provider in production. |
| Someone makes the server clone arbitrary repos | `allowed_hosts`, or no ingest route at all. |

## Sequencing against 2026-12-04 14:00 PT

The URL is required at submission, so it must exist before the form is submitted — but it
need not be the best version. Ship Option A, submit, and treat Option B as a post-submission
upgrade if a host is confirmed. The URL may be improved after submitting; the deadline
cannot be moved.

Set a calendar reminder for **2027-01-20** to confirm the URL still answers, nine days
before judging closes.
