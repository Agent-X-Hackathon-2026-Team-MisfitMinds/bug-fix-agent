# 14 — Real-Phone QA Checklist: T-29

**Owner:** You (project lead / QA)
**Devices:** 1 Android (Chrome), 1 iOS (Safari)
**Viewport:** 360px + desktop
**Network:** WiFi + slow 3G
**Depends on:** T-28 production deploy (smoke test passes first)

---

## Acceptance checklist

### All marketing pages (`/`, `/how-it-works`, `/demo`, `/security`, `/pricing`, `/about`, `/changelog`, `/privacy`, `/terms`)

- [ ] Loads ≤ 3s on 3G (Android Chrome)
- [ ] Loads ≤ 3s on 3G (iOS Safari)
- [ ] No horizontal scroll at 360px width
- [ ] Nav hamburger menu opens/closes on mobile
- [ ] Dark mode toggle works on mobile
- [ ] All links navigate to correct pages

### Auth flow

- [ ] Sign-in completes end-to-end on Android Chrome
- [ ] Sign-in completes end-to-end on iOS Safari
- [ ] `__Host-session_id` cookie set (HttpOnly, Secure, SameSite=Lax)
- [ ] Sign-out clears session, redirects to `/`
- [ ] No dashboard content flashes before auth redirect

### Dashboard + SSE timeline

- [ ] `/dashboard` renders signed-in runs list on mobile
- [ ] `/dashboard/runs/[runId]` SSE timeline animates on mobile
- [ ] Run detail shows red/green output, root cause, confidence
- [ ] "View draft PR" button works on mobile
- [ ] Offline state shows "You're offline" message

### Error states

- [ ] `/404` shows "Page not found" + "Go home" button
- [ ] `/500` shows "Something went wrong" + "Try again"
- [ ] `/maintenance` shows maintenance message
- [ ] No stack traces exposed to user

---

## Test record template

| Test step | Android Chrome | iOS Safari | Pass/Fail | Notes |
|-----------|---------------|------------|-----------|-------|
| Home page loads ≤3s on 3G | | | | |
| Marketing nav works at 360px | | | | |
| Dark mode toggle mobile | | | | |
| Sign-in flow completes | | | | |
| Sign-out clears session | | | | |
| Dashboard runs list mobile | | | | |
| SSE timeline animates mobile | | | | |
| 404 page shows microcopy | | | | |
| 500 page no stack trace | | | | |
| No horizontal scroll | | | | |

**QA sign-off:** All steps pass on both devices.  
**Devices tested:** Android [model] Chrome [version], iOS [model] Safari [version]  
**Date:** [date]  
**Signed:** [Your name], Project Lead / QA
