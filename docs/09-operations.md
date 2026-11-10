# 09 — Operations: Bug-Fix Agent

Site-reliability specification. Every environment, deploy step, alert threshold, backup, and rollback target is concrete and enforceable — no "looks fine" allowed.

**Reads:** 05-architecture.md (stack, budgets, env vars, ADRs) · 08-quality.md (CI gates G1–G14) · STANDARDS.md (launch gates) · 06-data-api.md (API contract) · 07-security-privacy.md (security controls) · **Length:** 2–3 pages · **Tracks:** Launch · Scale · **Sprint:** Skip the doc; keep one production deploy and one smoke test.

---

## 1 · Environments and how config differs

| Environment | Purpose | Frontend | Backend | Data | Config source | Notes |
|-------------|---------|----------|---------|------|---------------|-------|
| **Local** | Developer workstation | `npm run dev` (localhost:3000) | FastAPI `uvicorn` (localhost:8000) + Docker sandbox | Transient JSON files in `apps/api/data/` | `.env` (git-ignored) | `docker-compose.yml` brings up api + web + sandbox |
| **Preview** | PR validation | Vercel preview deploy on every PR | ngrok tunnel to local FastAPI (or a preview FastAPI instance) | Transient JSON | Vercel env vars + `.env.example` values | Short-lived; torn down with PR |
| **Production** | Live site | Vercel production on `main` merge | FastAPI on local Docker (host where the demo runs) | Transient JSON | Production env vars (from `.env.example` + real secrets) | ₹0; no managed DB |
| **Staging** | Not used | — | — | — | — | Explicitly out of scope for v1; preview covers staging |

### Config differences by environment

| Variable | Local | Preview | Production | Visibility |
|----------|-------|---------|------------|------------|
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | `https://<pr>.vercel.app` | Canonical domain | Public |
| `NEXT_PUBLIC_API_URL` | relative `/api` | ngrok URL | absolute backend URL | Public |
| `NEXT_PUBLIC_GITHUB_APP_ID` | real App ID | real App ID | real App ID | Public |
| `GITHUB_APP_ID` | real | real | real | Server-only |
| `GITHUB_APP_CLIENT_SECRET` | real | real | real | Server-only |
| `GITHUB_APP_PRIVATE_KEY` | real | real | real | Server-only |
| `GITHUB_APP_WEBHOOK_SECRET` | real | real | real | Server-only |
| `LLM_API_KEY` | real / cached | real / cached | real / cached | Server-only |
| `SESSION_SECRET` | real | real | real | Server-only |
| `MAINTENANCE_MODE` | unset | unset | unset (set `"true"` only during maintenance) | Server-only |

Rules (from `05-architecture.md`): no secrets in `NEXT_PUBLIC_*` variables; `.env` is git-ignored; `.env.example` lists every required key with placeholder values.

---

## 2 · CI/CD as steps

The pipeline below extends the CI gates already defined in `08-quality.md` (§5, gates G1–G14). Any gate failure blocks the deploy. Preview deploys run on every PR (Vercel automatic) without merging.

### Stage 1 — Lint + audit (parallel)
- G1 TypeScript: `npx tsc --noEmit` — zero errors
- G2 ESLint: `npx eslint . --max-warnings=0` — zero errors, zero warnings
- G3 Python lint: `ruff check apps/api/` — zero errors
- G4 Python types: `mypy --strict apps/api/` — zero errors
- G12 Node audit: `npm audit --audit-level=high` — zero high/critical
- G13 Python audit: `pip audit --strict --desc` — zero high/critical

### Stage 2 — Unit + integration tests (parallel)
- G5 Frontend unit: `npx vitest run --reporter=verbose` — all pass
- G6 Backend unit: `pytest tests/unit/ -v` — all pass
- G7 Backend integration: `pytest tests/integration/ -v` — all pass

### Stage 3 — Build
- G11: `npx next build` + `bash scripts/check-bundle-size.sh` — marketing ≤ 40 KB, dashboard ≤ 100 KB, error pages ≤ 30 KB initial JS

### Stage 4 — E2E + visual + accessibility + Lighthouse
- G8 Playwright E2E: `npx playwright test --reporter=html` — all pass (Chromium + WebKit)
- G9 axe a11y: `npx playwright test e2e/a11y/` — zero serious or critical violations
- G14 Visual regression: `npx playwright test e2e/visual/` — all screenshots match baseline (warning-only; manual approval to update)
- G10 Lighthouse CI: `npx lhci autorun` — Perf ≥ 90, A11y ≥ 95, BP ≥ 90, SEO ≥ 90 on preview routes

