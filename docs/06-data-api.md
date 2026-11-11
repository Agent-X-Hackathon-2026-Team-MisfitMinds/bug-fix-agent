# 06 — Data & API: Bug-Fix Agent

## Data store note (ADR-006 reconciliation)
Per ADR-006 in `docs/05-architecture.md`, v1 uses **no database** — run logs are transient JSON files in `apps/api/data/` behind a repository interface. The logical relational schema below is the **data contract**: table definitions, ERD, and a PostgreSQL migration are specified so the store can be swapped to SQL later with zero schema churn. All table/column names below are the canonical names used by the JSON-file repository and by the API responses.

## Tables (logical schema)

### `runs`
Purpose: One agent run triggered by the `agent-fix` GitHub issue label. Row owner: GitHub installation / repository owner (the repo that was labeled).

| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `installation_id` | `bigint` | NO | | GitHub App installation ID |
| `repository_full_name` | `text` | NO | | `owner/repo` |
| `issue_number` | `integer` | NO | | GitHub issue number |
| `issue_title` | `text` | NO | | Snapshot at label time |
| `issue_body` | `text` | NO | | Snapshot at label time |
| `status` | `text` | NO | `'pending'` | `pending` \| `reproducing` \| `fixing` \| `verifying` \| `completed` \| `failed` \| `could_not_reproduce` |
| `confidence` | `text` | YES | | `high` \| `medium` \| `low` |
| `pr_url` | `text` | YES | | Draft PR URL (opened on success) |
| `pr_number` | `integer` | YES | | Draft PR number |
| `test_output` | `text` | YES | | Red→green test output embedded for dashboard |
| `root_cause` | `text` | YES | | Plain-English root-cause write-up |
| `repo_language` | `text` | NO | | Detected language (v1: `python`) |
| `triggered_by` | `text` | NO | | GitHub login of the user who added the label |
| `created_at` | `timestamptz` | NO | `now()` | Audit |
| `updated_at` | `timestamptz` | NO | `now()` | Audit |
| `completed_at` | `timestamptz` | YES | | When the run reached a terminal state |

**PK:** `id`  

### `run_steps`
Purpose: One SSE timeline step per run (read→reproduce→diagnose→fix→verify→pr). Row owner: run owner.

| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `run_id` | `uuid` | NO | | FK → `runs.id` ON DELETE CASCADE |
| `step` | `text` | NO | | `read` \| `reproduce` \| `diagnose` \| `fix` \| `verify` \| `pr` |
| `status` | `text` | NO | `'pending'` | `pending` \| `running` \| `completed` \| `failed` |
| `started_at` | `timestamptz` | YES | | |
| `completed_at` | `timestamptz` | YES | | |
| `output` | `text` | YES | | Step stdout/logs (SSE event payload) |
| `error` | `text` | YES | | Error message if step failed |
| `created_at` | `timestamptz` | NO | `now()` | Audit |
| `updated_at` | `timestamptz` | NO | `now()` | Audit |

**PK:** `id`  
**FK:** `run_id` → `runs.id` ON DELETE CASCADE  
**Indexes:**
- `idx_run_steps_run_step` (run_id, step) — serves "fetch all steps for a run in order" (run detail + SSE timeline)
- `idx_run_steps_run_created` (run_id, created_at) — serves "steps ordered chronologically" (SSE replay)

### `llm_cache`
Purpose: Cached LLM responses keyed by hash of issue title + body, mitigating free-tier rate limits. Row owner: system.

| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `cache_key` | `text` | NO | | SHA-256 of `issue_title + issue_body` |
| `prompt_hash` | `text` | YES | | Hash of the prompt sent (for cache invalidation on prompt change) |
| `response` | `jsonb` | NO | | Cached LLM completion response |
| `ttl_seconds` | `integer` | NO | `86400` | Time-to-live in seconds (24h default) |
| `expires_at` | `timestamptz` | NO | `now() + interval '24 hours'` | Expiry for cleanup |
| `hit_count` | `integer` | NO | `0` | Number of cache hits |
| `created_at` | `timestamptz` | NO | `now()` | Audit |

### `webhook_events`
Purpose: GitHub webhook dedup and audit (X-GitHub-Delivery ID). Row owner: system.

| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `delivery_id` | `text` | NO | | GitHub `X-GitHub-Delivery` header |
| `event` | `text` | NO | | `issues` \| `pull_request` |
| `action` | `text` | NO | | `labeled` \| `unlabeled` |
| `repository_full_name` | `text` | NO | | |
| `issue_number` | `integer` | YES | | |
| `processed` | `boolean` | NO | `false` | Whether the webhook led to a run |
| `run_id` | `uuid` | YES | | FK → `runs.id` ON DELETE SET NULL |
| `received_at` | `timestamptz` | NO | `now()` | Audit |
| `processed_at` | `timestamptz` | YES | | Audit |

**PK:** `id`  
**Indexes:**
- `idx_webhook_events_delivery` (delivery_id) UNIQUE — serves "dedup: has this webhook already been processed?"
- `idx_webhook_events_received` (received_at DESC) — serves "audit log of recent webhooks"

### `sessions`
Purpose: GitHub OAuth user sessions. Row owner: authenticated user.

| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `github_user_id` | `bigint` | NO | | GitHub user ID |
| `github_login` | `text` | NO | | GitHub login |
| `token` | `text` | NO | | Encrypted GitHub access token |
| `expires_at` | `timestamptz` | NO | | Session expiry |
| `created_at` | `timestamptz` | NO | `now()` | Audit |

## Mermaid ERD
```mermaid
erDiagram
    runs ||--o{ run_steps : "contains"
    runs }o--|| webhook_events : "triggered by"
    runs ||--|| sessions : "triggered by (triggered_by)"

    runs {
        uuid id PK
        bigint installation_id
        text repository_full_name
        integer issue_number
        text issue_title
        text issue_body
        text status
        text confidence
        text pr_url
        integer pr_number
        text test_output
        text root_cause
        text repo_language
        text triggered_by
        timestamptz created_at
        timestamptz updated_at
        timestamptz completed_at
    }

    run_steps {
        uuid id PK
        uuid run_id FK
        text step
        text status
        timestamptz started_at
        timestamptz completed_at
        text output
        text error
        timestamptz created_at
        timestamptz updated_at
    }

    llm_cache {
        uuid id PK
        text cache_key
        text prompt_hash
        jsonb response
        integer ttl_seconds
        timestamptz expires_at
        integer hit_count
        timestamptz created_at
        timestamptz updated_at
    }

    webhook_events {
        uuid id PK
        text delivery_id UK
        text event
        text action
        text repository_full_name
        integer issue_number
        boolean processed
        uuid run_id FK
        timestamptz received_at
        timestamptz processed_at
    }

    sessions {
        uuid id PK
        bigint github_user_id UK
        text github_login

## v1 SQL migration (PostgreSQL drop-in)
```sql
-- 001_initial_schema.sql
-- Runs table
CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id BIGINT NOT NULL,
    repository_full_name TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_title TEXT NOT NULL,
    issue_body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','reproducing','fixing','verifying','completed','failed','could_not_reproduce')),
    confidence TEXT CHECK (confidence IN ('high','medium','low')),
    pr_url TEXT,
    pr_number INTEGER,
    test_output TEXT,
    root_cause TEXT,
    repo_language TEXT NOT NULL DEFAULT 'python',
    triggered_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_runs_installation_repo ON runs(installation_id, repository_full_name);
CREATE INDEX idx_runs_issue ON runs(repository_full_name, issue_number);
CREATE INDEX idx_runs_status_created ON runs(status, created_at DESC);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);

