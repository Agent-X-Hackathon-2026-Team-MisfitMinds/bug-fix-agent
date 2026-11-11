# Yash Vaidya New PRs - Detailed Review (Post-Fetch Update)

## Overview
After fetching the latest from origin, several new branches and commits have been discovered. This document reviews the **new PRs** that were not covered in the previous review.

## New Branches (PRs) from Yash

### 1. `docs/infra-T00-readme` - README Documentation

**Commits**:
- `b8dc9fe` - docs(readme): document setup, run, tests and CI for T-00 (116 lines added)
- `9ce3248` - docs(readme): correct how .env is resolved and started (12 lines changed)

**PR Details**:
- **Files Changed**: `README.md` (117 insertions, 1 deletion + 12 modifications)
- **Purpose**: Document the complete setup, run, test, and CI process for T-00

**Key Content Added** (from b8dc9fe):
- Project description and status (backend done, frontend/pipeline not wired)
- Layout documentation (apps/api/, apps/web/, packages/)
- Setup instructions (env contract, API + compose startup, sandbox image)
- Test suites (G6 unit, G7 integration, opt-in Docker tests)
- CI gates documentation
- What's NOT wired yet (web app, pipeline)

**Follow-up Fix** (9ce3248):
- Corrected how `.env` is resolved - Settings reads `.env` relative to working directory
- Starting uvicorn from `apps/api/` silently ignored root `.env`
- Documented root invocation with `--app-dir`
- Noted that `__Host-` cookies require Secure (HTTPS)

**Guide Alignment**: Section 9 - "Tool setup and usage" and Phase 0 Foundation

---

### 2. `docs/infra-T18-github-app-runbook` - GitHub App Setup Guide

**Commit**: `9318054` - docs(guide): add the GitHub App setup runbook for T-18 (220 lines)

**PR Details**:
- **File**: `guide/GitHub-App-Setup.md` (220 lines added)
- **Purpose**: Complete browser-based setup guide for GitHub App

**Content Structure**:
- **Who does what**: Browser steps (human) vs CLI steps (agent)
- **Step 1-5**: Create smee channel, create App, set permissions, install, put values in `.env`
- **Step 6-8**: Run API and tunnel, verify webhook + OAuth, read logs
- **Credential mapping**: Maps each GitHub App field to the `.env` key in `config.py`
- **Verification steps**: How to test each stage locally

**Key Sections**:
- GitHub App creation (browser flow)
- Permission configuration (issues, pull requests, contents)
- Webhook configuration (URL, secret, events)
- OAuth configuration (client ID, secret, callback URL)
- `.env` file template with all required keys
- Local verification steps

**Guide Alignment**: Section F - "Set up smee.io or ngrok for local webhook forwarding" and Section 9 - "GitHub App settings"

---

### 3. `fix/infra-T16-webhook-fail-closed` - Webhook Fail-Closed Test

**Commit**: `5a1e206` - test(webhook): fail closed when the webhook secret is unset (12 lines added)

**PR Details**:
- **File**: `apps/api/tests/unit/test_webhook.py` (+12 lines)
- **New Test**: `test_missing_secret_fails_closed`

**Test Implementation**:
```python
def test_missing_secret_fails_closed(monkeypatch: Any) -> None:
    monkeypatch.delenv("GITHUB_APP_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    response = post(payload(), delivery="delivery-no-secret")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"

    repo: RunRepo = app.state.run_repo
    runs, _ = repo.list(Caller(123, "octocat"))
    assert runs == []
```

**What It Tests**:
- When webhook secret is unset, the endpoint returns 500 INTERNAL_ERROR
- No run is created when secret is missing
- Fail-closed behavior (rejects rather than accepts)

**Context**: The revert of PR #12 dropped this test case, so main currently accepted the request path up to signature verification with an empty secret. This PR restores the fail-closed behavior.

**Guide Alignment**: Security checks - "GitHub webhook signature uses HMAC-SHA256; duplicate delivery IDs are rejected."

---

### 4. `fix/infra-T22-g7-integration-gate` - CI Integration Gate

**Commits**:
- `d294a6a` - ci(api): wire gate G7 (pytest integration) and move the route suite to it
- `53c3699` - ci(api): name the job after the gates it now runs

**PR Details**:
- **Files Changed**: `.github/workflows/api-ci.yml` (+3 lines), `apps/api/tests/unit/test_routes.py` → `apps/api/tests/integration/test_routes.py` (rename)
- **Purpose**: Wire gate G7 (pytest integration) as defined in docs/08-quality.md:427

**Key Changes**:

