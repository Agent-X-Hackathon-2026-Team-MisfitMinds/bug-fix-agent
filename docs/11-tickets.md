# 11 · Feature Tickets
> What exactly do I ask the AI to build today?

_Think of it as: The daily work orders handed to the crew: small, specific, and checked before sign-off._

**Reads:** 10-plan.md + the docs each ticket cites · **Length:** grows per phase · **Tracks:** Sprint · Launch · Scale · **Sprint:** 8–15 tickets in build order.

Ticket template:
```
T-NN · Title
Why:        user value in one line
Context:    docs/xx.md § …
Task:       what to build
Accept:
  - [ ] …(include states, accessibility, errors)
Test:       unit / E2E to write
Depends:    T-…
Priority:   MUST | SHOULD | COULD    Size: S | M
```

Rules: Size S or M only; anything bigger is split. Criteria always include states, accessibility, and errors. One ticket = one focused AI session = one commit. Generated one phase at a time, never far ahead.

---

## Phase 0 · Foundation

### T-00 · Repo init
Why: A developer can clone the repo and run both web and API locally with one command.
Context: docs/05-architecture.md § Folder tree · docs/00-brief.md § Stack
Task: Create monorepo folders (`apps/web`, `apps/api`, `packages/shared`), `docker-compose.yml` (api + web + sandbox), `.env.example` with all required keys as placeholders, `.gitignore` excluding `.env`, `node_modules`, `__pycache__`, and a README with install/dev/check commands.
Accept:
- [ ] `npm ci` installs frontend deps; `pip install -r requirements.txt` installs backend deps
- [ ] `docker compose up` starts web (localhost:3000) and api (localhost:8000) without errors
- [ ] `.env` is git-ignored; `.env.example` lists every key from docs/05-architecture.md § Environment variables
Test: `docker compose up` → both services healthy; `git check-ignore .env` returns .env
Depends: none
Priority: MUST Size: S

### T-01 · CI pipeline
Why: Every change runs through the full gate stack before merge, so nothing ships broken.
Context: docs/08-quality.md § 5 CI gates · docs/09-operations.md § 2 CI/CD as steps
Task: GitHub Actions workflow with all 14 gates (G1–G14): tsc, eslint, ruff, mypy, vitest, pytest unit, pytest integration, Playwright E2E, axe, Lighthouse CI, bundle size, npm audit, pip audit, visual regression.
Accept:
- [ ] Lint + audit stage runs in parallel and blocks on any failure
- [ ] Unit + integration stage runs after lint, blocks on any failure
- [ ] Build stage runs after tests; E2E + visual + axe + Lighthouse run after build
- [ ] Any gate failure blocks merge to main
Test: Open a PR with a deliberate lint error → CI fails; fix → CI passes
Depends: T-00
Priority: MUST Size: M

### T-02 · Shared types
Why: Frontend and backend agree on the shape of Run, Step, Status, Confidence so neither side drifts.
Context: docs/05-architecture.md § packages/shared · docs/06-data-api.md § Tables
Task: Define shared types (TS + Python via JSON schema) for Run, Step, status enum, confidence enum; re-export in `apps/web/types/` and `apps/api/schemas.py`.
Accept:
- [ ] TypeScript type matches Pydantic schema field-for-field
- [ ] Status enum includes: pending, reproducing, fixing, verifying, completed, failed, could_not_reproduce
- [ ] Confidence enum includes: high, medium, low
Test: Unit test asserts a serialized Run matches both TS and Python schemas
Depends: T-00
Priority: MUST Size: S

---

## Phase 1 · Design system & shell

### T-03 · Design tokens
Why: Every colour, spacing, radius, and shadow comes from tokens so the UI stays consistent and dark-mode parity is enforceable.
Context: docs/04-design-system.md § Design tokens · STANDARDS.md § 6 Design
Task: Define `--ds-*` CSS variables in `app/globals.css` (light + `[data-theme="dark"]`) and configure `tailwind.config.js` with the complete theme.
Accept:
- [ ] No hardcoded colours, font sizes, spacing, radii, or shadows anywhere in components
- [ ] Light and dark themes both meet WCAG 2.2 AA contrast ratios from docs/04-design-system.md § WCAG
- [ ] `prefers-reduced-motion` sets all durations to 0
Test: Token lint passes; axe contrast check on all text/background pairs
Depends: T-00
Priority: MUST Size: S

