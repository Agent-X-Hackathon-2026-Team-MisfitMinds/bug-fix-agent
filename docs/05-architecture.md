# 05 — Architecture: Bug-Fix Agent

## Stack
Every choice is boring, well-documented, and matches the PRD-specified stack where one was already locked.

| Layer | Choice | One-line reason | Alternative rejected |
|-------|--------|-----------------|---------------------|
| Frontend framework | Next.js (App Router) | SSG for marketing pages + SSR for the auth-gated dashboard; one repo for both | Remix (less SSG maturity, more config) |
| Backend API | FastAPI (Python) | PRD-specified; native Python for LangGraph/LLM ecosystem | Node/Express (would fight the Python agent stack) |
| Agent orchestration | LangGraph | PRD-specified; stateful graph gives retry/checkpoint for Read→Reproduce→Diagnose→Fix→Verify→PR | Plain Python scripts (no state, no resume, no branching) |
| Sandbox | Docker | PRD-specified; prebuilt images, isolation, resource limits | Firecracker/gVisor (overkill for a hackathon) |
| Auth | GitHub App OAuth | PRD-specified; no password storage, no PII, session tied to installation | Clerk/Auth0 (cost, vendor lock-in, extra PII) |
| Database | None (JSON files / in-memory) | ₹0 budget; run logs are transient and demo-scoped | PostgreSQL/Supabase (operational overhead, cost) |
| Real-time | SSE (FastAPI → Next.js) | PRD-specified; simple, one-way server→client timeline | WebSocket/Socket.io (more infra, stateful connections) |
| Frontend hosting | Vercel (Hobby) | ₹0, generous bandwidth, Next.js-native | Railway/Render (cost at 100k visits) |
| Backend hosting | Local Docker + ngrok/smee | ₹0, hackathon-appropriate, no cloud commit | Fly/Railway (cost, commitment) |

## Rendering and caching per route
| Route | Strategy | Revalidation | Notes |
|-------|----------|--------------|-------|
| `/` | Static (SSG) | On deploy only | Marketing home |
| `/how-it-works` | Static (SSG) | On deploy only | Marketing |
| `/demo` | Static (SSG) | On deploy only | Marketing; seeded issues baked at build |
| `/security` | Static (SSG) | On deploy only | Marketing |
| `/pricing` | Static (SSG) | On deploy only | Marketing |
| `/about` | Static (SSG) | On deploy only | Marketing |
| `/privacy` | Static (SSG) | On deploy only | Legal |
| `/terms` | Static (SSG) | On deploy only | Legal |
| `/changelog` | ISR | Revalidate 60s | Show active development without full rebuild |
| `/auth/github` | Dynamic (server-only) | None | Redirects to GitHub OAuth |
| `/auth/callback` | Dynamic (server-only) | None | Exchanges code, sets session cookie |
| `/dashboard` | Dynamic (SSR, auth-gated) | None | User-specific run list |
| `/dashboard/runs/[runId]` | Dynamic (SSR + client SSE) | None | SSR initial HTML, then SSE live timeline |
| `/404`, `/500`, `/maintenance` | Static | On deploy only | Error pages |

**Caching headers:**

## Folder tree
Monorepo-style split across frontend (Next.js), backend (FastAPI), and shared types.

