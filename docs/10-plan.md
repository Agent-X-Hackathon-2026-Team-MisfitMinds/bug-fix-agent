# 10 — Plan: Bug-Fix Agent

Release plan in 10 phases (0–9). Every phase leaves the site runnable and demoable; every phase ends with a provable "Done when" gate (a command you can run or a visible result you can open in a browser).

**Reads:** 00-brief.md · 01-prd.md · 02-content-seo.md · 03-app-flow.md · 04-design-system.md · 05-architecture.md · 06-data-api.md · 07-security-privacy.md · 08-quality.md · 09-operations.md · STANDARS.md · **Length:** 3–4 pages · **Tracks:** Sprint · Launch · Scale · **Demo DoD (from 00-brief.md):** On a prepared Python demo repo, label 3 seeded issues live → ≥2 produce draft PRs with red→green proof and root-cause notes; the 3rd ends with an honest "couldn't reproduce" comment. The dashboard shows each run end to end.

**Team (4 roles):** Agent/LangGraph pipeline · Sandbox/Infra (Docker runner, GitHub App, webhooks) · Frontend (Next.js dashboard) · Pitch/QA (demo repo, seeded bugs, deck, rehearsals).

**Budget:** ₹0 · **Deadline:** 24–48 hour hackathon sprint · **No database** (ADR-006: transient JSON files / in-memory).

---

## Parallelism across phases (4 team members)

| Phase | Parallel work |
|-------|---------------|
| 0 · Foundation | Agent: shared types · Sandbox/Infra: docker-compose.yml · Frontend: Next.js scaffold · Pitch/QA: .env.example + README |
| 1 · Design system & shell | Frontend builds tokens + shell; Sandbox/Infra provisions Docker + GitHub App in parallel |
| 2 · Data & auth | Sandbox/Infra builds auth + data layer; Frontend builds lib/api-client.ts + lib/session.ts in parallel |
| 3 · Core pages & states | Frontend owns all routes (no cross-team dependency once Phase 2 lib is done) |
| 4 · Core features | Agent builds LangGraph pipeline; Sandbox/Infra builds Docker sandbox + webhook handler in parallel (both depend on Phase 2 data layer) |
| 5 · Integrations | Sandbox/Infra wires GitHub App + Vercel; Frontend wires SSE bridge; Agent prepares seeded demo runs |
| 6 · Hardening | QA leads E2E + axe + CI gates; the other three fix issues found in parallel |
| 7 · Content, SEO & polish | Pitch/QA owns copy + structured data; the team fixes hardening bugs in parallel |
| 8 · Launch | All hands on deck — no parallelism; it is the launch gate |
| 9 · Post-launch | Pitch/QA leads demo prep + monitoring; others on standby for fixes |

---

## Phase 0 · Foundation

**Goal:** Repo scaffolding + CI spine so every later change runs through the full gate stack (G1–G14 from 08-quality.md).

**Deliverables:**
- Monorepo layout: `apps/web/` (Next.js), `apps/api/` (FastAPI), `packages/shared/` (types)
- `docker-compose.yml` bringing up api + web + Docker sandbox
- `.env.example` listing all required keys with placeholder values (no real secrets)
- `.gitignore` excluding `.env`, `node_modules`, `__pycache__`
- GitHub Actions workflow with CI gates G1–G14 (tsc, eslint, ruff, mypy, vitest, pytest unit, pytest integration, Playwright E2E, axe, Lighthouse CI, bundle size, npm audit, pip audit, visual regression)

**Tickets:**
- T-00 · Repo init — folder tree, docker-compose.yml, .env.example, README
- T-01 · CI pipeline — GitHub Actions workflow implementing all 14 gates
- T-02 · Shared types — Run, Step, Status, Confidence (TS/Python via JSON schema)

**Risks:** CI flakiness on first run; secrets leaking into `NEXT_PUBLIC_*`; monorepo config drift between web and api.

**Done when:** `npm ci && npm run check` passes locally and in CI; `docker compose up` starts both web (localhost:3000) and api (localhost:8000) without errors.

**Parallel:** Yes — all four roles work on independent scaffolding tasks.

**Runnable/demoable invariant:** `localhost:3000` shows a Next.js shell; `localhost:8000/docs` shows FastAPI OpenAPI docs.

---

## Phase 1 · Design system & shell