### T-04 · Base components
Why: Buttons, cards, skeletons, empty states, and toasts are the building blocks every page reuses; each must support all 7 states.
Context: docs/04-design-system.md § Component specs · docs/03-app-flow.md § State tables
Task: Build button, card, skeleton, empty-state, toast, status-badge components with default/hover/focus-visible/active/disabled/loading/error states; touch targets ≥44px.
Accept:
- [ ] Every interactive component has visible focus ring (2px `--ds-border-focus`, 2px offset)
- [ ] All buttons ≥44×44px touch area
- [ ] Empty state renders correct microcopy from docs/03-app-flow.md
Test: Vitest unit tests for each component in all 7 states; axe on component variants
Depends: T-03
Priority: MUST Size: S

### T-05 · Nav shell + dark mode
Why: Visitors can move between pages and switch themes; the shell works at 360px+.
Context: docs/03-app-flow.md § Mermaid sitemap · docs/04-design-system.md § Nav
Task: Build responsive nav (logo, links, auth actions) + footer; dark mode toggle respecting system preference; single-column below 768px.
Accept:
- [ ] Nav works keyboard-only (Tab/Enter/Escape)
- [ ] Dark mode toggles and persists; no white flashes on theme switch
- [ ] Layout has no horizontal scroll at 360px width
Test: Playwright E2E journey navigating all marketing links; axe on nav at 360px
Depends: T-04
Priority: MUST Size: S

---

## Phase 2 · Data & auth

### T-06 · Data repo + schemas
Why: All run data flows through a single repository interface with strict validation, so the API contract in 06-data-api.md is never violated.
Context: docs/06-data-api.md § Tables · docs/06-data-api.md § Standard error format · docs/07-security-privacy.md § 5
Task: JSON-file repository interface (`apps/api/data/`) with in-memory backend; Pydantic models for all request/response shapes; standard `{ error: { code, message, details } }` error format.
Accept:
- [ ] Pydantic validation rejects invalid `run_id`, `limit` (1–100), `cursor`, `status` enum
- [ ] Every API error returns the standard error shape with correct HTTP status
- [ ] Ownership filter applied on every query (installation_id + triggered_by)
Test: pytest unit tests for schemas and run_repo CRUD with ownership filter
Depends: T-02
Priority: MUST Size: S

### T-07 · API routes
Why: The frontend can fetch runs, stream events, and retry runs through well-defined, rate-limited endpoints.
Context: docs/06-data-api.md § API routes · docs/07-security-privacy.md § 6 Rate limits
Task: Implement GET /runs, GET /runs/{run_id}, GET /runs/{run_id}/events (SSE), POST /runs/{run_id}/retry, GET /auth/session, POST /auth/logout with rate limiting per endpoint.
Accept:
- [ ] `GET /runs` returns only caller's runs with cursor pagination
- [ ] `GET /runs/{run_id}` returns 404 (not 403) for other users' runs (IDOR prevention)
- [ ] `POST /runs/{run_id}/retry` requires Idempotency-Key header; rejects non-retryable states with 409
- [ ] Rate limits enforced: 60/min per user on GET routes, 5/min per run on retry
Test: pytest integration tests for all routes; rate-limit test (61 requests → 429)
Depends: T-06, T-08
Priority: MUST Size: M