```
bug-fix-agent/
├── apps/
│   ├── web/                    # Next.js dashboard + marketing
│   │   ├── app/
│   │   │   ├── (marketing)/    # /, /how-it-works, /demo, /security, /pricing, /about, /changelog
│   │   │   ├── auth/           # /auth/github, /auth/callback
│   │   │   ├── dashboard/      # /dashboard, /dashboard/runs/[runId]
│   │   │   ├── 404.tsx
│   │   │   ├── 500.tsx
│   │   │   ├── layout.tsx      # Root layout, nav, footer
│   │   │   └── maintenance/    # /maintenance
│   │   ├── components/
│   │   │   ├── nav.tsx
│   │   │   ├── footer.tsx
│   │   │   ├── run-list.tsx
│   │   │   ├── sse-timeline.tsx
│   │   │   ├── status-badge.tsx
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── empty-state.tsx
│   │   │   └── toast.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts    # fetch wrapper for FastAPI
│   │   │   ├── session.ts       # cookie read/validate
│   │   │   ├── sse.ts           # EventSource helper
│   │   │   └── utils.ts
│   │   ├── types/              # Frontend-only types (re-exported from shared)
│   │   └── public/             # OG image, favicon
│   └── api/                    # FastAPI backend
│       ├── main.py
│       ├── webhooks/
│       │   └── github.py       # label webhook handler
│       ├── pipeline/
│       │   ├── langgraph.py    # Read → Reproduce → Diagnose → Fix → Verify → PR
│       │   ├── sandbox.py      # Docker run wrapper
│       │   └── llm.py          # LLM calls with caching
│       ├── auth/
│       │   └── oauth.py        # GitHub App OAuth flow
│       ├── sse/                # SSE event stream
│       ├── docker/             # Dockerfile, prebuilt image config
│       └── data/               # JSON run logs (transient)
├── packages/
│   └── shared/                 # Duplicated if simpler for hackathon
│       └── types.ts            # Run, Step, Status, Confidence (shared TS/Python via JSON schema)
├── .env.example
├── docker-compose.yml          # Local dev: api + web + docker sandbox
└── README.md
```

## Module boundaries
| Module | May import | May NOT import |
|--------|-----------|---------------|
| `apps/web/app/` | `components/`, `lib/`, `types/` | `apps/api/` (separate process), other route groups directly |
| `apps/web/components/` | `lib/`, `types/` | `app/` (no circular deps) |
| `apps/web/lib/` | `types/` | `components/`, `app/` (pure logic only) |
| `apps/web/types/` | nothing | everything |

## Environment variables
| Name | Purpose | Server-only or public |
|------|---------|----------------------|
| `GITHUB_APP_ID` | GitHub App identifier for OAuth | Server-only |
| `GITHUB_APP_CLIENT_SECRET` | GitHub App client secret for token exchange | Server-only |
| `GITHUB_APP_PRIVATE_KEY` | PEM private key for GitHub App installation tokens | Server-only |
| `GITHUB_APP_WEBHOOK_SECRET` | Secret to verify GitHub webhook signatures | Server-only |
| `LLM_API_KEY` | API key for free-tier LLM (Gemini/Groq) | Server-only |
| `LLM_BASE_URL` | Base URL for LLM API endpoint | Server-only |
| `SESSION_SECRET` | Secret to sign/encrypt session cookie | Server-only |
| `NEXT_PUBLIC_GITHUB_APP_ID` | GitHub App ID exposed to frontend for OAuth link | Public |
| `NEXT_PUBLIC_APP_URL` | Canonical site URL for redirects and OG images | Public |
| `MAINTENANCE_MODE` | When "true", middleware redirects all routes to /maintenance | Server-only |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (relative in dev, absolute in prod) | Public |

**Rules:** No secrets in `NEXT_PUBLIC_*` variables. `.env` is git-ignored; `.env.example` lists all required keys with placeholder values.

## Third-party services and failure behaviour
| Service | Role | Failure behaviour |
|---------|------|-------------------|
| GitHub API | OAuth, issue/PR operations, webhooks | Rate-limited or down → show cached runs, display "GitHub unavailable — changes will sync when restored" toast; webhook retries via GitHub's own retry |
| LLM API (Gemini/Groq free tier) | Agent reasoning (diagnose, fix, root cause) | Rate-limited → serve cached LLM responses for rehearsed demo issues; for new issues, agent posts "couldn't process — LLM rate limit" comment and fails gracefully |
| Docker (local) | Sandbox execution | Local, no third-party failure; container startup failure → agent posts "reproduction failed — environment issue" comment |