**Goal:** Token-driven UI shell matching 04-design-system.md; every component supports all 7 states (default, hover, focus-visible, active, disabled, loading, error); dark mode parity; works at 360px+.

**Deliverables:**
- CSS variables `--ds-*` in `app/globals.css` (light + `[data-theme="dark"]`)
- `tailwind.config.js` with the complete theme from 04-design-system.md
- Components: button, card, nav, footer, skeleton, empty-state, toast, status-badge, run-list, sse-timeline
- Dark mode toggle + system preference detection
- Touch targets ≥44px; focus rings visible and unobscured

**Tickets:**
- T-03 · Design tokens — `--ds-*` CSS variables + Tailwind theme
- T-04 · Base components — button, card, skeleton, empty-state, toast
- T-05 · Nav shell + dark mode — nav, footer, theme toggle, responsive layout

**Risks:** Hardcoded colours/spacing/spacing escaping tokens; contrast failures below AA; dark mode parity broken at some viewport.

**Done when:** Design-director prompt passes; token lint clean (no hardcoded colours, font sizes, or spacing); screenshots at 360/768/1280 px in light + dark match the design-system spec.

**Parallel:** Yes — Frontend owns the UI; Sandbox/Infra can provision Docker + GitHub App concurrently.

**Runnable/demoable invariant:** Open `localhost:3000` — nav renders, dark mode toggles, all components in every state are visible via Storybook-style preview or a /dev sandbox page.

---

## Phase 2 · Data & auth

**Goal:** JSON-file repository + Pydantic schemas + FastAPI API routes + GitHub OAuth sessions with deny-by-default ownership (07-security-privacy.md §4, §2).

**Deliverables:**
- Data repo interface (`apps/api/data/`) with in-memory/JSON-file backend matching the logical schema in 06-data-api.md (runs, run_steps, llm_cache, webhook_events, sessions)
- Pydantic models for all request/response shapes
- API routes: GET /runs, GET /runs/{run_id}, GET /runs/{run_id}/events (SSE), POST /runs/{run_id}/retry, GET /auth/session, POST /auth/logout
- Auth: GitHub App OAuth flow, `__Host-session_id` cookie (HttpOnly, Secure, SameSite=Lax, 24h), session middleware, ownership filter on every query
- Frontend `lib/api-client.ts`, `lib/session.ts`, `lib/sse.ts`

**Tickets:**
- T-06 · Data repo + schemas — JSON-file repository, Pydantic models, error format
- T-07 · API routes — all GET/POST routes with rate limiting and ownership checks
- T-08 · GitHub OAuth + sessions — oauth.py, session middleware, sign-in/sign-out

**Risks:** IDOR via guessed run_id; cookie misconfig (missing HttpOnly/Secure); webhook secret mishandling; ownership check missed on a query.

**Done when:** pytest integration green (G6/G7); `GET /runs` without session → 401; `GET /runs/{other_user_run_id}` → 404 (not 403); `__Host-session_id` cookie has HttpOnly, Secure, SameSite=Lax.

**Parallel:** Yes — Sandbox/Infra builds auth + data layer; Frontend builds the client libraries in parallel once types are shared.

**Runnable/demoable invariant:** Open `localhost:3000/dashboard` unsigned-in → redirected to `/auth/github`; signed-in → dashboard shell renders with empty-state microcopy.

---

## Phase 3 · Core pages & states

**Goal:** All 16 routes from 03-app-flow.md rendered with every state (loading, empty, error, success, partial, offline, signed-out, signed-in, no-permission) and microcopy from the state tables.

**Deliverables:**
- Marketing pages: `/`, `/how-it-works`, `/demo`, `/security`, `/pricing`, `/about`, `/changelog`, `/privacy`, `/terms` (SSG/ISR per 05-architecture.md)
- Auth routes: `/auth/github`, `/auth/callback` (redirect-only)
- App routes: `/dashboard` (runs list), `/dashboard/runs/[runId]` (run detail + SSE timeline)
- Error pages: `/404`, `/500`, `/maintenance`
- SSE client (`lib/sse.ts`) connecting to FastAPI event stream
- Run list table + run detail timeline components
- Every page state has microcopy from 03-app-flow.md state tables

**Tickets:**
- T-09 · Marketing pages — all 9 static/ISR routes with nav, footer, CTA microcopy
- T-10 · Auth routes — `/auth/github`, `/auth/callback` redirect flow
- T-11 · Dashboard + run detail — runs list table, SSE timeline, step nodes
- T-12 · Error pages + SSE client — 404/500/maintenance, EventSource reconnect logic