**Change 1** (d294a6a): Wire G7
```yaml
- name: G7 - pytest integration
  run: python -m pytest tests/integration -v
```
- Moved `test_routes.py` from `tests/unit/` to `tests/integration/`
- Added G7 step to CI workflow
- Rationale: G7 is defined as `pytest tests/integration/ -v` on every commit, but the workflow only ran tests/unit while tests/integration held nothing but the opt-in Docker test

**Change 2** (53c3699): Rename job
```yaml
- name: Lint, types and unit tests
+ name: Lint, types, unit and integration tests
```

**Guide Alignment**: 
- Section 8: "Backend integration `pytest tests/integration/ -v` Yash"
- docs/08-quality.md:427 defines G7 as `pytest tests/integration/ -v` on every commit

---

## Updated Branches - New Commits from Yash

### T-00: Repo Skeleton (updated)
- `db4c61f` - fix(api): make the T-00 skeleton boot and pass the API gates
  - Fixed main.py import error (webhooks/github.py never defined `router`)
  - Fixed /health response shape mismatch with test_health.py
  - Aligned pyproject.toml and requirements.txt with CI gates
  - 4 files changed, 36 insertions, 87 deletions

### T-18: Webhook Tunnel (updated)
- `7dea71e` - fix(api): ignore empty env values so the container can boot
  - docker compose injects unset variables as empty strings
  - COOKIE_SECURE="" failed bool parsing, crash-looping the api container
  - env_ignore_empty makes Settings fall back to defaults for blank values
  - 2 files changed, 26 insertions

### T-00: README (updated)
- `b8dc9fe` - docs(readme): document setup, run, tests and CI for T-00
- `9ce3248` - docs(readme): correct how .env is resolved and started

### T-14: Docker Sandbox (updated)
- CI workflow additions (457613e, 18df732)

### T-16: Webhook (updated)
- CI workflow additions (97da373, 257d12a)

### T-21: Security Headers (updated)
- CI workflow additions (ed79724)

### T-06: Data Schemas (updated)
- `82bb88b` - merge: bring the T-00 skeleton fix into T-06

### T-08: OAuth (updated)
- `e53ba73` - CI workflow additions

### T-14 Tests: Sandbox Integration (updated)
- `689cf7c` - Merge pull request #14 (revert-12)

---

## Summary of New Work

### By Category:

| Category | New PRs | Description |
|----------|---------|-------------|
| **Documentation** | docs/infra-T00-readme, docs/infra-T18-github-app-runbook | README setup guide + GitHub App runbook |
| **Testing** | fix/infra-T16-webhook-fail-closed | Fail-closed webhook secret test |
| **CI/CD** | fix/infra-T22-g7-integration-gate | Wire G7 integration gate, rename job |
| **Bug Fixes** | T-00 skeleton fix, T-18 empty env fix | Boot fixes for container |

### By Guide Section:

| Guide Section | New Work |
|---------------|----------|
| Phase 0: Foundation | README documentation (T-00) |
| Section B: FastAPI/data | Skeleton boot fix (T-00) |
| Section C: Docker sandbox | CI workflow integration |
| Section F: Webhooks | Fail-closed test (T-16), GitHub App runbook (T-18) |
| Section F: CI checks | G7 integration gate (T-22) |

### Key Improvements:

1. **Documentation Completeness**: README now covers full setup, run, test, and CI process
2. **Security Hardening**: Fail-closed webhook secret test ensures no runs created without proper secret
3. **CI Coverage**: G7 integration gate now runs route tests on every commit
4. **Container Stability**: Empty env values no longer crash-loop the API container
5. **Developer Experience**: GitHub App setup runbook enables browser-based credential setup

### Assessment:

All new PRs are well-aligned with the team execution guide and address specific gaps:
- ✅ T-00 README was still a two-line placeholder → now fully documented
- ✅ GitHub App setup was browser-only → now has a complete runbook
- ✅ Webhook secret fail-closed behavior was dropped in revert → restored with test
- ✅ G7 integration gate was defined but not wired → now runs on every commit
- ✅ T-00 skeleton couldn't boot → fixed import and health shape issues
- ✅ Empty env values crashed container → now handled gracefully

---
*Review of new PRs from Yash Vaidya (post-fetch update)*
*New branches: docs/infra-T00-readme, docs/infra-T18-github-app-runbook, fix/infra-T16-webhook-fail-closed, fix/infra-T22-g7-integration-gate*
*Updated branches: T-00, T-06, T-07, T-08, T-14, T-16, T-21, T-18 (fix), T-14 (tests)*