### Stage 5 — Deploy (main branch only)
1. Vercel production deploy for `apps/web/` frontend
2. Backend restart: `docker compose down && docker compose up -d` (or redeploy previous image tag)
3. Verify health: `curl -sf https://<domain>/` returns 200; `curl -sf https://<domain>/auth/session` returns 200 or 401 (not 5xx)

### Stage 6 — Smoke test
- Hit production home, dashboard (signed-out redirect), and a seeded run detail page
- Confirm Lighthouse CI passes on live URL (run G10 against production if budget allows)

---

## 3 · Database migration process

Per ADR-006 in `05-architecture.md`, **v1 uses no database** — run logs are transient JSON files / in-memory behind a repository interface in `apps/api/data/`.

Consequences for operations:
- **No SQL migrations run in CI/CD.** There is no `db upgrade head` step.
- The logical schema in `06-data-api.md` (`runs`, `run_steps`, `llm_cache`, `webhook_events`, `sessions`) is the **data contract**.
- Any change to table/column names or the JSON file structure is a **breaking contract change** requiring:
  1. Update `06-data-api.md` first (per AGENTS.md: "When a decision changes, update the relevant file in `docs/` first").
  2. A one-time data migration script (if persisted JSON exists) or an explicit note that transient data is acceptable to lose.
  3. Backward-compatible reads during rollout (old and new shapes both readable).
- If a database is added later (ADR-006 reversibility is "High"), add Alembic/SQLModel migrations here and gate them behind `db upgrade head` in the deploy step.

---

## 4 · Monitoring — errors, uptime, real-user Web Vitals, logs without PII

Constraint: ₹0 budget and "zero third-party scripts" per `05-architecture.md`. No analytics, no tracking, no error-reporting SDKs. Monitoring is self-hosted / minimal.

| Signal | Tool | Source | Alert threshold | Response action |
|--------|------|--------|-----------------|-----------------|
| **Uptime** | UptimeRobot (free) or cron + `curl` | `https://<domain>/` | Down > 2 min | Page on-call; check Vercel status |
| **Server errors** | FastAPI access/error logs + Vercel function logs | `apps/api/` stdout/stderr; Vercel dashboard | Any 5xx > 5/min, or repeated 401/403 on `/webhooks/github` | Investigate auth / webhook secret |
| **Real-user Web Vitals** | Self-hosted — Next.js `web-vitals` logged to a first-party endpoint (or Vercel Analytics if enabled) | Browser navigation timing | p75 LCP > 2.5s, INP > 200ms, CLS > 0.1 | Investigate route JS / bundle size |
| **LLM rate limit** | App logs | `apps/api/pipeline/llm.py` cache miss + HTTP 429 | > 10 rate-limit errors / hour | Fall back to cached/demo runs |
| **Docker sandbox failure** | App logs | `apps/api/pipeline/sandbox.py` container exit code | Any container startup failure > 2/min | Check Docker daemon, image, `--memory`/`--cpus` limits |
| **Webhook failures** | App logs | `POST /webhooks/github` 401/409 | Invalid-signature burst | Rotate `GITHUB_APP_WEBHOOK_SECRET` if compromised |

**Logs rule — no PII:** Never log GitHub tokens, emails, issue bodies, PR diffs, or user data. Log only status codes, run IDs (not issue text), error classes, and timestamps.

---

## 5 · Backups and restore drill

Data is transient JSON files (ADR-006). Backup scope is small.

### What to back up
- `apps/api/data/` JSON run logs
- `.env.example` (template only — never real `.env` with secrets)
- `docker-compose.yml`
- `docs/` (this repository)

### Frequency and retention
- **Frequency:** Daily, and before every demo
- **Retention:** 7 days (demo-scoped; transient data is acceptable to lose after that)
- **Method:** Dated tarball of `apps/api/data/` copied off the host

### Restore drill (quarterly, and pre-launch)
1. Take the latest tarball of `apps/api/data/`
2. Wipe `apps/api/data/`
3. Restore the tarball
4. Run `pytest tests/integration/`
5. Run E2E journey J2 (live demo flow) against the restored data
6. Confirm the 3 seeded runs are visible on `/dashboard`
7. Document time-to-restore; target **< 10 minutes**

---

## 6 · Rollback in under 5 minutes