**Risks:** Missing a state on a page (state-table incompleteness); SSR/SSG routing mismatches; SSE reconnect creating duplicate steps.

**Done when:** All 16 routes axe-clean (G9); every route renders loading/empty/error/success states; pages work at 360px without horizontal scroll.

**Parallel:** Yes — Frontend owns all routes; no cross-team dependency once Phase 2 `lib/api-client.ts` exists.

**Runnable/demoable invariant:** Open each of the 16 routes in a browser — each shows correct microcopy for its current state; SSE timeline animates on a mocked run detail page.

---

## Phase 4 · Core features

**Goal:** The agent pipeline actually works end-to-end: webhook → LangGraph → Docker sandbox → LLM → red→green proof → draft PR → issue comments.

**Deliverables:**
- LangGraph pipeline: Read → Reproduce → Diagnose → Fix → Verify → PR (stateful, retry/checkpoint)
- Docker sandbox: `--network=none` after dep install, `--user=nonroot`, `--memory`, `--cpus`, no host mounts, no tokens inside container, 5-min timeout
- LLM calls with caching (cache key = SHA-256 of issue_title + issue_body), rate-limit retry, graceful "couldn't process" fallback
- GitHub webhook handler: `X-Hub-Signature-256` verification, `X-GitHub-Delivery` dedup, `agent-fix` label detection
- Draft PR creation via GitHub API (draft, not mergeable; agent has no merge permission)
- Issue progress comments at each step (picked up → reproducing → fixed → PR opened, or "couldn't reproduce")
- Seeded demo repo with 3 deterministic bugs (off-by-one, wrong condition, missing null check)

**Tickets:**
- T-13 · LangGraph pipeline — 6-step graph with retry/checkpoint/resume
- T-14 · Docker sandbox — resource limits, isolation, non-root, no network after dep install
- T-15 · LLM + caching — cached responses, rate-limit handling, fallback messages
- T-16 · Webhook handler — signature verify, dedup, label-triggered pipeline start
- T-17 · Seeded demo repo — 3 deterministic Python bugs with known fixes

**Risks:** Free-tier LLM rate limits stall mid-demo; sandbox escape or secret leakage; reproduction fails on live issue; overfitted fix passes new test but breaks intent; webhook never reaches local dev.

**Done when:** Label a seeded issue `agent-fix` → pipeline runs → draft PR opened with red→green test output and root-cause write-up; sandbox runs with `--network=none` confirmed in `build_docker_cmd()` unit test.

**Parallel:** Yes — Agent builds LangGraph; Sandbox/Infra builds Docker sandbox + webhook handler concurrently (both depend on Phase 2 data layer).

**Runnable/demoable invariant:** Label issue #1 (off-by-one) → see run appear on `/dashboard` → SSE timeline streams all 6 steps → draft PR link visible with `FAILED → PASSED` test output.

---

## Phase 5 · Integrations

**Goal:** Wire everything together and make it reachable from the internet for the hackathon demo.

**Deliverables:**
- GitHub App created and configured (client ID, private key, webhook secret, `agent-fix` label scope)
- Webhook forwarding: smee.io or ngrok from GitHub to local FastAPI (dev) or production backend
- Vercel: preview deploy on every PR, production deploy on `main` merge
- Production env vars injected (from `.env.example` + real secrets; no secrets in `NEXT_PUBLIC_*`)
- SSE bridge: FastAPI → Next.js EventSource working across preview/production origins
- Health check: `curl -sf https://<domain>/` returns 200

**Tickets:**
- T-18 · GitHub App + webhook — App registration, secret storage, webhook forwarding tunnel
- T-19 · Vercel deploy + env — preview + production, env var mapping per environment
- T-20 · SSE bridge — cross-origin EventSource from Vercel frontend to backend

**Risks:** ngrok/smee instability during demo; GitHub API rate limits; OAuth callback URL mismatch; backend unreachable from Vercel preview.

**Done when:** A real GitHub webhook (from the seeded repo) triggers the pipeline end-to-end; preview URL passes Lighthouse CI (G10); health check returns 200.

**Parallel:** Yes — Sandbox/Infra wires GitHub App + Vercel; Frontend wires SSE bridge; Agent prepares seeded demo runs concurrently.

