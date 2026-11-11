# 03 â€” App Flow: Bug-Fix Agent

## Mermaid sitemap
```mermaid
flowchart TD
    %% Marketing pages
    HOME[/]:::marketing
    HOW[/how-it-works]:::marketing
    DEMO[/demo]:::marketing
    SEC[/security]:::marketing
    PRICE[/pricing]:::marketing
    CHANGE[/changelog]:::marketing
    ABOUT[/about]:::marketing
    PRIV[/privacy]:::legal
    TERMS[/terms]:::legal

    %% Auth
    GH_AUTH[/auth/github]:::auth
    GH_CB[/auth/callback]:::auth

    %% App
    DASH[/dashboard]:::app
    RUN[/dashboard/runs/[runId]]:::app

    %% Errors
    NOT_FOUND[/404]:::error
    ERR[/500]:::error
    MAINT[/maintenance]:::error

    %% Marketing edges
    HOME --> HOW & DEMO & SEC & PRICE & DASH
    HOW --> DEMO & SEC
    DEMO --> HOME & SEC
    SEC --> HOW & HOME
    PRICE --> HOME & DEMO

    %% Footer edges (all)
    HOME --> PRIV & TERMS
    HOW --> PRIV & TERMS
    DEMO --> PRIV & TERMS
    SEC --> PRIV & TERMS
    PRICE --> PRIV & TERMS
    CHANGE --> PRIV & TERMS
    ABOUT --> PRIV & TERMS

    %% Auth edges
    HOME --> GH_AUTH
    DASH --> GH_AUTH
    GH_AUTH --> GH_CB
    GH_CB --> DASH

    %% App edges
    DASH --> RUN
    RUN --> DASH

    %% Error edges
    HOME -.-> NOT_FOUND
    HOME -.-> ERR
    HOME -.-> MAINT

    classDef marketing fill:#f9fafb,stroke:#e5e7eb,color:#111827
    classDef legal fill:#f9fafb,stroke:#e5e7eb,color:#374151,stroke-dasharray: 5 5
    classDef auth fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a
    classDef app fill:#ecfdf5,stroke:#10b981,color:#065f46
    classDef error fill:#fef2f2,stroke:#ef4444,color:#991b1b
```

## Critical journeys

### Journey 1 â€” Convert visitor to labeled issue (primary conversion goal)
1. Visitor lands on `/`
2. Clicks primary CTA "Add the agent-fix label"
3. Redirected to `/auth/github` â†’ GitHub OAuth consent â†’ `/auth/callback`
4. Session set, redirected to `/dashboard`
5. User opens their GitHub repo in a separate tab
6. Adds `agent-fix` label to an issue
7. GitHub webhook â†’ FastAPI â†’ LangGraph pipeline starts
8. Status comment posted on issue: "Picked up â€” reproducingâ€¦"
9. Pipeline completes â†’ draft PR opened with redâ†’green proof
10. User clicks "View draft PR" in dashboard or issue comment â†’ GitHub PR page

### Journey 2 â€” Live demo flow
1. Visitor lands on `/`, clicks secondary CTA "View the live demo"
2. Lands on `/demo`
3. Clicks "Open the demo repo" â†’ GitHub seeded repo page
4. Adds `agent-fix` label to one of 3 seeded issues
5. Returns to `/demo` â†’ clicks "View live runs" â†’ `/dashboard/runs/[runId]`
6. SSE live timeline streams: Read â†’ Reproduce â†’ Diagnose â†’ Fix â†’ Verify â†’ PR
7. Sees redâ†’green test output and draft PR link
8. Clicks draft PR link â†’ GitHub PR page

### Journey 3 â€” Review and approve a draft PR
1. User signs in with GitHub â†’ `/dashboard`
2. Clicks a run card showing status "PR opened"
3. SSE timeline shows root-cause write-up + confidence score
4. Clicks "View draft PR" â†’ GitHub PR page
5. Reviews code diff + test output
6. Approves PR (branch protection requires approving review)
7. Merges PR (agent never merges)

### Journey 4 â€” Sign in with GitHub
1. Clicks "Sign in with GitHub" on any page â†’ `/auth/github`
2. GitHub OAuth consent screen
3. Redirects to `/auth/callback` with authorization code
4. Server exchanges code for token, sets secure session cookie
5. Redirects to `/dashboard` (signed-in state)

### Journey 5 â€” Failed run recovery ("couldn't reproduce")
1. User labels issue `agent-fix`
2. Pipeline runs, cannot reproduce â†’ posts "couldn't reproduce" comment on issue
3. Run status on `/dashboard/runs/[runId]` shows "failed â€” couldn't reproduce"
4. User edits issue to add repro steps (expected vs actual)
5. User removes and re-adds `agent-fix` label â†’ new webhook â†’ new run
6. Pipeline retries â†’ success â†’ draft PR opened

## Per-page specs

