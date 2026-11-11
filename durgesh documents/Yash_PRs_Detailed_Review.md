# Yash Vaidya PRs - Detailed Implementation Review

## Overview
This document provides a detailed review of all PRs authored by **Yash Vaidya** for the bug-fix-agent project. The PRs are organized in the sequence specified by the team execution guide.

## Team Context
- **Yash Vaidya** - Backend and infrastructure owner
- **Responsibilities**: FastAPI, data/auth, Docker sandbox, GitHub App/webhooks, deployment plumbing
- **Owner files**: `apps/api/**`, Docker configuration, `docker-compose.yml`, GitHub App/webhook integration
- **Guide Reference**: Bug-Fix-Agent Team Execution Guide (Sections A-F)

---

## PR Sequence (As Specified)

The sequence follows the build order from the team execution guide:
1. T00 → Foundation
2. T06 → Data schemas and run repository
3. T08 → GitHub OAuth and encrypted sessions
4. T07 → API routes, SSE and rate limits
5. T14 → Docker sandbox wrapper
6. T16 → Webhook-driven run creation
7. T21 → Security response headers
8. T22 → CI pipeline for backend
9. T14 tests → Sandbox isolation and timeout tests
10. T18 → Dev webhook tunnel and data persistence

---

## T00: Repo and API Runtime Skeleton

**Commit**: `c830ec1` - `feat(infra): add repo and API runtime skeleton (T-00)`

### Files Changed (13 files, 40 insertions):
- `.gitignore` - Updated with sprint-specific ignore patterns
- `apps/api/Dockerfile` - Initial Docker image configuration
- `apps/api/auth/.gitkeep` - Auth module marker
- `apps/api/data/.gitkeep` - Data module marker
- `apps/api/docker/.gitkeep` - Docker config marker
- `apps/api/pipeline/.gitkeep` - Pipeline module marker
- `apps/api/sse/.gitkeep` - SSE module marker
- `apps/api/tests/fixtures/.gitkeep` - Test fixtures marker
- `apps/api/tests/unit/test_health.py` - Health endpoint test (10 lines)
- `apps/api/webhooks/.gitkeep` - Webhooks module marker
- `packages/shared/README.md` - Shared contract documentation
- `packages/shared/schema/.gitkeep` - Schema marker
- `scripts/.gitkeep` - Scripts marker

### Implementation Details:
- **Dockerfile**: Python 3.12-slim base, installs requirements.txt, creates non-root `appuser`, exposes port 8000, runs uvicorn
- **Health Test**: Verifies GET /health returns 200 with {"status": "ok"}
- **Shared Schema**: Documents the 7 status values and 3 confidence levels per guide spec
- **Foundation**: Establishes directory structure for all subsequent modules

### Guide Alignment:
- Phase 0 Foundation: "Repo, folder tree, Compose, .env.example, .gitignore"
- Shared contract: "Status values: pending, reproducing, fixing, verifying, completed, failed, could_not_reproduce"

---

## T06: Data Schemas and Run Repository

**Commit**: `24b9274` - `feat(api): add schemas, error format and ownership-guarded run repo (T-06)`

### Files Changed (6 files, 270 insertions):
- `apps/api/data/__init__.py` - Data package initialization
- `apps/api/data/run_repo.py` - **110 lines** - In-memory run repository with ownership guards
- `apps/api/errors.py` - **55 lines** - Standard error envelope and exception handlers
- `apps/api/main.py` - Integration of errors and schemas
- `apps/api/tests/unit/test_run_repo.py` - **73 lines** - Comprehensive run repo tests
- `apps/api/tests/unit/test_schemas.py` - **26 lines** - Schema validation tests

### Implementation Details:

#### Run Repository (run_repo.py)
- **RunRepo class**: In-memory dict-based repository (per ADR-006: no database in v1)
- **Caller dataclass**: `installation_id + github_login` for ownership enforcement
- **create()**: Creates run with full metadata
- **_owned()**: Ownership check that raises NotFoundError (404) for foreign users - NEVER 403 to prevent IDOR enumeration
- **get()**: Retrieves run with ownership guard
- **get_steps()**: Gets reproduction steps for a run
- **list()**: Lists runs with ownership filtering, cursor-based pagination, optional status filter
- **update_status()**: Updates run status, auto-sets completed_at for terminal states
- **add_step()**: Adds reproduction/test steps
- **check_retryable()**: Only allows retry on failed/could_not_reproduce states
- **delete_all_for_user()**: Cleanup utility
- **encode_cursor()/decode_cursor()**: Base64 url-safe cursor pagination with validation

