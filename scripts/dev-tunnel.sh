#!/usr/bin/env bash
# Forwards GitHub webhook deliveries to the local API during development.
set -euo pipefail

target="${WEBHOOK_TARGET:-http://localhost:8000/webhooks/github}"

if [[ -z "${SMEE_URL:-}" ]]; then
  cat >&2 <<'MSG'
SMEE_URL is not set.

  1. Open https://smee.io/new and copy the channel URL it gives you.
  2. Point the GitHub App webhook at that same URL.
  3. Re-run:  SMEE_URL=https://smee.io/your-channel scripts/dev-tunnel.sh
MSG
  exit 1
fi

exec npx --yes smee-client --url "$SMEE_URL" --target "$target" --path /webhooks/github