### T-08 · GitHub OAuth + sessions
Why: Users sign in with GitHub (no passwords, no PII); sessions are secure and expire after 24h.
Context: docs/03-app-flow.md § Auth flow · docs/07-security-privacy.md § 2 · docs/05-architecture.md § Environment variables
Task: Implement `/auth/github` redirect, `/auth/callback` token exchange, `__Host-session_id` cookie (HttpOnly, Secure, SameSite=Lax, 24h), session middleware, sign-out.
Accept:
- [ ] Session cookie has HttpOnly, Secure, SameSite=Lax flags
- [ ] Session expires after 24h absolute (no sliding window)
- [ ] Invalid/missing cookie redirects to `/auth/github`; no dashboard content flashes
- [ ] GitHub access token encrypted at rest (AES-256-GCM with SESSION_SECRET)
Test: Playwright E2E J4 (sign in/sign out); unit tests for oauth.py and middleware
Depends: T-06
Priority: MUST Size: S

---

## Phase 3 · Core pages & states

### T-09 · Marketing pages
Why: Visitors can learn about the product and convert on any static page.
Context: docs/02-content-seo.md § Page inventory · docs/03-app-flow.md § Per-page specs · docs/05-architecture.md § Rendering and caching
Task: Build `/`, `/how-it-works`, `/demo`, `/security`, `/pricing`, `/about`, `/changelog`, `/privacy`, `/terms` as SSG/ISR with nav, footer, hero, CTAs, and page-specific components.
Accept:
- [ ] Each page has unique title + meta description from docs/02-content-seo.md
- [ ] All pages render loading/error/offline states (static pages only)
- [ ] Images via `next/image` with dimensions; no layout shift
- [ ] Cache-Control headers set per docs/05-architecture.md § Caching headers
Test: axe scan on all public routes; Lighthouse SEO ≥ 95 on `/`
Depends: T-05
Priority: MUST Size: M

### T-10 · Auth routes
Why: Sign-in and callback are redirect-only pages that set the session cookie securely.
Context: docs/03-app-flow.md § /auth/github · docs/03-app-flow.md § /auth/callback · docs/07-security-privacy.md § 2.3
Task: Implement `/auth/github` (redirect to GitHub OAuth with state CSRF) and `/auth/callback` (exchange code, set cookie, redirect to `/dashboard` or `/` on error).
Accept:
- [ ] OAuth state parameter verified against CSRF cookie (mismatch → 401)
- [ ] Callback sets `__Host-session_id` cookie then redirects to `/dashboard`
- [ ] Error state shows human-readable message, no stack traces
Test: Playwright E2E J4; unit test for state verification
Depends: T-08
Priority: MUST Size: S

### T-11 · Dashboard + run detail
Why: Signed-in users see their runs list and can open any run to view the SSE timeline, red→green output, root cause, and confidence.
Context: docs/03-app-flow.md § /dashboard · docs/03-app-flow.md § /dashboard/runs/[runId] · docs/03-app-flow.md § State tables
Task: Build runs list table (loading/empty/error/success/partial/offline/signed-out/no-permission) and run detail page with 6-step SSE timeline, test output block, root-cause, confidence badge, "View draft PR" button.
Accept:
- [ ] Every state has exact microcopy from docs/03-app-flow.md state tables
- [ ] SSE timeline streams step events; reconnects without duplicate steps
- [ ] Forms keep input on error; retry button disabled during active run
- [ ] Ownership enforced: user cannot view another user's run detail
Test: Playwright E2E J2, J3, J5; axe on dashboard and run detail
Depends: T-07, T-10, T-05
Priority: MUST Size: M

### T-12 · Error pages + SSE client
Why: Users never hit a dead end; errors show a way forward and the SSE client recovers from network drops.
Context: docs/03-app-flow.md § Error pages · docs/03-app-flow.md § Form fields and validation · docs/04-design-system.md § Empty state
Task: Build `/404`, `/500`, `/maintenance` with helpful microcopy and buttons; SSE client (`lib/sse.ts`) with connect/reconnect/parse step events.
Accept:
- [ ] `/404` shows "Page not found" + "Go home" button; no stack trace
- [ ] `/500` shows "Something went wrong" + "Try again"; no internal details exposed
- [ ] SSE client reconnects after offline period; no duplicate steps
- [ ] Retry button shows "You're offline" when no network
Test: Vitest for SSE parser; E2E J8 (SSE reconnect); manual check of error pages
Depends: T-05, T-04
Priority: MUST Size: S