**Runnable/demoable invariant:** Open the preview URL → label a seeded issue → watch the live SSE timeline on `/dashboard/runs/[runId]`.

---

## Phase 6 · Hardening

**Goal:** All 14 CI gates green; E2E journeys J1–J8 passing; axe zero serious/critical; bundle size within budgets; security headers and rate limits enforced.

**Deliverables:**
- Security headers middleware (CSP, HSTS, X-Frame-Options, etc.) on both frontend and backend
- Rate limiting (slowapi) on all API endpoints per 07-security-privacy.md §6
- Full CI pipeline running G1–G14 on every PR
- E2E suite: J1–J8 (label→PR, demo flow, review PR, auth, failed recovery, IDOR negative, unauth negative, SSE reconnect)
- axe accessibility scan on all routes
- Bundle size: marketing ≤40 KB, dashboard ≤100 KB, error pages ≤30 KB
- Visual regression baselines at 3 widths + dark mode

**Tickets:**
- T-21 · Security headers + rate limits — middleware, slowapi, CSP, HSTS
- T-22 · CI pipeline — all 14 gates wired in GitHub Actions
- T-23 · E2E suite — Playwright journeys J1–J8 with OAuth mock
- T-24 · Bundle + visual baselines — size script, screenshot baselines

**Risks:** Gate failures blocking merge; flaky E2E tests everyone learns to ignore; bundle size creeping over budget; axe violations on dynamic routes.

**Done when:** All 14 CI gates green on a `main` push; E2E J1–J8 pass on Chromium + WebKit; axe scan zero serious/critical on all 16 routes; bundle budgets met.

**Parallel:** Yes — QA leads E2E + hardening; the other three fix issues found in parallel.

**Runnable/demoable invariant:** Run `npm run check` + `npm run test:e2e` — all green; open any route → axe reports no serious/violations.

---

## Phase 7 · Content, SEO & polish

**Goal:** Copy from 02-content-seo.md live on every page; structured data, OG images, sitemap, robots, canonical URLs, unique title/meta per page; Lighthouse SEO ≥ 95.

**Deliverables:**
- Page copy (H1, subhead, CTAs, meta title/description) for all 10 pages per 02-content-seo.md
- JSON-LD structured data per page type (SoftwareApplication, FAQPage, Product, Organization, AboutPage)
- Dynamic `og:image` route (Next.js) + Twitter card `summary_large_image`
- `sitemap.xml`, `robots.txt`, canonical URLs, noindex on private pages (`/dashboard`, `/dashboard/runs/*`)
- Dark mode parity, real copy and imagery everywhere (dashboard screenshots only, no stock photography)

**Tickets:**
- T-25 · Page copy — all H1/subhead/CTA/microcopy from 02-content-seo.md
- T-26 · Structured data + OG — JSON-LD, og:image route, Twitter cards
- T-27 · sitemap/robots/canonical — SEO plumbing, noindex on auth-gated routes

**Risks:** SEO regressions from missing meta tags; copy drift from approved text; structured data validation errors; OG image generation failures.

**Done when:** Lighthouse SEO ≥ 95 on `/`, `/how-it-works`, `/demo`, `/security`, `/pricing`; rich-results test validates all JSON-LD; unique title + meta description on every page; `/dashboard` and `/dashboard/runs/*` are noindex.

**Parallel:** Yes — Pitch/QA owns content while the team fixes hardening bugs from Phase 6 in parallel.

**Runnable/demoable invariant:** Open `/` → view source shows unique `<title>`, `<meta description>`, canonical link, JSON-LD; Lighthouse SEO score ≥ 95.

---

## Phase 8 · Launch

**Goal:** Production go-live; everything verified on real phones and real network; rollback and restore drills passed; demo ready.

**Deliverables:**
- Vercel production deploy on `main` merge; backend on local Docker (demo host)
- Smoke test: `curl -sf https://<domain>/` → 200; `/auth/session` → 200 or 401 (not 5xx)
- Manual QA script (08-quality.md §9) executed on one Android phone (Chrome) and one iOS device (Safari)
- Backup drill: tarball of `apps/api/data/`, restore, verify 3 seeded runs visible (< 10 min)
- Rollback drill: `vercel rollback` + `docker compose` redeploy (< 5 min total)
- Incident runbook rehearsed (detect → triage → fix → post-mortem)
- Uptime monitor with alerts configured (UptimeRobot free or cron + curl)