## Performance budgets per route
Aligned to STANDARDS.md: p75 LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1, TTFB ≤ 0.8s; Lighthouse mobile ≥ 90.

| Route | LCP (s) | INP (ms) | CLS | JS KB (initial) | Notes |
|-------|---------|----------|-----|-----------------|-------|
| `/` | ≤ 2.0 | ≤ 100 | ≤ 0.05 | ≤ 40 | Static, hero + CTA |
| `/how-it-works`, `/security`, `/pricing`, `/about`, `/demo` | ≤ 2.0 | ≤ 100 | ≤ 0.05 | ≤ 40 | Static, text-heavy |
| `/changelog` | ≤ 2.0 | ≤ 100 | ≤ 0.05 | ≤ 40 | ISR, text-heavy |
| `/dashboard` | ≤ 2.5 | ≤ 200 | ≤ 0.1 | ≤ 80 | SSR + run list table |
| `/dashboard/runs/[runId]` | ≤ 2.5 | ≤ 200 | ≤ 0.1 | ≤ 100 | SSR + SSE timeline |
| `/404`, `/500`, `/maintenance` | ≤ 2.0 | ≤ 100 | ≤ 0.05 | ≤ 30 | Static error pages |

**Measurement:** Lighthouse CI on every PR; real-user monitoring (self-hosted, no third-party) for p75 field metrics post-launch.

## Image, font, and script strategy

## Monthly cost
| Visits | Frontend (Vercel Hobby) | Backend (local Docker) | LLM API (free tier) | Total |
|--------|------------------------|------------------------|---------------------|-------|
| 1,000 | ₹0 | ₹0 | ₹0 (cached for rehearsed issues) | ₹0 |
| 100,000 | ₹0 (within Hobby bandwidth) | ₹0 | ₹0 if cached; rate limits apply for uncached | ₹0 |

**Assumptions:** Vercel Hobby includes 1TB bandwidth/month — 100k visits at ~100KB/page ≈ 10GB, well within limits. LLM free tier covers ~20–30 full runs; caching and recorded backup runs cover demo needs. No paid tiers, no credit card.

## Architecture Decision Records (ADRs)
Hard-to-reverse choices documented below.

### ADR-001: Next.js App Router over Remix
**Decision:** Use Next.js App Router for frontend.  
**Rationale:** Single framework handles both SSG (marketing pages) and SSR (auth dashboard). Vercel hosting is ₹0 and Next.js-native. PRD already specifies Next.js.  
**Rejected:** Remix — excellent SSR but weaker SSG story, more configuration, and not aligned with the PRD stack.  
**Reversibility:** Medium — migrating later means rewriting routing and data fetching patterns.

### ADR-002: FastAPI over Node/Express for backend
**Decision:** FastAPI (Python).  
**Rationale:** PRD-specified. Native Python for LangGraph, LLM SDKs, and Docker SDK. No language boundary between agent and API.  
**Rejected:** Node/Express — would require bridging Python agent logic via subprocess or separate service, adding complexity.  
**Reversibility:** High — backend is a separate process behind HTTP; could be rewritten independently.

### ADR-003: LangGraph over plain Python scripts
**Decision:** LangGraph for agent orchestration.  
**Rationale:** Stateful graph gives retry/checkpoint/resume across Read→Reproduce→Diagnose→Fix→Verify→PR. Critical for a hackathon demo where steps can fail and need to continue.  
**Rejected:** Plain Python scripts — no state persistence, no branching logic, no automatic retry on LLM failure.  
**Reversibility:** Medium — agent logic is encapsulated in `apps/api/pipeline/langgraph.py`; could be replaced with a state machine.