---

## Phase 4 · Core features

### T-13 · LangGraph pipeline
Why: The agent reads an issue, reproduces the bug, diagnoses, fixes, verifies, and opens a draft PR with stateful retry/checkpoint.
Context: docs/01-prd.md § Features MUST · docs/00-brief.md § Must-have features · docs/05-architecture.md § Agent orchestration
Task: Implement LangGraph graph: Read → Reproduce → Diagnose → Fix → Verify → PR; each step function isolated with mocked LLM/Docker for unit tests.
Accept:
- [ ] Each step reports status (pending/running/completed/failed) via SSE
- [ ] Pipeline checkpoints state so a failed step can resume
- [ ] Fix only proceeds if reproduction test failed before and passes after
- [ ] Confidence score (high/medium/low) with reasons assigned on completion
Test: pytest unit tests for each step function (mocked LLM, mocked Docker)
Depends: T-06, T-14, T-15
Priority: MUST Size: M

### T-14 · Docker sandbox
Why: Untrusted repo code runs in an isolated container with resource limits so the host is never compromised.
Context: docs/01-prd.md § Features MUST · docs/00-brief.md § Sandboxed code execution · docs/05-architecture.md § Sandbox · docs/07-security-privacy.md § 1.3
Task: Docker run wrapper with `--network=none` after dep install, `--user=nonroot`, `--memory`, `--cpus`, no host mounts, no tokens inside container, 5-minute timeout.
Accept:
- [ ] `build_docker_cmd()` includes `--network=none`, `--user=nonroot`, `--memory`, `--cpus`
- [ ] Container startup failure surfaces "reproduction failed — environment issue"
- [ ] No GitHub token, LLM key, or webhook secret enters the container
- [ ] Sandbox times out at 5 minutes; reports timeout on dashboard
Test: pytest unit test for `build_docker_cmd()` flags; integration test for timeout
Depends: T-06
Priority: MUST Size: M

### T-15 · LLM + caching
Why: The agent reasons about bugs using cached LLM responses to stay within free-tier rate limits.
Context: docs/01-prd.md § Features SHOULD · docs/00-brief.md § Risks · docs/06-data-api.md § llm_cache
Task: LLM call wrapper with cache key = SHA-256(issue_title + issue_body), rate-limit retry, graceful "couldn't process — LLM rate limit" fallback.
Accept:
- [ ] Cache hit returns stored response without calling LLM API
- [ ] Cache miss calls LLM and stores response with 24h TTL
- [ ] Rate-limit error posts "couldn't process" comment and fails gracefully
- [ ] Cache key cannot be poisoned by user-controlled issue text
Test: pytest unit tests for cache hit/miss/rate-limit retry; `hash_cache_key()` deterministic
Depends: T-06
Priority: SHOULD Size: S

### T-16 · Webhook handler
Why: Adding the `agent-fix` label to an issue starts the pipeline automatically — the single user action.
Context: docs/01-prd.md § Features MUST · docs/03-app-flow.md Journey 1 · docs/06-data-api.md § POST /webhooks/github · docs/07-security-privacy.md § 1.3
Task: `POST /webhooks/github` verifies `X-Hub-Signature-256`, dedups by `X-GitHub-Delivery`, detects `agent-fix` label, creates run, queues pipeline.
Accept:
- [ ] Valid webhook → run created; returns 200 with delivery_id
- [ ] Invalid signature → 401; missing headers → 400; duplicate delivery → 409
- [ ] Only `issues.labeled` or `issues.opened` carrying `label.name == "agent-fix"` triggers a run
- [ ] Webhook body never rendered; only extracted fields stored
Test: pytest integration tests for webhook (valid/invalid/duplicate/missing); signature helper test
Depends: T-06, T-13
Priority: MUST Size: S

