# Submission checklist

Every line is traceable to the Kiroween 2026 Official Rules. Tick nothing you have not
actually opened and looked at.

## Disqualification risks — check these first

- [ ] `/.kiro` exists **at the repository root** and is committed.
- [ ] Neither `.kiro` nor any sub-folder of it appears in `.gitignore`. The rules state this
      "could disqualify your submission." Verified by `scripts/check-kiro-committed.sh`.
- [ ] Repository is **public** and on **GitHub** (not GitLab, not BitBucket).
- [ ] An open-source licence file is present **and visible in the GitHub About panel**.
      A `LICENSE` file that GitHub fails to detect does not satisfy this.
- [ ] Two separate top-level application folders — `medium/` and `debt-collector/` —
      required for Skeleton Crew.
- [ ] Every line of the project was created on or after 2026-10-30. Any pre-existing code is
      disclosed in the submission.
- [ ] Sufficient use of Kiro is evident. Insufficient use is disqualifying at the judges'
      sole discretion.
- [ ] No third-party trademarks or copyrighted music in the video.
- [ ] All materials in English.

## Repository

- [ ] README explains what it is, how to install it, and how to run it.
- [ ] The repo contains **all** source, assets, and instructions needed to make it function.
- [ ] `.kiro/specs/` holds the seven specs, each with requirements, design, and tasks.
- [ ] `.kiro/hooks/` holds the hooks, and every one is a `command` hook.
- [ ] `.kiro/steering/` holds the five always-on files plus `demo-patient.md`.
- [ ] `.kiro/settings/mcp.json` configures the signals MCP server.
- [ ] Hypothesis property-based tests for the verifier are present and passing.
- [ ] A fresh clone installs and runs from the README alone, on a machine that is not yours.

## Live demo

- [ ] Public URL for each app, working.
- [ ] Free of charge and unrestricted for judges **until 2027-01-29 13:00 PT**.
- [ ] No login required. If one is unavoidable, credentials and instructions go in the
      Devpost form (judge-visible only, not public).
- [ ] The deployed build runs **no provider at all** — the same scripted path the video
      records, so it "must function as depicted in the video" holds and there is no quota
      for a judge, or anyone else, to exhaust. See [DEPLOY-PLAN.md](DEPLOY-PLAN.md).
- [ ] Neither UI shows `missing_ref` on the bare URL; a default snapshot is baked in.
- [ ] If the API is hosted rather than static, `ApiConfig.allowed_hosts` is set so the
      ingest route cannot be told to clone arbitrary repositories.
- [ ] Calendar reminder for 2027-01-20 to confirm the URL still answers.

## Video

- [ ] Under 3:00.
- [ ] Shows the project working on the device it was built for.
- [ ] Uploaded to YouTube and **set to public** — not unlisted, not private.
- [ ] No copyrighted music.

## Devpost form

- [ ] Category selected: **Skeleton Crew**.
- [ ] Text description of features and functionality.
- [ ] GitHub URL, app URLs, YouTube URL.
- [ ] **Kiro write-up** (`docs/KIRO-USAGE.md`) covering: which Kiro surfaces were used
      (IDE / CLI / Web / Crew) and how they differed; custom agents; agent hooks and the
      workflows they automated; spec-driven development and how it compared to vibe coding;
      steering strategy; MCP; property-based testing; Kiro powers.
- [ ] Bonus prizes selected, with their required evidence attached.
- [ ] **Submitted, not left in draft.** A saved draft is not an entry.

## Bonus evidence

- [ ] Blog post URL — published during the submission period, mentions Kiroween 2026.
- [ ] Social post URL — `#KiroweenHackathon26` is the **first text in the post**.
- [ ] Kiroween 2025 registration confirmed, if applicable.
- [ ] Student details for every team member, if claiming.
- [ ] Kiro Crew app repo URL, if claiming.
