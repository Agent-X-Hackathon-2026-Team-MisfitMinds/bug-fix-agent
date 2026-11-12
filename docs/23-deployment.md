# Deployment Guide

Fixie is two apps: `apps/api` (FastAPI, in-memory sessions/runs, Docker sandbox)
and `apps/web` (Next.js, proxies `/api`, `/auth`, `/webhooks` to the API).
The supported production shape is **one public origin** serving both, because the
session cookie is `__Host-`-prefixed and the GitHub App needs stable URLs.

```
                 ┌──────────────── one public origin (HTTPS) ───────────────┐
browser/GitHub ──►  web:3000 (Next standalone)  ──rewrites──►  api:8000    │
                 │  (Caddy terminates TLS; or a Cloudflare tunnel instead)  │
                 └──────────────────────────────────────────────────────────┘
                                        api spawns sandbox containers
                                        (bug-fix-agent-sandbox:latest, siblings)
```

## Prerequisites

- A host with Docker (Compose v2). For the sandbox, the **host daemon must be
  reachable** - the API creates sibling containers, so no Docker-in-Docker is
  needed, but the socket must be mounted.
- The sandbox image, built once on that daemon:

  ```bash
  docker build -f apps/api/docker/sandbox.Dockerfile -t bug-fix-agent-sandbox:latest apps/api/docker
  ```

- A root `.env` (copy from `.env.example`). Compose reads it for substitution.
  Required: the `GITHUB_*` values, `SESSION_SECRET`, `GEMINI_API_KEY`,
  `API_BASE_URL`, `WEB_ORIGIN`. Optional: `GEMINI_MODEL`,
  `GEMINI_FALLBACK_MODELS` (failover models), `DOCKER_GID`.
- Set `API_BASE_URL` and `WEB_ORIGIN` to the **public site URL** (not a
  localhost), with `COOKIE_SECURE=true`. The GitHub App callback is
  `<site>/auth/callback` and the webhook is `<site>/webhooks/github` - both go
  through the web proxy.

## Option A - cloud VM + docker compose + real domain (recommended)

1. Provision any small VM (2 GB RAM minimum - the sandbox caps tests at 512 MB)
   with Docker installed, then clone the repo.
2. `stat -c '%g' /var/run/docker.sock` on the VM and put the result in `.env`
   as `DOCKER_GID` (often `999` or `998`) so the API's non-root user may use the socket.
3. Point your domain's A/AAAA record at the VM and add `SITE_DOMAIN=app.example.com`
   to `.env` (`API_BASE_URL` / `WEB_ORIGIN` = `https://app.example.com`).
4. Build the sandbox image (command above), then:

   ```bash
   docker compose --profile tls up -d --build
   ```

   Caddy obtains and renews the certificate automatically (ports 80/443 open).
5. In the GitHub App settings, set callback `<site>/auth/callback` and webhook
   `<site>/webhooks/github`.
6. Verify: `curl https://<site>/api/auth/session` returns `{"authenticated":false}`,
   the dashboard sign-in works, and a `agent-fix` label event arrives in the API
   logs as `POST /webhooks/github 200`.

## Option B - this laptop + Cloudflare named tunnel (free, stable URL)

Named tunnels keep **one URL forever** (unlike quick `trycloudflare` links,
which rotate on every restart and once lost can never be re-registered).

1. Add a domain to Cloudflare (free plan works) - or reuse one.
2. `cloudflared tunnel login`, then:

   ```bash
   cloudflared tunnel create fixie
   cloudflared tunnel route dns fixie app.example.com
   ```

3. Point the tunnel at the compose stack (no ports 80/443 needed):

   ```yaml
   # ~/.cloudflared/config.yml
   tunnel: <tunnel-id>
   credentials-file: ~/.cloudflared/<tunnel-id>.json
   ingress:
     - hostname: app.example.com
       service: http://localhost:3000
     - service: http_status:404
   ```

4. `docker compose up -d --build` (without the `tls` profile - the tunnel
   replaces Caddy) and run `cloudflared tunnel run fixie` (install as a service
   for auto-start).
5. Same GitHub App + verification steps as Option A, with `API_BASE_URL` /
   `WEB_ORIGIN` = `https://app.example.com`.

## Current interim setup (Vercel + quick tunnel)

Right now the web runs on Vercel (`fixie-steel.vercel.app`) whose rewrites
target a **quick tunnel** to the API. This works but has two fragile edges:

- If the laptop sleeps/reboots, the quick tunnel dies and its URL is lost
  forever (`Unauthorized: Tunnel not found` is unrecoverable). Then:
  start a new tunnel, update the Vercel env `API_BACKEND_URL` to the new URL,
  redeploy, and update the GitHub App webhook URL.
- In-memory state means every API restart signs everyone out and clears the
  runs list.

Options A/B above remove both problems.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Dashboard stuck on skeleton | API unreachable through the proxy - check `curl <site>/api/auth/session` and the API's `/health` |
| GitHub login redirects to an old domain | `API_BASE_URL`/`WEB_ORIGIN` in the API `.env` are stale; set them to the current site and restart the API |
| Webhook deliveries fail | GitHub App webhook URL points at a dead URL; update it to `<site>/webhooks/github` |
| Runs fail with sandbox error | Sandbox image missing on the daemon - rebuild it (command above), or the API can't reach the socket - check `DOCKER_GID` |
| `401` from Gemini on the first LLM step | Key invalid/rotated - update `GEMINI_API_KEY` and restart; failover only helps with per-model overload, not bad keys |
| Everything resets after a restart | Expected: sessions/runs are in-memory by design (ADR-006) |