### T-17 · Seeded demo repo
Why: The hackathon demo needs 3 deterministic Python bugs so judges can see red→green proof reliably.
Context: docs/00-brief.md § Demo definition of done · docs/06-data-api.md § Seed data · docs/01-prd.md § MVP scope
Task: Create seeded Python repo with 3 deterministic bugs (off-by-one, wrong condition, missing null check), known fixes, and pre-written reproduction tests.
Accept:
- [ ] Issue #1 (off-by-one): red→green fix achievable; confidence high
- [ ] Issue #2 (wrong condition): red→green fix achievable; confidence medium
- [ ] Issue #3 (missing null check): honest "couldn't reproduce"; confidence null
- [ ] Prebuilt Docker image has dependencies baked in; versions pinned
Test: Manual demo run labels all 3 issues; ≥2 produce draft PRs with red→green proof
Depends: T-14, T-13
Priority: MUST Size: S

---

## Phase 5 · Integrations

### T-18 · GitHub App + webhook
Why: The app receives real webhooks from GitHub so labeling an issue triggers the pipeline end-to-end.
Context: docs/05-architecture.md § Third-party services · docs/09-operations.md § 1 Environments · docs/07-security-privacy.md § 9 Secret handling
Task: Register GitHub App (client ID, private key, webhook secret, `agent-fix` label scope); set up smee.io/ngrok tunnel for local dev; store secrets server-only.
Accept:
- [ ] GitHub App installed on seeded demo repo
- [ ] Webhook secret verified on every incoming webhook
- [ ] Secrets in `.env` (git-ignored); never in `NEXT_PUBLIC_*` or logs
- [ ] Webhook forwarding tunnel reachable from public internet
Test: Send test webhook from GitHub → FastAPI receives and returns 200
Depends: T-16, T-08
Priority: MUST Size: S

### T-19 · Vercel deploy + env
Why: Frontend deploys automatically on PRs (preview) and `main` (production) with correct env vars per environment.
Context: docs/05-architecture.md § Frontend hosting · docs/09-operations.md § 1 · docs/09-operations.md § 2 Stage 5
Task: Connect repo to Vercel; configure preview deploy on every PR and production deploy on `main`; inject env vars per environment table in 09-operations.md § 1.
Accept:
- [ ] `NEXT_PUBLIC_APP_URL` differs per environment (localhost / preview / production domain)
- [ ] `NEXT_PUBLIC_API_URL` points to correct backend per environment
- [ ] No secrets in `NEXT_PUBLIC_*` variables
- [ ] Production deploy triggered only on `main` merge
Test: `curl -sf https://<preview-url>/` returns 200; preview env vars match table
Depends: T-00, T-09
Priority: MUST Size: S

### T-20 · SSE bridge
Why: The Vercel-hosted frontend can stream live timeline events from the backend across origins.
Context: docs/05-architecture.md § Real-time · docs/03-app-flow.md Journey 2 · docs/09-operations.md § 2 Stage 5
Task: Wire EventSource from Next.js frontend to FastAPI SSE endpoint; handle cross-origin `connect-src` in CSP; reconnect on network drop.
Accept:
- [ ] SSE stream opens from preview URL to backend origin
- [ ] Step events render in order on run detail page
- [ ] CSP `connect-src` includes backend origin; no `'unsafe-eval'`
- [ ] Reconnection indicator shown then hidden on recovery
Test: Playwright E2E J2, J8; manual check on preview URL
Depends: T-07, T-19, T-05
Priority: MUST Size: S

---

## Phase 6 · Hardening

### T-21 · Security headers + rate limits
Why: OWASP Top 10 protections are enforced via headers and rate limits on every response and endpoint.
Context: docs/07-security-privacy.md § 6 Rate limits · docs/07-security-privacy.md § 7 Security headers · STANDARS.md § 1 Security
Task: Add security headers middleware (CSP, HSTS, X-Frame-Options, etc.) on frontend and backend; rate limiting (slowapi) on all API endpoints.
Accept:
- [ ] CSP: `default-src 'self'`, no `'unsafe-eval'`, `frame-ancestors 'none'`
- [ ] HSTS: `max-age=63072000; includeSubDomains; preload`
- [ ] All endpoints return security headers; rate limits return 429 + Retry-After
- [ ] npm audit + pip audit: zero High/Critical
Test: Headers scan on production URL; rate-limit integration tests
Depends: T-07, T-19
Priority: MUST Size: S