### ADR-004: Docker over Firecracker/gVisor for sandbox
**Decision:** Docker containers with resource limits, non-root user, no network after dep install.  
**Rationale:** PRD-specified. Prebuilt images with dependencies baked in. Familiar tooling, ₹0, fast startup.  
**Rejected:** Firecracker/gVisor — stronger isolation but more complex setup, slower cold start, overkill for a hackathon demo on trusted seeded repos.  
**Reversibility:** Medium — sandbox wrapper is in `apps/api/pipeline/sandbox.py`; interface could be retargeted.

### ADR-005: SSE over WebSocket for live timeline
**Decision:** Server-Sent Events (FastAPI → Next.js).  
**Rationale:** PRD-specified. One-way server→client is exactly what a run timeline needs. Simpler than WebSocket (no connection state, reconnects automatically via EventSource).  
**Rejected:** WebSocket/Socket.io — stateful connections, more infra, unnecessary complexity for read-only timeline.  
**Reversibility:** High — SSE client is a small wrapper; could swap to WebSocket with minimal UI changes.

### ADR-006: No database (JSON files / in-memory) over PostgreSQL
**Decision:** Transient run logs stored as JSON files / in-memory.  
**Rationale:** ₹0 budget. Run logs are demo-scoped and short-lived. No user accounts, no persistent data beyond the hackathon.  
**Rejected:** PostgreSQL/Supabase — operational overhead, cost, and schema migrations not justified for transient data.  
**Reversibility:** High — data access is behind a small interface in `apps/api/data/`; could add a DB later.

### ADR-007: GitHub App OAuth over Clerk/Auth0
**Decision:** GitHub App OAuth for authentication.  
**Rationale:** PRD-specified. No password storage, no email collection, no PII. Session tied to GitHub installation. Free.  
**Rejected:** Clerk/Auth0 — cost at scale, vendor lock-in, additional PII (email, profile) that contradicts the privacy goal.  
**Reversibility:** Medium — auth flow is encapsulated in `apps/api/auth/oauth.py`; replacing means rewriting session handling.

### ADR-008: System fonts over Google Fonts
**Decision:** System fonts (`system-ui`, `ui-monospace`) only.  
**Rationale:** Zero external requests, instant render, ₹0, no privacy concerns (no third-party font provider). Matches STANDARDS.md performance pillar (≤2 font families, preloaded).  
**Rejected:** Google Fonts — external request, render-blocking, privacy data to Google.  
**Reversibility:** High — font stack is a CSS variable; swapping is a one-line change.

- **Images:** AVIF/WebP via Next.js `next/image`. Only image is the shared OG screenshot (generated dynamically or static). Sized correctly, lazy-loaded below the fold.
- **Fonts:** System fonts only (`system-ui`, `ui-monospace`). Zero external font requests. Preloaded via `font-display: swap`.
- **Scripts:** Zero third-party scripts. No analytics, no tracking, no error-reporting SDKs. All JS is first-party Next.js + component code.
- **CSS:** Tailwind CSS, purged to used classes only; critical CSS inlined by Next.js.

| smee.io / ngrok | Webhook forwarding (dev only) | Down → GitHub can't reach local webhook; runs won't trigger until tunnel restored; dashboard still works manually |
| Vercel | Frontend hosting | Down → site unavailable; no mitigation (hackathon scope) |
| None | Analytics, tracking, error reporting | Intentionally none — zero third-party scripts per STANDARDS.md |

| `apps/api/` | Python stdlib + FastAPI + LangGraph + Docker SDK | `apps/web/` (separate process; communicates via HTTP) |
| `packages/shared/` | nothing | everything (consumed by both sides via codegen or manual sync) |

**Cross-process communication:** `apps/web` → `apps/api` via HTTP fetch (REST + SSE). No shared in-memory state.
- Static pages: `Cache-Control: public, max-age=31536000, immutable` (versioned assets)
- ISR: `Cache-Control: public, s-maxage=60, stale-while-revalidate=300`
- `/dashboard` and run detail: `Cache-Control: private, no-store` (user-specific, no CDN caching)
- Auth routes: `Cache-Control: no-store` (never cache OAuth flows)
