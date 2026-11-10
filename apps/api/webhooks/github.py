"""GitHub webhook handler for the bug-fix agent."""

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .schemas import *
import hmac
import hashlib
import base64
from typing import Optional


# Bearer token security scheme
security = HTTPBearer(auto_error=False)


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not signature:
        return False
    
    # GitHub sends signatures in format: sha256=<hex_hmac>
    if not signature.startswith("sha256="):
        return False
    
    expected_hmac = signature[7:]  # Remove "sha256=" prefix
    computed_hmac = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    # Secure comparison to prevent timing attacks
    return hmac.compare_digest(expected_hmac, computed_hmac)


class GitHubWebhookHandler:
    """Handler for GitHub webhook events."""
    
    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret
    
    def verify_delivery(
        self,
        delivery_id: str,
        x_gitHub_event: str,
    ) -> bool:
        """Verify webhook delivery ID to prevent duplicates.
        
        GitHub recommends deduplicating on X-GitHub-Delivery header.
        """
        # In production, store delivered delivery IDs in Redis or DB
        # For now, always accept (basic implementation)
        return True
    
    async def handle_issues_labeled(self, payload: GitHubWebhookPayload) -> Optional[Dict]:
        """Handle issues.labeled events.
        
        Only trigger when label 'agent-fix' is added.
        """
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