### T-22 · CI pipeline
Why: The full gate stack runs on every PR so nothing merges broken.
Context: docs/08-quality.md § 5 CI gates · docs/09-operations.md § 2 CI/CD as steps
Task: Wire all 14 gates (G1–G14) into GitHub Actions; any failure blocks merge.
Accept:
- [ ] G1–G14 all defined with exact commands and thresholds
- [ ] Build stage required before E2E; E2E required before Lighthouse
- [ ] Visual regression is warning-only (manual approval to update baselines)
- [ ] Lighthouse CI thresholds met on preview routes
Test: Open PR → all gates run; deliberate failure blocks merge
Depends: T-01
Priority: MUST Size: M

### T-23 · E2E suite
Why: Critical journeys are covered end-to-end so the money path (label → draft PR) never regresses.
Context: docs/08-quality.md § 3 Critical journeys · docs/03-app-flow.md § Critical journeys · STANDARS.md § 9 Code quality
Task: Playwright E2E tests J1–J8 (label→PR, demo flow, review PR, auth, failed recovery, IDOR negative, unauth negative, SSE reconnect) with OAuth mock.
Accept:
- [ ] J1: label → draft PR with red→green proof
- [ ] J2: demo flow shows all 6 SSE steps + red→green output
- [ ] J6: IDOR attempt returns 404, no data leaked
- [ ] J7: unauthenticated access to `/dashboard` redirects, no flash
- [ ] All journeys pass on Chromium + WebKit
Test: `npx playwright test --reporter=html` all pass
Depends: T-08, T-11, T-13, T-16
Priority: MUST Size: M

### T-24 · Bundle + visual baselines
Why: Routes stay within JS budgets and visual regressions are caught before merge.
Context: docs/05-architecture.md § Performance budgets · docs/08-quality.md § 5.3 Bundle size · docs/08-quality.md § 8 Visual regression
Task: Bundle size check script (marketing ≤40 KB, dashboard ≤100 KB, error pages ≤30 KB); Playwright screenshot baselines at 360/768/1280px + dark mode.
Accept:
- [ ] No route exceeds its JS budget
- [ ] Visual baselines committed for all key pages at 3 widths + dark mode
- [ ] Visual diff threshold: maxDiffPixelRatio 0.01
Test: `bash scripts/check-bundle-size.sh` passes; `npx playwright test e2e/visual/` matches baselines
Depends: T-09, T-11
Priority: SHOULD Size: S

---

## Phase 7 · Content, SEO & polish

### T-25 · Page copy
Why: Every page has approved, conversion-oriented copy matching the voice/tone in 02-content-seo.md.
Context: docs/02-content-seo.md § Page copy · docs/02-content-seo.md § Voice and tone
Task: Write H1, subhead, CTAs, meta title (≤60 chars), meta description (≤155 chars) for all 10 pages; no hype words, no false autonomy claims.
Accept:
- [ ] Each page has unique title + meta description
- [ ] Copy avoids banned words ("revolutionary", "magic", "autonomous", "kills triage")
- [ ] Primary conversion goal clear on every page (add `agent-fix` label or view demo)
- [ ] Microcopy matches docs/03-app-flow.md state tables exactly
Test: Manual review against docs/02-content-seo.md; Lighthouse SEO checks meta tags
Depends: T-09
Priority: MUST Size: S