### `/` â€” Home
**Purpose:** Convert visitor to add `agent-fix` label or view demo  
**Entry points:** Direct URL, search, social  
**Exits:** `/auth/github`, `/demo`, `/how-it-works`, `/security`, `/pricing`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead + 2 CTAs), feature grid (3 MUST features), trust bar (draft PR / human gate / Docker sandbox), footer  
**Data needed:** None (static)

### `/how-it-works` â€” How it works
**Purpose:** Explain the 6-step pipeline; build trust via proof  
**Entry points:** `/`, `/security`, nav  
**Exits:** `/demo`, `/security`, `/`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead), 6-step pipeline (Read â†’ Reproduce â†’ Diagnose â†’ Fix â†’ Verify â†’ Draft PR), redâ†’green proof callout, CTA button, footer  
**Data needed:** None (static)

### `/demo` â€” Demo
**Purpose:** Live seeded-repo demo (hackathon DoD)  
**Entry points:** `/`, nav  
**Exits:** GitHub seeded repo, `/dashboard/runs/[runId]`, `/security`, `/`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead + CTA), 3 seeded issue cards (off-by-one, wrong condition, missing null check), "Open demo repo" link, "View live runs" link, status legend, footer  
**Data needed:** Seeded issue list (title, body, expected bug type), run status mapping (issue number â†’ runId â†’ status)

### `/security` â€” Security
**Purpose:** Address trust/sandbox concerns (#1 blocker)  
**Entry points:** `/`, `/how-it-works`, nav  
**Exits:** `/`, `/how-it-works`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead), security checklist (Docker sandbox, no network after dep install, no host mounts, non-root user, CPU/memory/time limits, no tokens in container, draft PRs only, agent never merges, branch protection required), CTA "Read the brief", footer  
**Data needed:** None (static)

### `/pricing` â€” Pricing
**Purpose:** Confirm â‚¹0 / free, self-hostable  
**Entry points:** `/`, nav  
**Exits:** `/`, `/demo`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead + CTA), pricing card (â‚¹0, free tier, self-hostable, no credit card), footer  
**Data needed:** None (static)

### `/changelog` â€” Changelog
**Purpose:** SEO freshness; show active development  
**Entry points:** nav, footer  
**Exits:** `/`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead), changelog list (date, version, change description), footer  
**Data needed:** Changelog entries (Markdown)

### `/about` â€” About
**Purpose:** Team credibility (4-person hackathon team)  
**Entry points:** nav, footer  
**Exits:** `/`, `/privacy`, `/terms`  
**Components:** Nav, hero (H1 + subhead), team cards (4 roles: Agent/LangGraph, Sandbox/Infra, Frontend/Next.js, Pitch/QA), footer  
**Data needed:** Team member names/roles (static)

### `/privacy` â€” Privacy
**Purpose:** Legal compliance (GitHub App OAuth, data handling)  
**Entry points:** footer, all pages  
**Exits:** `/`, `/terms`  
**Components:** Nav, hero (H1 + subhead), privacy sections (data collected, retention, no PII in logs, delete via GitHub App uninstall), footer  
**Data needed:** None (static)

### `/terms` â€” Terms
**Purpose:** Legal compliance  
**Entry points:** footer, all pages  
**Exits:** `/`, `/privacy`  
**Components:** Nav, hero (H1 + subhead), terms sections (no warranty on agent output, human review required, hackathon project no SLA), footer  
**Data needed:** None (static)

### `/auth/github` â€” GitHub OAuth start
**Purpose:** Initiate GitHub App OAuth flow  
**Entry points:** `/`, `/dashboard`, any page "Sign in with GitHub"  
**Exits:** GitHub consent screen â†’ `/auth/callback`  
**Components:** Redirect only (no UI)  
**Data needed:** GitHub App client ID, redirect URI, scope (repo read, issues write, pull requests draft)

### `/auth/callback` â€” GitHub OAuth callback
**Purpose:** Handle OAuth callback, set session  
**Entry points:** GitHub redirect  
**Exits:** `/dashboard` (success), `/` (error)  
**Components:** Redirect only (no UI)  
**Data needed:** Authorization code from query string, GitHub App client secret

### `/dashboard` â€” Dashboard (runs list)

## State tables (microcopy per page state)
States: loading, empty, error, success, partial, offline, signed-out, signed-in, no-permission.
Marketing pages (`/`, `/how-it-works`, `/demo`, `/security`, `/pricing`, `/changelog`, `/about`, `/privacy`, `/terms`) are static â€” only loading/error/offline apply.

### `/dashboard` â€” Runs list
| State | Microcopy |
|-------|-----------|
| loading | "Loading your runsâ€¦" (skeleton rows) |
| empty | "No runs yet. Add the `agent-fix` label to a GitHub issue to get started." + link to `/how-it-works` |
| error | "Couldn't load runs. Try again." + retry button |
| success | "X runs found" + run list table (issue title, repo, status badge, created at, PR link) |
| partial | "X runs loaded, Y still updatingâ€¦" + list + SSE reconnecting indicator |
| offline | "You're offline. Runs will sync when you're back online." + cached runs shown if available |
| signed-out | "Sign in with GitHub to see your runs." + sign-in button |
| signed-in | Full dashboard with run list + "Sign out" button |
| no-permission | "You don't have access to this repository's runs." + link to `/` |

