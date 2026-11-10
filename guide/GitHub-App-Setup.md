# GitHub App setup (T-18)

How to create and wire the GitHub App this backend needs. Written so a person can
follow it in a browser and an AI agent can pick up from step 6 without ever seeing a
secret.

## Who does what

| Step | Who |
|---|---|
| 1–5: create the smee channel, create the App, set permissions, install it, put values in `.env` | **A human with the GitHub account.** GitHub has no API for creating an App; it is a browser flow on your account. |
| 6–8: run the API and tunnel, verify webhook + OAuth, read logs | Either. The agent can do all of this once `.env` exists. |

Do **not** paste the private key, client secret or webhook secret into chat, an issue
or a PR. The agent only needs to know *that* the values are set, and can check that
itself (see step 7).

## Before you start

- The seeded demo repository exists (T-17). You need admin on it to install the App.
- Node.js available (the tunnel runs through `npx`).
- The API runs locally on port 8000 and reads `.env` from the **process working
  directory** — see step 5, this trips people up.

## 1 · Create a tunnel URL first

The App needs a public webhook URL, so create the tunnel before the App.

1. Open <https://smee.io/new> (no account needed) and copy the channel URL, e.g.
   `https://smee.io/AbCdEf123456`.
2. Keep that tab; the URL goes into the App in step 2 and into the tunnel command in
   step 6.

`smee.io` forwards every webhook to your machine, so nothing needs a public IP. If
you prefer ngrok, `ngrok http 8000` works too — use `https://<id>.ngrok-free.app/webhooks/github`
as the webhook URL and skip the smee client in step 6.

## 2 · Create the GitHub App

Go to **Settings → Developer settings → GitHub Apps → New GitHub App**
(<https://github.com/settings/apps/new>).

| Field | Value |
|---|---|
| GitHub App name | `fixie-misfitminds` (must be globally unique; add a suffix if taken) |
| Homepage URL | `https://github.com/Agent-X-Hackathon-2026-Team-MisfitMinds/bug-fix-agent` |
| Webhook → Active | **checked** |
| Webhook URL | the smee URL from step 1 |
| Webhook secret | generate a long random string, e.g. `openssl rand -hex 32`. **Copy it — step 5 needs it.** |
| SSL verification | Enable |
| Identifying and authorizing users → Callback URL | `http://localhost:8000/auth/callback` |
| Request user authorization (OAuth) during installation | leave unchecked — the app starts OAuth from `/auth/github` itself |
| Expire user authorization tokens | leave unchecked |
| Webhook → Subscribe to events | **Issues** |

The callback is the exact `redirect_uri` this code sends (`auth/oauth.py:30`), so a
trailing slash or a different port will fail with a `redirect_uri` mismatch.

## 3 · Permissions

Repository permissions (minimum for the agent to read an issue, push a branch and open
a PR):

| Permission | Access |
|---|---|
| Contents | Read and write |
| Issues | Read and write |
| Pull requests | Read and write |
| Metadata | Read-only (forced) |

Account permissions: none. Organisation permissions: none.

Click **Create GitHub App**.

## 4 · Collect the credentials

On the App's settings page:

| Value | Where |
|---|---|
| **App ID** | top of the page, a number like `1234567` |
| **Client ID** | under "About", starts with `Iv1.` or `Iv23` |
| **Client secret** | "Generate a new client secret" → copy it once |
| **Private key** | scroll to "Private keys" → "Generate a private key" → downloads a `.pem`. Keep it outside the repo. |
| **Webhook secret** | the string you generated in step 2 |

## 5 · Install the App and write `.env`

**Install:** left sidebar → **Install App** → choose your account → **Only select
repositories** → pick the seeded demo repo → Install.

**Write `.env`** at the repo root (copy `.env.example` first). The values this code
actually reads:

```dotenv
GITHUB_APP_CLIENT_ID=Iv1.xxxxxxxxxxxx
GITHUB_APP_CLIENT_SECRET=<client secret>
GITHUB_APP_WEBHOOK_SECRET=<webhook secret>
SESSION_SECRET=<openssl rand -hex 32>
API_BASE_URL=http://localhost:8000
WEB_ORIGIN=http://localhost:3000
COOKIE_SECURE=true
```

Notes, all verified against `apps/api/config.py`:

- `SESSION_SECRET` signs the OAuth state and encrypts tokens. The legacy alias
  `API_SECRET_KEY` still works, but prefer `SESSION_SECRET`.
- `GITHUB_APP_ID` and the private key are **not read by any code yet** — keep them in
  `.env` for the later installation-token work, but their absence will not stop the
  webhook or OAuth from working today.
- Blank values fall back to defaults (`env_ignore_empty`), so an empty key is never a
  crash — it is a silent default, which is why step 7 checks behaviour, not just the
  file.
- **`.env` is read from the working directory.** Starting uvicorn from `apps/api`
  ignores a root `.env`. Run from the repo root with `--app-dir apps/api` (step 6) or
  copy the file to `apps/api/.env`.
- `.env` is git-ignored. Never commit it, and never add a `NEXT_PUBLIC_*` copy of
  `GITHUB_APP_CLIENT_SECRET`, `SESSION_SECRET` or the webhook secret.

## 6 · Run the API and the tunnel

Terminal 1, from the repo root:

```bash
python -m venv .venv
.venv/Scripts/activate            # source .venv/bin/activate on macOS/Linux
pip install -r apps/api/requirements.txt
python -m uvicorn --app-dir apps/api main:app --reload --port 8000
```

Terminal 2:

```bash
npx --yes smee-client --url https://smee.io/<your-channel> --target http://localhost:8000/webhooks/github --path /webhooks/github
```

`scripts/dev-tunnel.sh` used to wrap this, but it was reverted with #12 and is not on
`main`; the one-liner above is the same thing.

## 7 · Verify

**a) The API is up and the secret is loaded.**

