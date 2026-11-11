# 14 — Mobile QA Checklist: T-29

**Owner:** You (project lead / QA)
**Priority:** Low. Run only after the first clean demo rehearsal (see `docs/22-scope-decisions.md`).
**Depends on:** T-28 production deploy for Part B; Part A needs only a local build.

This checks the **website in a mobile-sized browser**. There is no Android or iOS app.
If a part is skipped, record it as NOT RUN. Do not mark it passed.

---

## Part A — minimum: browser devtools at 360px

Desktop Chrome or Edge, device toolbar set to 360px wide. About 10 minutes.

| Check | Result (PASS / FAIL / NOT RUN) | Notes |
|-------|-------------------------------|-------|
| `/login` — no horizontal scroll, buttons reachable | | |
| `/dashboard` — runs list readable, no horizontal scroll | | |
| `/dashboard/runs/[runId]` — six-step timeline readable | | |
| Run detail shows red/green output, root cause, confidence | | |
| "View draft PR" link works | | |
| Light / dark toggle works | | |
| Not-found page shows message + way back | | |
| Error page shows no stack trace | | |
| `/maintenance` shows maintenance message | | |

## Part B — optional: one real phone

Only if time allows after rehearsal. One device is enough; Android Chrome or iOS Safari.

| Check | Device / browser | Result (PASS / FAIL / NOT RUN) | Notes |
|-------|------------------|-------------------------------|-------|
| Sign-in completes end to end | | | |
| No dashboard content flashes before auth redirect | | | |
| `/dashboard` runs list renders | | | |
| Live timeline updates during a run | | | |
| Sign-out clears the session | | | |
| Offline shows an offline message | | | |

---

## Sign-off

**Part A:** [PASS / FAIL / NOT RUN] on [date], browser [name + version]
**Part B:** [PASS / FAIL / NOT RUN] on [date], device [model], browser [name + version]
**Signed:** [Your name], Project Lead / QA