#### Error Format (errors.py)
- **Standard envelope**: `{"error": {"code", "message", "details"}}`
- **Custom exceptions**: AppError, ValidationFailed, Unauthorized, Forbidden, NotFoundError, ConflictError
- **register_error_handlers()**: FastAPI exception handlers for AppError, RequestValidationError, and generic Exception
- **_body()**: Consistent error response builder

#### Ownership Pattern (Security Critical):
```python
def _owned(self, caller: Caller, run: Run | None) -> Run:
    if run is None or run.installation_id != caller.installation_id \
            or run.triggered_by != caller.github_login:
        raise NotFoundError("Run not found")  # 404, NOT 403!
    return run
```

### Test Coverage:
- Owner can get their own run
- Foreign user gets 404 (not 403)
- Foreign installation gets 404
- Unknown ID returns 404
- List only own runs and paginates correctly
- Status filter works
- Retry only allowed on failed/could_not_reproduce states
- Bad cursor raises ValidationFailed

### Guide Alignment:
- Section B: "Pydantic for request/response / validation. Keep repository records and ownership interface small."
- Security: "Foreign runs raise NotFoundError (404), never Forbidden, to prevent IDOR enumeration."

### Follow-up Fix:
- `f75c229` - Reconcile T-06 schemas, errors and webhook imports (httpx 0.27.2 pin, error handler alignment)
- `f7001f9` - Fix .dockerignore tracking in .gitignore

---

## T08: GitHub OAuth and Encrypted Sessions

**Commit**: `30d7739` - `feat(infra): add GitHub OAuth and encrypted sessions (T-08)`

### Files Changed (11 files, 625 insertions - largest single PR):
- `apps/api/auth/__init__.py` - Auth package
- `apps/api/auth/crypto.py` - **25 lines** AES-256-GCM encryption
- `apps/api/auth/deps.py` - **30 lines** Auth dependency
- `apps/api/auth/oauth.py` - **105 lines** OAuth flow with CSRF protection
- `apps/api/auth/router.py` - **149 lines** OAuth routes
- `apps/api/auth/sessions.py` - **83 lines** Session management
- `apps/api/config.py` - **43 lines** Configuration
- `apps/api/main.py` - Updated for auth integration
- `apps/api/requirements.txt` - Added dependencies
- `apps/api/tests/conftest.py` - **21 lines** Test config
- `apps/api/tests/unit/test_auth.py` - **158 lines** Auth tests

### Implementation Details:

#### crypto.py - AES-256-GCM
- Token encryption using cryptography library
- AES-256-GCM for authenticated encryption
- Key derived from SESSION_SECRET

#### oauth.py - OAuth Flow
- `start_oauth()` - Initiates GitHub OAuth with signed CSRF state
- `callback()` - Handles OAuth callback, validates state, exchanges code for token
- State signing prevents CSRF attacks
- Redirect to GitHub authorization URL

#### sessions.py - Session Management
- Creates `__Host-session_id` cookie
- HttpOnly, Secure, SameSite=Lax, Path=/, 24-hour expiry
- Stores encrypted GitHub token server-side
- Logout functionality

#### deps.py - Auth Dependency
- `require_auth()` FastAPI dependency
- Extracts and validates session cookie
- Returns authenticated user context
- Used to protect routes

#### config.py - Configuration
- Environment variable management
- SESSION_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
- Webhook secret configuration
- LLM API key configuration

### Security Features:
1. **CSRF Protection**: Signed state parameter in OAuth flow
2. **Token Encryption**: AES-256-GCM for all stored tokens
3. **Cookie Security**: `__Host-session_id` with all required flags
4. **No Secrets in Browser**: All private keys stay server-side
5. **Session Expiry**: 24-hour absolute expiry

### Test Coverage (158 lines):
- OAuth start/callback flow
- CSRF state validation
- Token encryption/decryption
- Session cookie flags
- Logout functionality
- Unauthorized access handling

### Guide Alignment:
- Section B step 3: "Build OAuth/session. __Host-session_id cookie: Cookie flags and logout tests pass. HttpOnly, Secure, SameSite=Lax, 24h."
- Section B step 4: "GitHub App OAuth; verify state; encrypt token with AES-256-GCM"