### `/dashboard/runs/[runId]` â€” Run detail
| State | Microcopy |
|-------|-----------|
| loading | "Loading run [runId]â€¦" (skeleton timeline) |
| empty | "No run found for [runId]." + link back to `/dashboard` |
| error | "Couldn't load this run. Try again." + retry button + link back |
| success | Run header + SSE timeline + redâ†’green output + root-cause + confidence + "View draft PR" button |
| partial | Timeline partially loaded + "Step X of 6 â€” still runningâ€¦" + SSE live indicator |
| offline | "You're offline. Timeline will resume when you reconnect." + last known state shown |
| signed-out | "Sign in with GitHub to view run details." + sign-in button |
| signed-in | Full run detail view |
| no-permission | "You don't have permission to view this run." + link back to `/dashboard` |

### `/auth/github` â€” GitHub OAuth start
| State | Microcopy |
|-------|-----------|
| loading | "Redirecting to GitHubâ€¦" |
| error | "Couldn't start sign-in. Try again." + back button |
| success | (redirects to GitHub consent â€” no terminal state on this page) |

### `/auth/callback` â€” GitHub OAuth callback
| State | Microcopy |
|-------|-----------|
| loading | "Signing you inâ€¦" |
| error | "Sign-in failed. Try again." + link to `/` |
| success | (redirects to `/dashboard`) |

### `/demo` â€” Demo
| State | Microcopy |
|-------|-----------|
| loading | "Loading seeded issuesâ€¦" |
| empty | "No seeded issues available." |
| error | "Couldn't load demo issues. Try again." + retry button |
| success | 3 seeded issue cards + "Open demo repo" + "View live runs" |
| offline | "Demo issues cached. Open the demo repo to try labeling." |

## Form fields and validation
The application has no traditional user-facing forms (no sign-up, login form, contact form, or settings form). The only interactive elements are buttons and links:

| Element | Validation rule | Error message |
|---------|-----------------|---------------|
| "Sign in with GitHub" button | Requires click; no input | "Couldn't start sign-in. Try again." |
| "View draft PR" button | Requires valid prUrl; hidden if no PR | (button disabled/hidden) |
| "View issue" button | Requires valid issueUrl | (button disabled/hidden) |
| Retry button (error states) | Requires network connectivity | "You're offline. Check your connection." |
| "Try again" button (500) | Requires server recovery | "Still not working. Try again later." |

## Auth flow
**Provider:** GitHub App OAuth  
**Flow:**
1. User clicks "Sign in with GitHub" â†’ GET `/auth/github`
2. Server redirects to GitHub OAuth consent with client_id, redirect_uri, scope (repo, issues write, pull requests draft)
3. User grants consent â†’ GitHub redirects to `/auth/callback?code=xxx`
4. Server exchanges code for access token (client_secret), verifies state parameter
5. Server sets secure, HttpOnly, SameSite=Lax session cookie with GitHub user id + token
6. Server redirects to `/dashboard`
7. Subsequent requests validate session cookie; invalid/missing cookie â†’ redirect to `/auth/github`
8. Sign out: clear session cookie â†’ redirect to `/`

**No password storage.** No email collection. No custom auth UI. Session tied to GitHub App installation.

## Payment flow
**None.** The product is â‚¹0 â€” free tiers and hackathon credits only. No paid tiers, no credit card collection, no Stripe/PayPal integration, no pricing plans beyond "free." The `/pricing` page is informational only.

## Account deletion flow
**No separate user accounts exist.** Users authenticate via GitHub App OAuth. To delete access:
1. User uninstalls the GitHub App from their GitHub settings â†’ revokes token
2. User clears browser cookies / signs out â†’ session removed
3. No user data is stored server-side beyond transient run logs (issue text, repo metadata) which are purged on demo repo reset
4. "Delete my data" via `/privacy` page â†’ instructs user to uninstall GitHub App + clear cookies

## Error pages

### `/404` â€” Not found
**H1:** Page not found  
**Subhead:** The page you're looking for doesn't exist.  
**Buttons:** "Go home" (â†’ `/`), "Go to dashboard" (â†’ `/dashboard`, signed-in only)  
**Nav:** Full nav with footer links

### `/500` â€” Server error
**H1:** Something went wrong  
**Subhead:** We hit an error on our end.  
**Buttons:** "Try again" (â†’ refresh), "Go home" (â†’ `/`)  
**Nav:** Full nav with footer links  
**Note:** No stack traces or internal details exposed to the client

### `/maintenance` â€” Maintenance
**H1:** We're deploying an update  
**Subhead:** Check back in [ETA].  
**Button:** "Check back soon" (â†’ `/`)  
**Nav:** Minimal nav (logo only)  
**Activation:** Middleware checks `MAINTENANCE_MODE` env flag; when true, all routes redirect to `/maintenance` except static assets
**Data needed:** Maintenance message, ETA
