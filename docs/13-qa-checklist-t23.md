# 13 — QA Checklist: T-23 E2E Suite Verification

**Owner:** You (project lead / QA lead)
**Verifies:** Subhi's Playwright E2E tests J1–J8 pass on Chromium + WebKit
**Depends on:** T-08, T-11, T-13, T-16 (must be merged to main first)
**Gate:** `npx playwright test --reporter=html` — all J1–J8 pass

---

## The 8 E2E Journeys (J1–J8)

From docs/08-quality.md § 3 and docs/03-app-flow.md § Critical journeys:

| Journey | Name | What it tests | Expected result |
|---------|------|---------------|-----------------|
| J1 | Label → PR | Add `agent-fix` label to seeded issue → draft PR opened with red→green proof | Draft PR created, test output shows FAILED→PASSED |
| J2 | Demo flow | All 6 SSE steps render on run detail + red/green output visible | Timeline streams read→reproduce→diagnose→fix→verify→pr |
| J3 | Review PR | Open draft PR, verify root-cause + confidence + PR link | PR body shows root cause, confidence High/Medium/Low |
| J4 | Login/logout | GitHub OAuth sign-in → dashboard → sign-out | Session cookie set, dashboard renders, sign-out clears cookie |
| J5 | Failed-run recovery | Pipeline failure → retry button → successful rerun | Retry works, run recovers to completed state |
| J6 | IDOR negative | User A tries to access User B's run detail | Returns 404, no data leaked |
| J7 | Unauth negative | Access `/dashboard` without session | Redirects to `/auth/github`, no dashboard content flash |
| J8 | SSE reconnect | Network drop during run → reconnect | Timeline reconnects, no duplicate steps |

---

## Acceptance checklist (all must pass before T-23 is Done)

- [ ] J1 passes: label issue → draft PR with red→green proof on Chromium
- [ ] J1 passes: label issue → draft PR with red→green proof on WebKit
- [ ] J2 passes: all 6 SSE steps visible on run detail page
- [ ] J2 passes: red/green test output block renders correctly
- [ ] J3 passes: root-cause text, confidence badge, "View draft PR" link present
- [ ] J4 passes: sign-in → dashboard → sign-out flow completes
- [ ] J5 passes: failed run retries and completes successfully
- [ ] J6 passes: foreign run_id returns 404 (not 403)
- [ ] J7 passes: unauthenticated dashboard access redirects with no flash
- [ ] J8 passes: SSE reconnects without duplicate steps
- [ ] HTML report generated: `npx playwright test --reporter=html`
- [ ] Test evidence saved to PR (screenshots, report link)
- [ ] QA sign-off comment posted on PR

---

## How to run

From `apps/web/`:

```powershell
# Install Playwright browsers (first time only)
npx playwright install

# Run all E2E tests
npx playwright test --reporter=html

# Run specific journey
npx playwright test --grep "J1"

# View HTML report
npx playwright show-report
```

**Note:** Playwright test-results, playwright-report, and test-results folders are git-ignored — do not commit them. Save evidence as screenshots to the PR instead.

---

## QA sign-off template (paste on PR)

```
QA sign-off — T-23 E2E Suite

Journeys tested: J1–J8 on Chromium + WebKit
Results: [PASS/FAIL] per journey
HTML report: [link]
Screenshots: [attached]

All 8 journeys pass. Ready for merge.
— [Your name], Project Lead / QA
```
