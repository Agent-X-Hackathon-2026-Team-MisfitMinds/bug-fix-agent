# 22 — Scope Decisions

**Owner:** You (project lead)
**Why this file exists:** Team Execution Guide §11 — when project files disagree, the decision is
written down first and code follows. Decisions here override older text in `docs/00`–`docs/11` and
in the guide.

---

## D-01 · Marketing pages and related content are out of scope

**Date:** 2026-11-11 · **Decided by:** project lead

This is a hackathon project. The product is the agent and its dashboard. The marketing site and
its content work are dropped.

**Dropped**
- Routes: `/how-it-works`, `/demo`, `/security`, `/pricing`, `/about`, `/changelog`, `/privacy`, `/terms`
- Page copy, SEO metadata, JSON-LD, OG images, sitemap / robots / canonical work
- Tickets (lead's mapping): T-09, T-25, T-26, T-27
- Lighthouse SEO ≥ 95 target on public routes

**Kept**
- Sign-in, `/dashboard`, `/dashboard/runs/[runId]`, error and maintenance pages
- The demo / example workspace views, as long as sample data stays labelled as not live

**Older text now stale**
`docs/02-content-seo.md` (whole file), route lists in `docs/03-app-flow.md`, `docs/05-architecture.md`,
`docs/08-quality.md`, Phase 3 and Phase 7 in `docs/10-plan.md`, the tickets above in `docs/11-tickets.md`,
and guide §2 (Subhi), §4 (folder tree) and §6 (Phase 7).

**Open at the time of writing**
`apps/web/src/app/[slug]/page.tsx`, `robots.ts` and `sitemap.ts` are still on `main` and still serve
those routes. Removing them is a frontend change for the frontend owner.

---

## D-02 · Mobile QA (T-29) is reduced and deprioritised

**Date:** 2026-11-11 · **Decided by:** project lead

Judges watch the demo on a laptop or projector. Phone polish does not change the demo outcome;
a pipeline that does not run does. T-29 also depended on T-28 and on the marketing pages in D-01.

**New scope** (`docs/14-phone-qa-checklist-t29.md`)
- Part A, minimum: devtools check at 360px on sign-in, dashboard, run detail, error pages.
- Part B, optional: one real phone, only after the first clean rehearsal.
- Anything skipped is recorded as NOT RUN.

T-29 is a website check in a mobile browser. No Android or iOS app is being built.

**Priority order for the team:** pipeline runs end to end → first clean rehearsal → everything else.