-- Run steps table
CREATE TABLE run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    step TEXT NOT NULL CHECK (step IN ('read','reproduce','diagnose','fix','verify','pr')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    output TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- LLM cache table
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT NOT NULL UNIQUE,
    prompt_hash TEXT,
    response JSONB NOT NULL,
    ttl_seconds INTEGER NOT NULL DEFAULT 86400,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours'),
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_cache_key ON llm_cache(cache_key);
CREATE INDEX idx_llm_cache_expires ON llm_cache(expires_at);

-- Webhook events table
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id TEXT NOT NULL UNIQUE,
    event TEXT NOT NULL,
    action TEXT NOT NULL,
    repository_full_name TEXT NOT NULL,
    issue_number INTEGER,
    processed BOOLEAN NOT NULL DEFAULT false,
    run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_webhook_events_received ON webhook_events(received_at DESC);

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_user_id BIGINT NOT NULL UNIQUE,
    github_login TEXT NOT NULL,
    token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Updated_at trigger helper
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_runs_updated_at BEFORE UPDATE ON runs

## Seed data (3 seeded demo issues)
```sql
-- Seed runs for the 3 deterministic seeded bugs (demo DoD)
INSERT INTO runs (installation_id, repository_full_name, issue_number, issue_title, issue_body,
                  status, confidence, pr_url, pr_number, test_output, root_cause, repo_language,
                  triggered_by, created_at, updated_at, completed_at) VALUES
(1, 'fixie-demo/seeded-repo', 1, 'Off-by-one in calculate_discount',
 'When quantity is 10, discount is calculated as 10% instead of 15%.',
 'completed', 'high', 'https://github.com/fixie-demo/seeded-repo/pull/1', 1,
 'FAILED test_off_by_one (before fix) → PASSED test_off_by_one (after fix)',
 'Loop boundary used < instead of <= at line 42.',
 'python', 'demo-user', now() - interval '10 minutes',
 now() - interval '10 minutes', now() - interval '8 minutes'),

(1, 'fixie-demo/seeded-repo', 2, 'Wrong condition in validate_age',
 'Age 18 is rejected though it should be accepted.',
 'completed', 'medium', 'https://github.com/fixie-demo/seeded-repo/pull/2', 2,
 'FAILED test_validate_age_boundary (before fix) → PASSED test_validate_age_boundary (after fix)',
 'Condition used > instead of >= at line 17.',
 'python', 'demo-user', now() - interval '8 minutes',
 now() - interval '8 minutes', now() - interval '6 minutes'),

(1, 'fixie-demo/seeded-repo', 3, 'Missing null check in get_user_profile',
 'Crashes when profile avatar_url is null.',
 'failed', NULL, NULL, NULL, NULL,
 'Agent could not reproduce: no steps to reproduce provided.',
 'python', 'demo-user', now() - interval '6 minutes',
 now() - interval '6 minutes', now() - interval '5 minutes');

INSERT INTO run_steps (run_id, step, status, started_at, completed_at, output, error, created_at, updated_at) VALUES
-- Run 1 (completed)
((SELECT id FROM runs WHERE issue_number = 1), 'read', 'completed',
 now() - interval '10 minutes', now() - interval '10 minutes',
 'Read issue #1 from fixie-demo/seeded-repo', NULL,
 now() - interval '10 minutes', now() - interval '10 minutes'),
((SELECT id FROM runs WHERE issue_number = 1), 'reproduce', 'completed',
 now() - interval '10 minutes', now() - interval '9 minutes',
 'Cloned repo, installed deps, ran pytest. Bug reproduced: test_off_by_one failed.', NULL,
 now() - interval '10 minutes', now() - interval '9 minutes'),
((SELECT id FROM runs WHERE issue_number = 1), 'diagnose', 'completed',
 now() - interval '9 minutes', now() - interval '8 minutes',
 'Root cause: loop boundary < instead of <= at line 42.', NULL,
 now() - interval '9 minutes', now() - interval '8 minutes'),
((SELECT id FROM runs WHERE issue_number = 1), 'fix', 'completed',
 now() - interval '8 minutes', now() - interval '8 minutes',
 'Patched line 42: changed < to <=.', NULL,
 now() - interval '8 minutes', now() - interval '8 minutes'),
((SELECT id FROM runs WHERE issue_number = 1), 'verify', 'completed',
 now() - interval '8 minutes', now() - interval '8 minutes',
 'Ran full suite: 45 passed, 0 failed. Red→green confirmed.', NULL,
 now() - interval '8 minutes', now() - interval '8 minutes'),
((SELECT id FROM runs WHERE issue_number = 1), 'pr', 'completed',

## Standard error format
Every API error returns this shape:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": []
  }
}
```

| Error code | HTTP status | Meaning |
|------------|-------------|---------|
| `VALIDATION_ERROR` | 400 | Request body failed schema validation; `details` lists field errors |
| `UNAUTHORIZED` | 401 | Missing or invalid session |
| `FORBIDDEN` | 403 | Session lacks permission for this resource |
| `NOT_FOUND` | 404 | Resource does not exist |
| `CONFLICT` | 409 | Idempotency-key reuse with different payload, or duplicate webhook |
| `RATE_LIMITED` | 429 | Too many requests; `Retry-After` header set |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Pagination
Cursor-based pagination on list endpoints (`GET /runs`). Query params:
- `limit`: integer, default 20, max 100
- `cursor`: opaque string from previous response's `next_cursor`; omitted for first page

Response shape:
```json
{
  "data": [...],
  "next_cursor": "base64-encoded-offset-or-null",
  "has_more": true
}
```

## API routes
All routes are served by the FastAPI backend (`apps/api/`). Auth means a valid session cookie (`session_id`) set by `/auth/callback`; webhook routes use GitHub webhook secret verification instead.

| Route | Method | Auth | Rate limit |
|-------|--------|------|------------|
| `/webhooks/github` | POST | Webhook secret | 100/min per IP |
| `/runs` | GET | Session cookie | 60/min per user |
| `/runs/{run_id}` | GET | Session cookie | 60/min per user |
| `/runs/{run_id}/events` | GET (SSE) | Session cookie | 30/min per user |
| `/runs/{run_id}/retry` | POST | Session + Idempotency-Key | 5/min per run |
| `/auth/session` | GET | Session cookie (optional) | 60/min per user |
| `/auth/logout` | POST | Session cookie | 30/min per user |

### `POST /webhooks/github`
Receives GitHub issue/PR webhook events. Verifies `X-Hub-Signature-256` using `GITHUB_APP_WEBHOOK_SECRET`. Dedups by `X-GitHub-Delivery`. On `issues.labeled` or `issues.opened` where the issue carries the `agent-fix` label, creates a `run` and queues the LangGraph pipeline.

**Input:** raw JSON body + headers (`X-GitHub-Delivery`, `X-Hub-Signature-256`, `X-GitHub-Event`)  
**Output:** `{"status": "accepted", "delivery_id": "..."}`  
**Error codes:** `VALIDATION_ERROR` (400), `UNAUTHORIZED` (401 — bad signature), `CONFLICT` (409 — duplicate delivery), `INTERNAL_ERROR` (500)  
**Rate limit:** 100/min per IP

### `GET /runs`
Lists runs for the authenticated user's installation. Supports cursor pagination and optional `status` filter.

**Input (query):** `limit` (int, 1–100, default 20), `cursor` (string, optional), `status` (string, optional)  
**Output:**
```json
{
  "data": [
    {
      "id": "uuid",
      "repository_full_name": "string",
      "issue_number": 1,
      "issue_title": "string",
      "status": "string",
      "confidence": "string|null",
      "pr_url": "string|null",
      "created_at": "ISO8601",
      "completed_at": "ISO8601|null"
    }
  ],
  "next_cursor": "string|null",
  "has_more": true
}
```
**Error codes:** `UNAUTHORIZED` (401), `VALIDATION_ERROR` (400), `INTERNAL_ERROR` (500)  
**Rate limit:** 60/min per user

### `GET /runs/{run_id}`
Returns a single run with its steps (for the run detail page).

**Input (path):** `run_id` (uuid)  
**Output:**
```json
{
  "id": "uuid",
  "repository_full_name": "string",
  "issue_number": 1,
  "issue_title": "string",
  "issue_body": "string",
  "status": "string",
  "confidence": "string|null",
  "pr_url": "string|null",
  "pr_number": "integer|null",
  "test_output": "string|null",
  "root_cause": "string|null",
  "repo_language": "string",
  "triggered_by": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "completed_at": "ISO8601|null",
  "steps": [
    {
      "id": "uuid",
      "step": "string",
      "status": "string",
      "started_at": "ISO8601|null",
      "completed_at": "ISO8601|null",
      "output": "string|null",
      "error": "string|null",
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ]
}
```
**Error codes:** `NOT_FOUND` (404), `UNAUTHORIZED` (401), `FORBIDDEN` (403 — wrong installation), `INTERNAL_ERROR` (500)  
**Rate limit:** 60/min per user

### `GET /runs/{run_id}/events`
SSE stream of timeline events for a run. Client connects and receives step updates as they happen.

**Input (path):** `run_id` (uuid)  
**Output:** SSE events of type `step_updated` with JSON payload matching a `run_steps` row, plus `run_status_changed` when the parent run status changes  
**Error codes:** `NOT_FOUND` (404), `UNAUTHORIZED` (401), `FORBIDDEN` (403)  
**Rate limit:** 30/min per user (connection-based)

### `POST /runs/{run_id}/retry`
Re-triggers a failed or could_not_reproduce run. Requires `Idempotency-Key` header.

**Input (path):** `run_id` (uuid)  
**Input (header):** `Idempotency-Key` (string, required)  
**Output:** `{"status": "retry_queued", "run_id": "uuid"}`  
**Error codes:** `NOT_FOUND` (404), `UNAUTHORIZED` (401), `FORBIDDEN` (403), `CONFLICT` (409 — run not in retryable state), `INTERNAL_ERROR` (500)  
**Rate limit:** 5/min per run

### `GET /auth/session`
Returns the current session if authenticated, or empty if not.

**Input:** none (session cookie)  
**Output:**
```json
{
  "authenticated": true,
  "github_login": "string",
  "github_user_id": 123456
}
```
or `{"authenticated": false}`  
**Error codes:** `INTERNAL_ERROR` (500)  
**Rate limit:** 60/min per user

### `POST /auth/logout`
Clears the session cookie.

**Input:** none (session cookie)  
**Output:** `{"status": "logged_out"}`  
**Error codes:** `UNAUTHORIZED` (401), `INTERNAL_ERROR` (500)  
**Rate limit:** 30/min per user


## Idempotency
Write endpoints (`POST /runs/{run_id}/retry`, `POST /webhooks/github`) support the `Idempotency-Key` header. The server stores the key with the response body and status code. Replaying the same key returns the cached response without re-executing. Keys expire after 24 hours. Idempotency is not required for payments (no payments in v1 — ₹0 budget).

## Audit fields
Every table includes `created_at` and `updated_at` (timestamptz, defaults to `now()`). `runs` additionally has `triggered_by` (GitHub login of the user who added the label) and `completed_at` (terminal state timestamp). `webhook_events` has `processed_at`. `sessions` has `expires_at`. The `updated_at` column is maintained by a PostgreSQL trigger (see migration above); the JSON-file repository updates it on every write.

 now() - interval '8 minutes', now() - interval '8 minutes',
 'Opened draft PR #1 with red→green proof.', NULL,
 now() - interval '8 minutes', now() - interval '8 minutes');