**Tickets:**
- T-28 · Production deploy + smoke test — Vercel prod, backend restart, health checks
- T-29 · Real-phone QA sign-off — Android + iOS per 08-quality.md §9
- T-30 · Restore + rollback drills — backup tarball, restore < 10 min; rollback < 5 min

**Risks:** Production env mismatch (secrets missing); backend unreachable from Vercel; DNS propagation delay; demo fails mid-presentation due to LLM rate limits or sandbox crash.

**Done when:** `curl -sf https://<domain>/` → 200; smoke test passes; QA sign-off comment on the launch PR; restore drill < 10 min; rollback drill < 5 min.

**Parallel:** No — all hands on deck; this is the launch gate.

**Runnable/demoable invariant:** Production URL live; smoke test green; real-phone QA signed off.

---

## Phase 9 · Post-launch

**Goal:** Ops steady-state + demo reproducible on demand for the hackathon presentation.

**Deliverables:**
- Monitoring: uptime alerts, server error logs, real-user Web Vitals (self-hosted, no third-party scripts), LLM rate-limit alerts, Docker sandbox failure alerts
- Monthly maintenance cadence (09-operations.md §9): dependency updates, security audits, Lighthouse re-check, cost review, quarterly restore/rollback drills, secrets rotation review
- Demo rehearsal script: label 3 seeded issues live, verify ≥2 draft PRs with red→green proof, 3rd "couldn't reproduce", dashboard shows all 3 runs end-to-end
- Recorded backup run (in case LLM rate limits stall during live demo)

**Tickets:**
- T-31 · Monitoring + alerts — uptime monitor, error logging, Web Vitals, alert thresholds
- T-32 · Maintenance runbook — monthly/quarterly task list with owners
- T-33 · Demo rehearsal script — step-by-step for the 3-seeded-issue DoD + recorded backup

**Risks:** LLM rate limits during live demo; sandbox failure mid-presentation; monitoring gaps hiding a production outage.

**Done when:** Demo DoD reproducible on demand (2/3 seeded → draft PR red→green; 3rd "couldn't reproduce"); uptime monitor with alerts live; monthly maintenance runbook reviewed.

**Parallel:** Yes — Pitch/QA leads demo prep + monitoring; others on standby for fixes.

**Runnable/demoable invariant:** Run the demo rehearsal script end-to-end on the production URL; all 3 seeded runs visible on `/dashboard`; ≥2 draft PRs with red→green proof.

---

## Phase dependencies (critical path)

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
```

Phases 1, 2, 4, 5, 6, 7, 9 contain parallelizable sub-work (see table above). Phase 8 is serial.

## "Runnable and demoable" invariant check per phase

| Phase | Open this in a browser | Should see |
|-------|----------------------|------------|
| 0 | `localhost:3000` | Next.js shell |
| 1 | `localhost:3000` | Nav, dark mode, token-driven components in all 7 states |
| 2 | `localhost:3000/dashboard` | Signed-out redirect → `/auth/github` |
| 3 | All 16 routes | Correct state microcopy on every page |
| 4 | `localhost:3000/dashboard/runs/[runId]` | SSE timeline streaming 6 steps, red→green output |
| 5 | Preview URL | Live webhook-triggered run with SSE timeline |
| 6 | CI run on a PR | All 14 gates green |
| 7 | `https://<domain>/` | Lighthouse SEO ≥ 95, unique title/meta |
| 8 | `https://<domain>/` | Smoke test 200, real-phone QA signed off |
| 9 | Production URL | Demo DoD reproducible: 2/3 draft PRs red→green, 3rd "couldn't reproduce" |

## Risks register (hackathon-level)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Free-tier LLM rate limits stall mid-demo | High | High | Cache LLM responses for rehearsed issues; recorded backup run |
| Reproduction fails (env drift, flaky install) | Medium | High | Prebuilt Docker image with deps baked in; pinned versions |
| Wrong/overfitted fix | Medium | Medium | Full existing suite must pass; lower confidence on large diffs; human review gate |
| Sandbox escape / secret leakage | Low | High | `--network=none`, `--user=nonroot`, no host mounts, no tokens in container, 5-min timeout |
| Scope creep across 6 features in 48h | High | Medium | Build order is pipeline → sandbox → PR → issue comments → dashboard; dashboard can fall back to simple log view |
| "How is this different from Copilot/Devin?" | Medium | High | Pitch leads with red→green proof + mandatory human gate + ₹0 self-hostable |
