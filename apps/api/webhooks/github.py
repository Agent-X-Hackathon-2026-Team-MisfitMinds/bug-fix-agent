"""GitHub webhook handling: signature, dedup and run creation."""
import hashlib
import hmac
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from config import get_settings
from data.run_repo import RunRepo
from data.webhook_repo import DeliveryStore
from errors import AppError, ConflictError, Unauthorized, ValidationFailed
from rate_limit import rate_limit
from schemas import GitHubWebhookPayload

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature[len("sha256="):])


def _webhook_secret() -> str:
    secret = get_settings().github_webhook_secret.get_secret_value()
    if not secret:
        raise AppError("Webhook secret is not configured")
    return secret


TRIGGER_ACTIONS = frozenset({"opened", "labeled"})


def is_agent_fix_labeled(payload: GitHubWebhookPayload) -> bool:
    if payload.action not in TRIGGER_ACTIONS or payload.issue is None:
        return False
    labels = payload.issue.get("labels", [])
    return any(str(label.get("name", "")).lower() == "agent-fix" for label in labels)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def extract_run_fields(payload: GitHubWebhookPayload) -> dict[str, Any] | None:
    issue = payload.issue
    if issue is None or not is_agent_fix_labeled(payload):
        return None
    repository = payload.repository
    return {
        "installation_id": _as_int((payload.installation or {}).get("id")),
        "repository_full_name": str(repository.get("full_name", "")),
        "issue_number": _as_int(issue.get("number")),
        "issue_title": str(issue.get("title", "")),
        "issue_body": str(issue.get("body") or ""),
        "triggered_by": str(payload.sender.get("login", "")),
    }


def _get_repo(request: Request) -> RunRepo:
    return cast(RunRepo, request.app.state.run_repo)


def _get_deliveries(request: Request) -> DeliveryStore:
    return cast(DeliveryStore, request.app.state.webhook_deliveries)


@router.post("/github", dependencies=[Depends(rate_limit("webhook", 100))])
async def github_webhook(request: Request) -> dict[str, str]:
    delivery_id = request.headers.get("X-GitHub-Delivery")
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")
    if not delivery_id or not signature or not event:
        raise ValidationFailed("Missing required webhook headers")

    body = await request.body()
    if not verify_webhook_signature(body, signature, _webhook_secret()):
        raise Unauthorized("Invalid webhook signature")

    try:
        payload = GitHubWebhookPayload.model_validate_json(body)
    except ValidationError as exc:
        raise ValidationFailed("Invalid webhook payload") from exc

    fields = extract_run_fields(payload)
    if fields is not None:
        if (
            fields["installation_id"] <= 0
            or not fields["repository_full_name"]
            or fields["issue_number"] <= 0
            or not fields["triggered_by"]
        ):
            raise ValidationFailed("Webhook payload is missing run fields")

    if not _get_deliveries(request).check_and_add(delivery_id):
        raise ConflictError("Duplicate webhook delivery")

    if fields is not None:
        run = _get_repo(request).create(**fields)
        queue = getattr(request.app.state, "pipeline_queue", None)
        if callable(queue):
            queue(run.id)

    return {"status": "accepted", "delivery_id": delivery_id}