### Security Checklist Compliance:
- Cookie is `__Host-session_id`, HttpOnly, Secure, SameSite=Lax, Path=/, no Domain, 24-hour expiry
- No token, issue body, PR diff, email or other personal data in logs

---

## T07: API Routes, SSE and Rate Limits

**Commit**: `42acff6` - `feat(infra): add run routes, SSE and rate limits (T-07)`

### Files Changed (9 files, 489 insertions):
- `apps/api/rate_limit.py` - **50 lines** Sliding-window rate limiter
- `apps/api/data/idempotency.py` - **40 lines** Idempotency key protection
- `apps/api/routes/__init__.py` - Routes package
- `apps/api/routes/runs.py` - **148 lines** Run CRUD endpoints
- `apps/api/auth/router.py` - **16 lines** Auth updates
- `apps/api/data/run_repo.py` - **12 lines** Idempotency support
- `apps/api/main.py` - **8 lines** Route registration
- `apps/api/tests/conftest.py` - **6 lines** Test config
- `apps/api/tests/unit/test_routes.py` - **212 lines** Route tests

### Implementation Details:

#### runs.py - Run CRUD Endpoints (148 lines)
- `GET /runs` - List runs with pagination and status filter
- `GET /runs/{run_id}` - Get run details (ownership-guarded)
- `GET /runs/{run_id}/steps` - Get reproduction steps
- `POST /runs/{run_id}/retry` - Retry failed/could_not_reproduce runs
- `DELETE /runs/{run_id}` - Delete run (if allowed)
- `GET /runs/{run_id}/events` - SSE timeline stream

#### rate_limit.py - Rate Limiter (50 lines)
- Per-user/per-run sliding-window limits
- Returns 429 with Retry-After header after 61 requests/minute
- Endpoint-specific limits
- Uses slowapi library

#### idempotency.py - Idempotency Protection (40 lines)
- Idempotency-Key header support
- Replay protection for retries
- Prevents duplicate run creation on retry

#### SSE Implementation
- Server-Sent Events for live timeline updates
- Event stream endpoint
- De-duplication on reconnect

### Test Coverage (212 lines):
- Ownership checks on all endpoints
- Rate limit behavior
- Idempotency replay protection
- SSE stream behavior
- Error responses for unauthorized/foreign access

### Guide Alignment:
- Section B step 5: "Add API endpoints. Unauthenticated=401; foreign run=404; retry requires run detail, SSE, retry, session, Idempotency-Key."
- Section B step 6: "Add rate limits. 61 requests to a 60/min endpoint return 429 with Retry-After."

### Follow-up Fix:
- `1193cc2` - Align .env.example and docker-compose with documented keys (added SESSION_SECRET, webhook secret, client-id; stopped mounting repo root into API container)

---

## T14: Docker Sandbox Wrapper

**Commit**: `fd5ff63` - `feat(infra): add isolated Docker sandbox wrapper (T-14)`

### Files Changed (4 files, 256 insertions):
- `apps/api/docker/sandbox.Dockerfile` - **13 lines** Prebuilt sandbox image
- `apps/api/pipeline/__init__.py` - Pipeline package init
- `apps/api/pipeline/sandbox.py` - **138 lines** Sandbox wrapper
- `apps/api/tests/unit/test_sandbox.py` - **105 lines** Sandbox tests

### Implementation Details (sandbox.py - 138 lines):

#### build_docker_cmd() Function
Constructs docker run command with:
- `--network=none` - No network access
- `--user=nonroot` - Non-root user execution
- `--memory=512m` - Memory cap
- `--cpus=1` - CPU cap
- `--pids-limit=100` - PID limit
- `--cap-drop=ALL` - Drop all capabilities
- `--security-opt=no-new-privileges` - No privilege escalation
- `--read-only` - Read-only filesystem
- No host mounts
- No secrets in container
- `--timeout=300` (5 minutes)