| Component | Rollback mechanism | Target time |
|-----------|-------------------|-------------|
| Frontend (Vercel) | `vercel rollback` or redeploy previous deployment from Vercel dashboard | < 2 min |
| Backend (Docker) | `docker compose down && git stash && docker compose up -d` (or redeploy previous image tag) | < 3 min |
| Data (JSON files) | Restore `apps/api/data/` from backup tarball | < 2 min |
| **Total rollback** | | **< 5 min** |

Rollback triggers: any production gate failure post-deploy, P1 incident, or severe Web Vitals regression. Rollback drill is run quarterly alongside the restore drill.

---

## 7 · Incident runbook: detect → triage → fix → post-mortem

### Detect
Sources: uptime alert, error-log spike, Web Vitals degradation, user report, or failed CI gate on `main`.

### Triage (target ≤ 15 minutes)
1. Confirm scope: frontend only, backend only, or both.
2. Check Vercel deployment status and Docker container logs.
3. Identify the changed commit (the last deploy).
4. Assign an incident owner and severity:
   - **P1:** Site down / core journey broken (label → draft PR)
   - **P2:** A journey degraded (SSE timeline, dashboard)
   - **P3:** Minor UI or perf regression

### Fix
1. **First response:** if a bad deploy, rollback (per §6) before debugging live.
2. **Config issue:** verify env vars match `.env.example`; confirm no secrets leaked into `NEXT_PUBLIC_*` or logs.
3. **Code issue:** hotfix on a branch, run the full CI gates (G1–G14), fast-follow deploy.
4. Communicate status on the PR/issue.

### Post-mortem (within 24 hours for P1)
- Timeline: detect → triage → fix → recover
- Root cause (5 whys)
- Action items with owners and due dates
- Update `docs/` if a decision changed (per AGENTS.md non-negotiable)

---

## 8 · Domain, DNS, and email deliverability

### Domain
- Custom domain on Vercel (or `<project>.vercel.app` if strict ₹0)
- DNS: Vercel-managed or Cloudflare; A/CNAME records point to Vercel

### Email deliverability
The product sends **no transactional email** (no sign-up, no contact form, no notifications per `03-app-flow.md`). If outbound email is ever added:

| Record | Value | Purpose |
|--------|-------|---------|
| **SPF** | `v=spf1 include:_spf.google.com ~all` (or provider-specific) | Authorize mail senders |
| **DKIM** | Enabled via email provider; public key published as DNS TXT | Cryptographically sign mail |
| **DMARC** | `v=DMARC1; p=none; rua=mailto:dmarc@<domain>` (start at `none`, move to `quarantine`) | Reporting and policy |

Until email is sent, mark deliverability as **N/A — no email sent** and document that decision here.

---

## 9 · Monthly maintenance

| Task | Cadence | Owner | Evidence / gate |
|------|---------|-------|-----------------|
| Dependency updates (npm + pip) | Monthly | Any team member | `npm outdated` / `pip list --outdated` PR |
| Security audit (npm audit + pip audit) | Monthly | QA lead | Zero high/critical (gates G12–G13) |
| Lighthouse re-check on key routes | Monthly | QA lead | Perf ≥ 90, A11y ≥ 95 |
| Cost review (Vercel bandwidth, LLM free tier) | Monthly | SRE lead | ₹0 confirmed; within Hobby 1 TB/month bandwidth |
| Backup restore drill | Quarterly | SRE lead | Restore < 10 min; seeded demo passes |
| Rollback drill | Quarterly | SRE lead | Rollback < 5 min |
| Secrets rotation review | Quarterly | SRE lead | `GITHUB_APP_WEBHOOK_SECRET`, `SESSION_SECRET` rotated if exposed |

---

## 10/10 check

- [ ] Environments defined with config differences documented
- [ ] CI/CD steps map to CI gates G1–G14 from `08-quality.md`
- [ ] Database migration process stated (no DB in v1; contract change procedure)
- [ ] Monitoring defined with alert thresholds (uptime, errors, Web Vitals, logs without PII)
- [ ] Backups and restore drill with < 10 min target
- [ ] Rollback under 5 minutes with tested drill
- [ ] Incident runbook: detect → triage → fix → post-mortem
- [ ] Domain, DNS, and email deliverability (SPF/DKIM/DMARC) addressed
- [ ] Monthly maintenance cadence with owners and evidence

## Avoid

- Treating preview as production (preview is short-lived; config differs)
- Committing `.env` or real secrets to the repo
- Running SQL migrations against a non-existent database
- Logging PII (tokens, issue bodies, emails)
- Skipping the rollback drill because "it's a hackathon"
- Adding third-party monitoring scripts (violates zero third-party scripts rule)
