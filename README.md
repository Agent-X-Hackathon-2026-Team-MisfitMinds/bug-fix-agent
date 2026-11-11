# bug-fix-agent

Bug fix agent for the Agent-X Hackathon 2026 — Team MisfitMinds.

Label a GitHub issue with `agent-fix` and the agent reproduces the bug, proposes a
fix, verifies it in an isolated sandbox and opens a pull request. A FastAPI service
does the work and streams progress over SSE; a Next.js dashboard shows each run.

## Status

- **Backend — done and green on `main`:** GitHub App OAuth with encrypted sessions,
  run + retry routes, SSE stream, verified webhook with delivery dedup, Docker
  sandbox runner, security headers, rate limiting, and the API CI gates.
- **Frontend — available in `apps/web`.** The demo workspace uses example data;
  live backend sign-in, run data, retry and SSE still require integration testing.
- **Pipeline — not wired.** The webhook creates a run and calls
  `app.state.pipeline_queue`, which is still `None`; nothing processes runs until
  the agent graph is connected.

## Layout

```
apps/api/            FastAPI service (all backend work)
  auth/              GitHub OAuth, session cookies, token encryption
  data/              in-memory repositories (no database, per ADR-006)
  pipeline/          Docker sandbox runner
  routes/            run endpoints + SSE
  webhooks/          GitHub signature verification and run creation
  tests/unit/        pytest unit suite (G6)
  tests/integration/ pytest route suite (G7) + opt-in Docker sandbox tests
apps/web/            Next.js dashboard (in progress)
packages/shared/     shared schema notes
docs/                product, architecture, security and quality specs
```

## Requirements

- Python 3.12
- Docker (only for the sandbox and the compose stack)
- Node.js 20+ (only for the web app)

## Configuration

The server reads a `.env` from the **process working directory**. Running uvicorn
from the repo root (as shown below) means the root `.env` is the one that applies;
if you start it from `apps/api` instead, copy the file to `apps/api/.env`.

```bash
cp .env.example .env   # then fill in real values; .env is git-ignored
```

The server reads `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`,
`GITHUB_APP_WEBHOOK_SECRET`, `SESSION_SECRET`, `API_BASE_URL`, `WEB_ORIGIN` and
`COOKIE_SECURE`. `config.py` also accepts the shorter legacy names
(`GITHUB_CLIENT_ID`, `GITHUB_WEBHOOK_SECRET`, ...). Blank values fall back to the
development defaults, so an unset variable never crashes the process.

Leave `COOKIE_SECURE=true`. The session cookie is `__Host-session_id`, and browsers
reject `__Host-` cookies that lack the `Secure` attribute; Chrome accepts them over
http://localhost, but any other host needs HTTPS.

## Run the API

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use source .venv/bin/activate elsewhere
pip install -r apps/api/requirements.txt
python -m uvicorn --app-dir apps/api main:app --reload --port 8000
```

`--app-dir` puts `apps/api` on `sys.path` without changing the working directory, so
the root `.env` is picked up.

```bash
curl localhost:8000/health      # {"status":"ok"}
```

Open http://localhost:8000/docs for the OpenAPI page.

Or with Docker:

```bash
docker compose up -d api        # publishes 8000; ./apps/api/data is bind-mounted
```

The bind mount is deliberate: `/app/data` also holds the `data` package's Python
modules, so a named volume would shadow them.

## Sandbox image

```bash
docker build -f apps/api/docker/sandbox.Dockerfile -t bug-fix-agent-sandbox:latest apps/api/docker
```

The container runs as a non-root user with no network, a read-only root filesystem,
memory/CPU caps and a hard timeout.

## Tests

```bash
cd apps/api
python -m pytest tests/unit -q            # G6
python -m pytest tests/integration -v     # G7
python -m ruff check .                    # G3
python -m mypy --strict .                 # G4
```

Docker sandbox tests are opt-in:

```bash
RUN_DOCKER_TESTS=1 python -m pytest tests/integration -q
```

## CI

[`.github/workflows/api-ci.yml`](.github/workflows/api-ci.yml) runs G3 (ruff),
G4 (mypy --strict), G6 (unit) and G7 (integration) on every push to `main` and every
pull request that touches `apps/api`. A second advisory job runs `pip-audit` (G13)
and reports vulnerable pins without failing the build.

## Demo flow

Once the frontend and the agent graph are connected: open the dashboard, label a
seeded issue with `agent-fix`, and watch the run move through
`read → reproduce → diagnose → fix → verify → pr` on `/dashboard/runs/<id>`.

## Frontend setup (apps/web)

From the repository root:

```bash
cd apps/web
npm ci --workspaces=false
npx playwright install chromium webkit
npm run dev
```

Open http://localhost:3000. The demo workspace uses example data. Real GitHub sign-in and dashboard data require the backend setup and an `API_BACKEND_URL` supplied by the team. Do not commit credentials.

Run the frontend checks from `apps/web`:

```bash
npm run check
npm run test
npx playwright test --workers=1
```

The Playwright command runs both Chromium and WebKit. On Windows WebKit only, `keyboard can navigate the app shell with a visible focus indicator` is skipped: in our Windows Playwright WebKit diagnostic, Tab skipped ordinary links. It still runs in Chromium and Linux WebKit. Revisit this limitation when the browser or Playwright is updated.

The browser tests use mocked API responses and do not verify live backend integration. Playwright WebKit is not the same as testing Safari itself.