#### Sandbox Execution Flow:
1. Build docker command with all restrictions
2. Execute with subprocess (explicit arg list, never shell=True)
3. Capture stdout, stderr, exit code, timeout state
4. On timeout: force-remove container by deterministic name
5. Return structured results to caller (Durgesh's pipeline)

#### sandbox.Dockerfile (13 lines):
- Python 3.12-slim base
- Pinned dependency versions
- Prebuilt stable dependencies (reduces demo-time network installs)
- Non-root user setup
- Entrypoint for test execution

### Test Coverage (105 lines):
- Verify --network=none is included
- Verify --user=nonroot is included
- Verify memory and CPU limits present
- Verify 5-minute timeout enforced
- Verify no host mounts
- Verify no secrets passed
- Timeout cleanup behavior

### Guide Alignment:
- Section C step 1: "Create prebuilt Docker image for Python demo repository. Pin Python and dependency versions."
- Section C step 2: "Implement build_docker_cmd() with --network=none, --user=nonroot, memory and CPU limits, and hard five-minute timeout."
- Section C step 3: "Do not mount host filesystem. Do not pass tokens into container."
- Section C step 6: "Run integration check that container cannot access network during tests."

### Follow-up Fix:
- `a4d98f7` - Fix(infra): remove sandbox container when the run times out (force-remove by deterministic name after timeout)

---

## T16: Create Runs from Agent-Fix Webhooks

**Commit**: `a1f4538` - `feat(infra): create runs from agent-fix webhooks (T-16)`

### Implementation Details:

#### Webhook Handler (webhooks/github.py)
- `POST /webhooks/github` endpoint
- **HMAC-SHA256 signature verification** for GitHub webhook authenticity
- **X-GitHub-Delivery deduplication** - rejects duplicate deliveries
- **Trigger only on `issues.labeled`** with label `agent-fix`
- Read issue title, body, repository, reproduction steps
- Create run record in RunRepo
- Add progress comment to GitHub issue
- Push agent branch
- Open draft PR (never merge - per non-negotiable rule)

#### Security Features:
- Webhook secret verification using HMAC
- Fail-closed behavior: unset secret rejects deliveries (verified by T18 tests)
- No secrets in logs
- Generic error messages for users

### Guide Alignment:
- Section F: "Real GitHub label reaches local GitHub App, webhook tunnel, integrate Yash + Subhi + Durgesh API; preview can show live Vercel preview, cross-origin SSE timeline."
- Non-negotiable: "The agent opens draft PRs only; it never merges."

---

## T21: Security Response Headers

**Commit**: `09857d5` - `feat(infra): add security response headers to the API (T-21)`

### Implementation Details:
- Added security headers to all API responses:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security (HSTS)
  - Content-Security-Policy
- CORS configuration adjustments
- Rate limit response headers

### Guide Alignment:
- Phase 6: "Security headers, rate limits, all CI All required checks green; no high/critical dependency audit issues."

---

## T22: Backend Lint, Types and Unit Tests on PRs

**Commit**: `071273a` - `ci(infra): run backend lint, types and unit tests on PRs (T-22)`

### Files Changed (1 file, 64 insertions):
- `.github/workflows/api-ci.yml` - **64 lines** CI workflow

### CI Workflow Configuration:
- **G3**: `ruff check apps/api/` - Python linting
- **G4**: `mypy --strict apps/api/` - Python type checking
- **G6**: `pytest tests/unit/ -v` - Backend unit tests
- **G13**: `pip audit --strict` - Python dependency audit (advisory only)

### Advisory Job Handling:
- G13 runs as advisory job (doesn't block merges)
- Reason: Pinned fastapi/starlette/cryptography versions predate security fixes
- Requires deliberate upgrade decision (per guide: "If a tool cannot be installed or run in time, record it as NOT RUN rather than pretending it passed.")

### Follow-up Fix:
- `3603cc9` - Keep advisory audit job from blocking merges (3-line change to make G13 advisory)

### Guide Alignment:
- Section F gate commands: `ruff check apps/api/`, `mypy --strict apps/api/`, `pytest tests/unit/ -v`, `pytest tests/integration/ -v`
- Phase 6: "All required checks green; no high/critical dependency audit issues."

---

## T14 Tests: Sandbox Isolation and Timeout

**Commit**: `9908410` - `test(infra): cover real sandbox isolation and timeout (T-14)`

### Implementation Details:
- `apps/api/tests/unit/test_sandbox.py` - 105 lines of sandbox tests
- Tests verify:
  - Container cannot access network during tests
  - Resource/time limits are applied
  - Timeout behavior is correct
  - Non-root user execution works
  - Proper error handling on timeout
  - Container cleanup after timeout

### Guide Alignment:
- Section C step 6: "Run an integration check that the container cannot access the network during tests and that resource/time limits are applied."

---

## T18: Dev Webhook Tunnel and Data Persistence

**Commit**: `208e4da` - `feat(infra): add dev webhook tunnel and fail-closed secret test (T-18)`

### Files Changed (2 files, 31 insertions):
- `scripts/dev-tunnel.sh` - **18 lines** smee.io webhook forwarding script
- `apps/api/tests/unit/test_webhook.py` - **13 lines** Fail-closed secret test

### Implementation Details:

#### dev-tunnel.sh (18 lines):
- Forwards smee.io deliveries to local API
- Enables GitHub App webhook testing without public host
- Keeps tunnel running during live demo

#### Fail-Closed Test (13 lines):
- Verifies that unset webhook secret rejects deliveries
- Does NOT verify against empty key (security critical)
- Ensures fail-closed behavior rather than fail-open

### Follow-up Fix:
- `1912900` - Fix(infra): persist apps/api/data across container restarts
  - Added bind mount for `/app/data` in `docker-compose.yml`
  - Problem: JSON run data was lost on container recreate
  - Solution: Bind mount (not named volume) because `/app/data` also holds Python modules
  - 2 lines added to docker-compose.yml

### Guide Alignment:
- Section F: "Set up smee.io or ngrok for local webhook forwarding; connect Vercel for frontend previews. Keep all secrets in local .env / server-only environment settings."
- Critical security: "Fail-closed behavior when webhook secret is unset"

---

## Summary of Yash's Contributions

### By Area:
| Area | Tickets | Key Deliverables |
|------|---------|------------------|
| **FastAPI & Data** | T06-T08 | Schemas, error formats, run repo, OAuth, sessions, rate limits, SSE |
| **Docker Sandbox** | T14 | Isolated container with network/user/cap/time limits, 5-min timeout |
| **CI/CD** | T21-T22 | Security headers, lint/types/tests, advisory audit handling |
| **Webhooks & Tunnel** | T16, T18 | Webhook handler, dev tunnel, fail-closed secret validation, data persistence |

### By Phase:
| Phase | Tickets | Description |
|-------|---------|-------------|
| Phase 0: Foundation | T00 | Repo skeleton and Dockerfile |
| Phase 2: Data + Auth | T06, T08, T07 | Data schemas → OAuth → API routes |
| Phase 4: Core Agent | T14, T16 | Sandbox wrapper, webhook integration |
| Phase 5: Integration | T21 | Security headers |
| Phase 6: Quality | T22, T14 tests | CI pipeline, sandbox tests |
| Phase 8: Launch | T18 | Webhook tunnel, data persistence |

### Security Checklist Compliance:
- ✅ HMAC-SHA256 webhook signature verification
- ✅ IDOR prevention via 404 (not 403) for foreign runs
- ✅ `__Host-session_id` cookie with HttpOnly, Secure, SameSite=Lax
- ✅ AES-256-GCM token encryption
- ✅ CSRF state signing in OAuth flow
- ✅ Fail-closed webhook secret behavior
- ✅ Docker: non-root, no network, no mounts, no secrets, CPU/memory/time limits
- ✅ No tokens in sandbox
- ✅ No merge permission for agent
- ✅ Draft PRs only (never auto-merge)

### Non-Negotiable Rules Compliance:
- ✅ Python + pytest only
- ✅ Docker isolation with no host mounts
- ✅ No network after dependency install
- ✅ Non-root execution
- ✅ No secrets in sandbox
- ✅ 5-minute timeout
- ✅ Agent opens draft PRs only
- ✅ No auto-merge

---

## Technical Debt / Follow-up Items:
1. **Advisory CI Job**: G13 pip audit is advisory due to pinned vulnerable dependencies - needs deliberate upgrade
2. **Data Persistence**: In-memory repository (ADR-006) - JSON persistence via bind mount for container restarts
3. **SSE Implementation**: Basic SSE stream - needs reconnect handling and de-duplication (Subhi's frontend work)
4. **Pipeline Integration**: Sandbox interface agreed with Durgesh for LangGraph pipeline nodes

## Guide References:
- Section A: Shared contract (Yash defines Pydantic models)
- Section B: Yash - FastAPI, data and auth sequence (T06-T08)
- Section C: Yash - Docker sandbox sequence (T14)
- Section D: Durgesh - LangGraph sequence (uses Yash's sandbox)
- Section E: Subhi - Frontend sequence (uses Yash's API)
- Section F: You - QA, demo and launch sequence

---
*Document created from git history review of Yash Vaidya's contributions to the bug-fix-agent project*
*Sequence follows: T00 → T06 → T08 → T07 → T14 → T16 → T21 → T22 → T14 tests → T18*
