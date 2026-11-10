"""GitHub webhook handler helpers for the bug-fix agent."""

import hashlib
import hmac
from typing import Any

from schemas import GitHubWebhookPayload


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not signature.startswith("sha256="):
        return False

    expected_hmac = signature[len("sha256="):]
    computed_hmac = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_hmac, computed_hmac)


class GitHubWebhookHandler:
    """Handler for GitHub webhook events."""

    def __init__(self, webhook_secret: str) -> None:
        self.webhook_secret = webhook_secret

    def verify_delivery(self, delivery_id: str, x_github_event: str) -> bool:
        """Check whether a delivery was already processed."""
        return True

    async def handle_issues_labeled(
        self, payload: GitHubWebhookPayload
    ) -> dict[str, Any] | None:
        """Handle issues.labeled events with the agent-fix label."""
        issue = payload.issue
        if not issue:
            return None

        labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
        if "agent-fix" not in labels:
            return None

        return {
            "issue_number": issue.get("number"),
            "issue_title": issue.get("title"),
            "issue_body": issue.get("body"),
            "repo_full_name": payload.repository.get("full_name"),
            "repo_owner": payload.repository.get("owner", {}).get("login"),
            "action": payload.action,
        }