### T-26 · Structured data + OG
Why: Search engines and social previews understand each page; OG images make links compelling.
Context: docs/02-content-seo.md § Structured data · docs/02-content-seo.md § Open Graph plan · docs/04-design-system.md § Iconography and imagery rules
Task: JSON-LD per page type; dynamic `og:image` route (Next.js); Twitter card `summary_large_image`; dashboard screenshots only (no stock photography).
Accept:
- [ ] `/` has SoftwareApplication + Organization JSON-LD
- [ ] `/pricing` has Product JSON-LD with price ₹0
- [ ] og:image generates dynamically; og:title/og:description set on every page
- [ ] Rich-results test validates all JSON-LD
Test: Rich-results validation; manual OG tag check on each page
Depends: T-09, T-25
Priority: SHOULD Size: S

### T-27 · sitemap/robots/canonical
Why: Crawlers index public pages correctly; private pages stay out of search results.
Context: docs/02-content-seo.md § Internal links · STANDARS.md § 7 Discoverability · docs/09-operations.md § 8 Domain, DNS
Task: Generate `sitemap.xml` and `robots.txt`; canonical URLs on every page; noindex on `/dashboard` and `/dashboard/runs/*`.
Accept:
- [ ] sitemap.xml lists all public marketing pages
- [ ] robots.txt allows public, disallows private routes
- [ ] Canonical URL present on every page
- [ ] `/dashboard` and `/dashboard/runs/*` have noindex
Test: `curl` sitemap.xml and robots.txt; check noindex meta on dashboard
Depends: T-09, T-11
Priority: SHOULD Size: S

---

## Phase 8 · Launch

### T-28 · Production deploy + smoke test
Why: The site is live on production and basic health checks pass.
Context: docs/09-operations.md § 2 Stage 5 · docs/09-operations.md § 2 Stage 6 · docs/05-architecture.md § Frontend hosting
Task: Vercel production deploy on `main` merge; backend restart on Docker host; health checks (`curl -sf https://<domain>/` → 200; `/auth/session` → 200 or 401).
Accept:
- [ ] Production URL returns 200 on home page
- [ ] `/auth/session` returns 200 or 401 (not 5xx)
- [ ] Backend reachable from Vercel frontend
- [ ] Smoke test documented and repeatable
Test: `curl -sf https://<domain>/` → 200; smoke test passes
Depends: T-19, T-18, T-22
Priority: MUST Size: S

### T-29 · Real-phone QA sign-off
Why: The site works on real phones, not just desktop browsers.
Context: docs/08-quality.md § 9 Manual QA script · STANDARS.md § 5 Experience
Task: Execute QA script on one Android (Chrome) and one iOS (Safari) at 360px + desktop, on WiFi and slow 3G; record pass/fail per step.
Accept:
- [ ] All marketing pages load ≤3s on 3G; no horizontal scroll
- [ ] Auth flow completes end-to-end on real phone
- [ ] Dashboard SSE timeline works on mobile
- [ ] Error states (404, offline) handled gracefully
Test: QA sign-off comment on launch PR with device/OS/browser/table
Depends: T-28
Priority: MUST Size: S

### T-30 · Restore + rollback drills
Why: If production breaks, we can restore data and rollback deploy in under 5 minutes.
Context: docs/09-operations.md § 5 Backups · docs/09-operations.md § 6 Rollback · STANDARS.md § 8 Reliability
Task: Tarball backup of `apps/api/data/`; restore drill (<10 min); rollback drill (`vercel rollback` + `docker compose` redeploy, <5 min total).
Accept:
- [ ] Restore: wipe data, restore tarball, verify 3 seeded runs visible on `/dashboard`
- [ ] Rollback: revert to previous deploy; site functional
- [ ] Total rollback time < 5 minutes
- [ ] Drill documented with timestamps
Test: Run restore drill; run rollback drill; measure both
Depends: T-28
Priority: MUST Size: S

---

## Phase 9 · Post-launch