```bash
curl -s localhost:8000/health                       # {"status":"ok"}
```

A missing webhook secret returns `500 INTERNAL_ERROR` on every delivery (fail-closed
by design), so if deliveries succeed, the secret is loaded.

**b) A signed request reaches the handler.** This proves the secret in `.env` matches
what you think it is, without going through GitHub:

```bash
BODY='{"action":"labeled","issue":{"number":1,"title":"t","body":"b","labels":[{"name":"agent-fix"}]},"repository":{"full_name":"fixie-demo/seeded-repo"},"sender":{"login":"octocat"},"installation":{"id":123}}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$GITHUB_APP_WEBHOOK_SECRET" | sed 's/^.* //')
curl -s -X POST localhost:8000/webhooks/github \
  -H "X-GitHub-Delivery: local-verify-1" \
  -H "X-GitHub-Event: issues" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  --data "$BODY"
```

Expect `{"status":"accepted","delivery_id":"local-verify-1"}`. This also creates one
run, which is fine — it is in-memory and disappears on restart.

**c) A real delivery arrives.** Label any issue in the demo repo with `agent-fix`,
then check **App settings → Advanced → Recent Deliveries**: the delivery should show a
`200` and the response body `{"status":"accepted",...}`.

**d) OAuth works.** Open <http://localhost:8000/auth/github> in Chrome, authorize, and
you should land on `http://localhost:3000/dashboard`. Then:

```bash
curl -s localhost:8000/auth/session -b cookies.txt   # {"authenticated": true, ...}
```

If the browser rejects the session cookie, see the table below — it is the `__Host-`
prefix, not a code bug.

## 8 · Troubleshooting

| Symptom | Cause |
|---|---|
| `400 VALIDATION_ERROR` "Missing required webhook headers" | The request did not come through the tunnel, or a manual test omitted `X-GitHub-Delivery` / `X-GitHub-Event` / `X-Hub-Signature-256`. |
| `400 VALIDATION_ERROR` "Webhook payload is missing run fields" | Event is not `issues` with `action: labeled`, or `installation.id` / `repository.full_name` / `issue.number` / `sender.login` is absent. |
| `401 UNAUTHORIZED` | Webhook secret in the App differs from `GITHUB_APP_WEBHOOK_SECRET`. Regenerate both, update `.env`, restart. |
| `409 CONFLICT` | Same `X-GitHub-Delivery` already processed. Expected on redelivery; it is the dedup working. |
| `500 INTERNAL_ERROR` on every delivery | Secret is empty — `.env` not loaded (wrong working directory) or `env_ignore_empty` fell back to the default. |
| Nothing in Recent Deliveries | App not installed on that repo, webhook URL wrong, or smee client not running. |
| OAuth redirects back with `?error=oauth_state` | State cookie missing or older than 10 minutes, or the callback URL does not match exactly. |
| `redirect_uri` mismatch from GitHub | Callback URL must be `http://localhost:8000/auth/callback`. |
| Session cookie never appears | `__Host-session_id` needs `Secure`; use Chrome on `http://localhost` or HTTPS. Only non-localhost HTTP needs extra work. |

## 9 · Security rules

- `.env` and the `.pem` stay out of git. If either is committed, rotate the secret or
  delete and regenerate the private key.
- Install the App on the demo repo only, never "All repositories".
- The private key is used to mint installation tokens (branch push, PR creation). If
  it leaks, an attacker can act as the App on that repo.
- Revoke with **App settings → Delete App** and clear the credentials from `.env` when
  the hackathon is over.

## 10 · Checklist

- [ ] smee channel created and URL copied
- [ ] App created, webhook active, callback `http://localhost:8000/auth/callback`
- [ ] Events: Issues. Permissions: Contents RW, Issues RW, Pull requests RW
- [ ] Client secret, webhook secret and private key generated and stored safely
- [ ] App installed on the seeded demo repo only
- [ ] `.env` has client id, client secret, webhook secret and `SESSION_SECRET`
- [ ] `curl localhost:8000/health` → 200
- [ ] Signed local POST → `accepted`
- [ ] Label an issue `agent-fix` → Recent Deliveries shows 200
- [ ] `http://localhost:8000/auth/github` → dashboard, `/auth/session` authenticated

When done, hand the agent: the App slug, App ID, Client ID (these are not secret) and
the path to `.env`. It can verify steps 7a–7d itself without the secret values.
