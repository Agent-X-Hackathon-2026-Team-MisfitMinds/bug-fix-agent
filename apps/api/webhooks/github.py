"""GitHub webhook handling: signature verification and delivery dedup."""
import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter, Request
from pydantic import ValidationError

from errors import AppError, ConflictError, Unauthorized, ValidationFailed
from schemas import GitHubWebhookPayload

router = APIRouter()

_processed_deliveries: set[str] = set()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature[len("sha256="):])


def _webhook_secret() -> str:
    secret = os.getenv("GITHUB_APP_WEBHOOK_SECRET") or os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise AppError("Webhook secret is not configured")
    return secret


def is_agent_fix_labeled(payload: GitHubWebhookPayload) -> bool:
    if payload.action != "labeled" or payload.issue is None:
        return False
    labels = payload.issue.get("labels", [])
    return any(str(label.get("name", "")).lower() == "agent-fix" for label in labels)


def extract_run_fields(payload: GitHubWebhookPayload) -> dict[str, Any] | None:
    issue = payload.issue
    if issue is None or not is_agent_fix_labeled(payload):
        return None
    repository = payload.repository
    return {
        "installation_id": int((payload.installation or {}).get("id") or 0),
        "repository_full_name": str(repository.get("full_name", "")),
        "issue_number": int(issue.get("number", 0)),
        "issue_title": str(issue.get("title", "")),
        "issue_body": str(issue.get("body") or ""),
        "triggered_by": str(payload.sender.get("login", "")),
    }


@router.post("/github")
async def github_webhook(request: Request) -> dict[str, str]:
    delivery_id = request.headers.get("X-GitHub-Delivery")
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")
    if not delivery_id or not signature or not event:
        raise ValidationFailed("Missing required webhook headers")

    body = await request.body()
    if not verify_webhook_signature(body, signature, _webhook_secret()):
        raise Unauthorized("Invalid webhook signature")

    if delivery_id in _processed_deliveries:
        raise ConflictError("Duplicate webhook delivery")
    _processed_deliveries.add(delivery_id)

    try:
        payload = GitHubWebhookPayload.model_validate_json(body)
    except ValidationError as exc:
        raise ValidationFailed("Invalid webhook payload") from exc

    extract_run_fields(payload)
    return {"status": "accepted", "delivery_id": delivery_id}
