# 20 — Demo Kit: T-33

**Owner:** You (project lead / QA)
**Use with:** `docs/18-demo-rehearsal-t33.md` (step checklist) and `docs/19-seeded-demo-reference.md`
(the three bugs and exact issue text; lands with T-17)
**Sources:** `docs/00-brief.md`, `docs/01-prd.md`, Team Execution Guide §1, §2, §7F, §8

**Honesty rule.** This kit describes what we show and what we expect. It contains no results.
Results are written into `docs/18` only after a rehearsal actually produced them. If a step did not
run, say NOT RUN. Never present a recording as live, never invent a passing test or a PR.

Two claims we never make: the agent is autonomous, and the agent merges. It opens **draft** PRs; a
human reviews and merges.

---

## 1. Judge-facing script (5:00)

| # | Time | On screen | Say |
|---|------|-----------|-----|
| 1 | 0:00–0:30 | Slide 2 | Developers lose hours to triage: reading an issue, reproducing it, finding the cause, before any fix is written. Tools that fix without proof are not trusted, so the hours stay. |
| 2 | 0:30–0:50 | Demo repo, issue #1 open | Our whole interface is one action. I add the label `agent-fix` to this issue. Nothing else. |
| 3 | 0:50–2:20 | Dashboard run detail, live timeline | The run appears. Six steps: read the issue, reproduce it inside a Docker sandbox, diagnose, fix, verify, open a pull request. Narrate each step as it turns complete. On Reproduce: "it first writes a test that fails. No failing test, no fix." On Verify: "the new test must pass and the existing suite must stay green." |
| 4 | 2:20–3:20 | The draft PR on GitHub | This is the output: a draft pull request. Failing-before and passing-after test output, the root cause in plain English, what changed, and a confidence level with reasons. It is a draft. The agent has no merge permission. A person decides. |
| 5 | 3:20–4:00 | Issue #5, then its run | This issue is too vague to reproduce. Label it. The agent does not guess: it comments that it could not reproduce and opens no PR. An honest "no" is a feature. |
| 6 | 4:00–4:40 | Slide 6 | Safety. Untrusted code runs only in a throwaway container: no network after dependencies are installed, non-root user, no host mounts, CPU, memory and time limits, and no tokens inside the sandbox. |
| 7 | 4:40–5:00 | Slide 7 | Scope today: Python and pytest, on our seeded repository. Cost: ₹0, free tiers only, self-hostable for private repos. Other languages are roadmap. |

Block lengths: 30 + 20 + 90 + 60 + 40 + 40 + 20 = 300 seconds.

**Presenter notes**
- Issue #4 is labelled before going on stage only if the rehearsal showed a single run takes too
  long to show two live. Say so if it was started earlier.
- Keep the terminal with the webhook tunnel off the projected screen (guide §9: no secrets in
  screenshots).
- If the live run stalls: follow section 4, announce the switch.

---

## 2. Slide outline (8 slides)

| # | Title | One line | Visual to capture |
|---|-------|----------|-------------------|
| 1 | Bug-Fix Agent | Every GitHub issue becomes a tested, human-reviewed pull request. | Product name, team name, Agent-X Hackathon 2026 |
| 2 | The problem | Developers spend hours triaging issues; unproven auto-fixes are not trusted. | Plain text, no stock imagery |
| 3 | One action | Add the `agent-fix` label. Everything else is automatic until review. | Screenshot: label being added to an issue |
| 4 | How it works | Read → Reproduce → Diagnose → Fix → Verify → Draft PR. | Six-step timeline from the dashboard |
| 5 | Proof, not promises | A test that fails before the fix and passes after it, with the existing suite green. | Screenshot: failing-before / passing-after output from a real rehearsal run |
| 6 | Safe by construction | Docker sandbox: no network after install, non-root, no host mounts, no tokens, hard limits. Draft PR only; a human merges. | Short list; optional `docker run` flags |
| 7 | Scope and cost | Python + pytest, seeded demo repo, ₹0. Roadmap: more languages. | Scope vs roadmap, two columns |
| 8 | Team and ask | Four owners: agent, backend and sandbox, frontend, QA and demo. | Names and roles |

Slides 3, 4 and 5 use screenshots taken from a real rehearsal run. Until one exists, leave the
placeholders empty; do not mock up results. The dashboard's `/demo/example` page is labelled
"illustrative, not live" and may be shown only with that label visible.

---

## 3. Judge Q&A

**How is this different from Copilot or Devin?**
Three things, in this order: red-to-green proof on every PR (a failing test before, passing after),
a mandatory human gate (draft PR, no merge permission), and ₹0 self-hostable operation for private
repos.

**What stops the sandbox leaking secrets or attacking the host?**
Tests run in a throwaway Docker container with no network, a non-root user, no host mounts, dropped
capabilities and CPU, memory and time limits. Tokens never enter the container.

**What if the fix is wrong or overfitted to the new test?**
The full existing suite must stay green, confidence is reported with reasons, and the PR is a draft.
The human reviewer is the final gate; the agent cannot merge.

**Does it work on other languages or any repository?**
Not in this version. MVP is Python with pytest on our seeded repository. Other languages are roadmap.

**Why did the third issue fail?**
By design. Its text has no steps and no expected or actual behaviour. The agent reports that it
could not reproduce rather than inventing a fix.

**What about free-tier LLM rate limits?**
Responses for the rehearsed issues are cached, failures end in a clear failed state, and we carry a
recorded run as a fallback, which we announce as a recording.

**Is the fix merged automatically?**
No. Never. Draft PR plus human review.

If a question touches something that is not built or was not run, say so directly.

---

## 4. Recorded backup run

**When to record:** immediately after the first rehearsal in which all of `docs/18` passes. Not
before; a recording of a partial or simulated run is not a backup.

**The recording must show** (same items as the "Recorded backup run" checklist in `docs/18`):
1. Label added to issue #1; run appears; all six steps complete.
2. Draft PR for issue #1 with failing-before / passing-after output and root cause.
3. Same for issue #4.
4. Issue #5 ending in the "couldn't reproduce" comment, with no PR.
5. Dashboard listing all three runs.

**Before recording**
- Close terminals and tabs that show `.env` values, tokens, the tunnel URL or the GitHub App private
  key.
- Use the same demo repo and issue text as the live demo (`docs/19`).
- One continuous take per issue; do not splice a failing run into a passing one.

**Storage:** keep the file outside the repository (it is large and may show account details). Have
it on the presenting laptop and one second device. Record where it is here after it exists:

| Item | Value |
|------|-------|
| Recorded on (date) | |
| Commit of `main` used | |
| File location | |
| Second copy | |
| Checked playable by | |

**Switching during the live demo**
- Trigger: a live step shows no progress for the limit agreed at rehearsal, or the LLM returns a
  rate-limit failure.
- Say: "The free-tier model has rate-limited us. This is a recording of the same run from our
  rehearsal." Then play from the matching step.
- Afterwards, show the real draft PRs from that rehearsal on GitHub so judges see they exist.

---

## Rehearsal log

Fill in after each rehearsal. One row per attempt, including failed ones.

| Date | Issue #1 | Issue #4 | Issue #5 | Dashboard shows 3 runs | Notes |
|------|----------|----------|----------|------------------------|-------|
| | | | | | |