```

    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_run_steps_updated_at BEFORE UPDATE ON run_steps
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_llm_cache_updated_at BEFORE UPDATE ON llm_cache
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```


CREATE INDEX idx_run_steps_run_step ON run_steps(run_id, step);
CREATE INDEX idx_run_steps_run_created ON run_steps(run_id, created_at);
```

        text token
        timestamptz expires_at
        timestamptz created_at
        timestamptz updated_at
    }
```

| `updated_at` | `timestamptz` | NO | `now()` | Audit |

**PK:** `id`  
**Indexes:**
- `idx_sessions_github_user` (github_user_id) UNIQUE — serves "lookup session by GitHub user" (auth middleware)
- `idx_sessions_expires` (expires_at) — serves "find expired sessions for cleanup"

| `updated_at` | `timestamptz` | NO | `now()` | Audit |

**PK:** `id`  
**Indexes:**
- `idx_llm_cache_key` (cache_key) — serves "lookup cached response by issue hash" (pipeline cache check)
- `idx_llm_cache_expires` (expires_at) — serves "find expired entries for cleanup" (background job)

**Indexes:**
- `idx_runs_installation_repo` (installation_id, repository_full_name) — serves "list runs for this installation/repo" (dashboard query)
- `idx_runs_issue` (repository_full_name, issue_number) — serves "find run by issue" (webhook dedup + status check)
- `idx_runs_status_created` (status, created_at DESC) — serves "list runs ordered by newest first" (dashboard)
- `idx_runs_created_at` (created_at DESC) — serves pagination by recency