### T-31 · Monitoring + alerts
Why: Production issues are detected before users report them, without third-party scripts.
Context: docs/09-operations.md § 4 Monitoring · docs/05-architecture.md § Third-party services · STANDARS.md § 10 Observability
Task: Configure uptime monitor (UptimeRobot free or cron + curl), error log review, self-hosted real-user Web Vitals, LLM rate-limit alerts, Docker sandbox failure alerts.
Accept:
- [ ] Uptime alert triggers if site down > 2 min
- [ ] 5xx spike > 5/min triggers investigation
- [ ] Web Vitals alerts: p75 LCP > 2.5s, INP > 200ms, CLS > 0.1
- [ ] No PII in any log or alert payload
Test: Deliberate test error → appears in logs; uptime monitor configured
Depends: T-28
Priority: SHOULD Size: S

### T-32 · Maintenance runbook
Why: Monthly/quarterly ops tasks have owners and evidence so the site stays healthy.
Context: docs/09-operations.md § 9 Monthly maintenance · STANDARS.md Launch gates
Task: Document dependency updates, security audits, Lighthouse re-checks, cost reviews, restore/rollback drills, secrets rotation with cadence and owners.
Accept:
- [ ] Monthly task list with owner and evidence gate for each
- [ ] Quarterly restore drill scheduled (<10 min target)
- [ ] Quarterly rollback drill scheduled (<5 min target)
- [ ] Secrets rotation review scheduled quarterly
Test: Runbook reviewed by team; first monthly audit completed
Depends: T-30, T-31
Priority: SHOULD Size: S

### T-33 · Demo rehearsal script
Why: The hackathon demo is reproducible on demand — the actual DoD judges will watch.
Context: docs/00-brief.md § Demo definition of done · docs/01-prd.md § Success metrics · docs/03-app-flow.md Journey 2
Task: Step-by-step script to label 3 seeded issues live; verify ≥2 draft PRs with red→green proof; 3rd ends "couldn't reproduce"; dashboard shows all 3 runs end-to-end; recorded backup run ready.
Accept:
- [ ] Demo DoD met: ≥2 of 3 seeded issues → draft PR with red→green proof
- [ ] 3rd issue posts honest "couldn't reproduce" comment
- [ ] Dashboard shows all 3 runs with SSE timeline
- [ ] Recorded backup run available if LLM rate limits stall
Test: Run full demo rehearsal on production URL; all assertions pass
Depends: T-17, T-28, T-13
Priority: MUST Size: M

---

## Dependency graph (critical path)

```
T-00 → T-01 → T-02
T-00 → T-03 → T-04 → T-05
T-02 → T-06 → T-07 → T-08 → T-10 → T-11
T-06 → T-13 → T-16 → T-18 → T-19 → T-20
T-14 → T-17 (seeded demo)
T-11 → T-23 (E2E) → T-22 (CI green)
T-09 → T-25 → T-26 → T-27
T-28 → T-29 → T-30 → T-31 → T-32
T-17 → T-33 (demo rehearsal)
```

## Parallel-friendly ticket clusters

| Cluster | Tickets | Can run in parallel |
|---------|---------|---------------------|
| Repo + CI | T-00, T-01, T-02 | Yes (T-00 first) |
| UI shell | T-03, T-04, T-05 | Yes (T-03 first) |
| Data + auth | T-06, T-07, T-08 | Yes (T-06 first) |
| Pages | T-09, T-10, T-11, T-12 | Yes (after T-05, T-08) |
| Core features | T-13, T-14, T-15, T-16, T-17 | Yes (after T-06; T-13/14/16 depend on T-06) |
| Integrations | T-18, T-19, T-20 | Yes (after T-16, T-19) |
| Hardening | T-21, T-22, T-23, T-24 | Yes (after respective deps) |
| Content/SEO | T-25, T-26, T-27 | Yes (after T-09) |
| Launch | T-28, T-29, T-30 | Serial (T-28 first) |
| Post-launch | T-31, T-32, T-33 | Yes (after T-28; T-33 after T-17, T-28) |

## Size policy
All tickets are S or M. No ticket exceeds one focused session. If a ticket looks larger than M, split it (e.g., T-11 dashboard could split into runs list and run detail; T-23 E2E could split into J1–J4 and J5–J8).
