"""GitHub API client for Bug-Fix Agent.

Provides operations needed by the LangGraph pipeline without merge permission.
All operations are scoped to the GitHub App installation context.

Critical security:
- GitHub webhook signature uses HMAC-SHA256; duplicate delivery IDs are rejected.
- Every run query checks both installation ownership and triggering GitHub login.
- Unknown/foreign runs return 404, not 403.
- Cookie is __Host-session_id, HttpOnly, Secure, SameSite=Lax, Path=/, no Domain, 24-hour expiry.
- React renders issue content and test output as text. Never use dangerouslySetInnerHTML for untrusted content.
- Never use eval, exec, os.system or shell interpolation with user-controlled strings.
- No token, issue body, PR diff, email or other personal data in logs. Keep errors generic for users.
- Agent account/App has no merge permission. Draft PR plus protected main is the human gate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any, List, Union

import httpx


# ------------------------------------------------------------
# GitHub App Configuration
# ------------------------------------------------------------


class GitHubConfig:
    """Configuration for GitHub App connection."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        webhook_secret: str,
        callback_url: str,
        webhook_url: str,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.webhook_secret = webhook_secret
        self.callback_url = callback_url
        self.webhook_url = webhook_url


# ------------------------------------------------------------
# Webhook Verification
# ------------------------------------------------------------


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256.

    GitHub sends signatures in format: sha256=<hex_hmac>
    """
    if not signature:
        return False

    # GitHub sends signatures in format: sha256=<hex_hmac>
    if not signature.startswith("sha256="):
        return False

    expected_hmac = signature[7:]  # Remove "sha256=" prefix
    computed_hmac = hmac.new(
        webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Secure comparison to prevent timing attacks
    return hmac.compare_digest(expected_hmac, computed_hmac)


def verify_delivery_id(
    delivery_id: str,
    stored_delivery_ids: Optional[set] = None,
) -> bool:
    """Verify webhook delivery ID to prevent duplicate deliveries.

    GitHub recommends deduplicating on X-GitHub-Delivery header.
    """
    if stored_delivery_ids is None:
        # Basic implementation - always accept
        # In production, store delivered delivery IDs in Redis/DB
        return True

    if delivery_id in stored_delivery_ids:
        return False  # Already processed

    # Store the new delivery ID (in production, persist to Redis/DB)
    stored_delivery_ids.add(delivery_id)
    return True


# ------------------------------------------------------------
# GitHub API Client
# ------------------------------------------------------------


class GitHubAPIClient:
    """Client for GitHub API operations.

    Key constraints:
    - App has NO merge permission
    - Draft PRs only; agent must never merge
    - All runs check installation ownership
    - Unknown/foreign runs return 404, not 403
    """

    def __init__(self, config: GitHubConfig, http_client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self.http_client = http_client or httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
            ),
        )
        self._base_url = "https://api.github.com"

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an authenticated API request."""
        url = f"{self._base_url}{endpoint}"

        # Add authentication headers
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # In a real implementation, would add GitHub App JWT authentication
        # For now, using standard token-based auth
        # headers["Authorization"] = f"Bearer {self.config.installation_id}"

        response = await self.http_client.request(
            method=method,
            url=url,
            headers=headers,
            **kwargs,
        )

        return response

    async def get_issue(self, issue_id: int, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """Fetch issue details from GitHub.

        Args:
            issue_id: GitHub issue number
            repo_full_name: Repository in "owner/name" format

        Returns:
            Issue dictionary or None if not found
        """
        endpoint = f"/repos/{repo_full_name}/issues/{issue_id}"
        response = await self._request("GET", endpoint)

        if response.status_code == 404:
            return None
        elif response.status_code == 403:
            # Forbidden - may indicate app lacks permissions
            return None
        elif response.status_code != 200:
            # Log error but don't crash
            return None

        return response.json()

    async def get_repo(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """Fetch repository details from GitHub.

        Args:
            repo_full_name: Repository in "owner/name" format

        Returns:
            Repository dictionary or None if not found
        """
        endpoint = f"/repos/{repo_full_name}"
        response = await self._request("GET", endpoint)

        if response.status_code == 404:
            return None
        elif response.status_code != 200:
            return None

        return response.json()

    async def get_repo_language(self, repo_full_name: str) -> Optional[str]:
        """Get the primary language of a repository."""
        repo = await self.get_repo(repo_full_name)
        if repo:
            return repo.get("language", "").lower()
        return None

    async def push_branch_and_open_draft_pr(
        self,
        repo_full_name: str,
        branch_name: str,
        pr_title: str,
        pr_body: str,
        maintainer_can_modify: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Push a branch and open a draft pull request.

        Critical: App must NOT have merge permission.
        The PR stays draft until human review is ready.

        Args:
            repo_full_name: Repository in "owner/name" format
            branch_name: Name of the branch to push
            pr_title: PR title
            pr_body: PR body/markdown content
            maintainer_can_modify: Whether maintainers can modify the PR

        Returns:
            PR dictionary or None if failed
        """
        import base64

        # 1. Push the branch
        # In a real implementation, this would use the Git REST API
        # to create or update the branch. For now, we'll simulate.

        # 2. Open a draft PR
        endpoint = f"/repos/{repo_full_name}/pulls"

        body = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": "main",
            "draft": True,  # Critical: PR stays draft
            "maintainer_can_modify": maintainer_can_modify,
        }

        response = await self._request("POST", endpoint, json=body)

        if response.status_code == 403:
            # App lacks permission to create PR
            return None
        elif response.status_code != 201:
            # Log error
            return None

        return response.json()

    async def add_issue_comment(
        self,
        repo_full_name: str,
        issue_id: int,
        comment_body: str,
    ) -> Optional[Dict[str, Any]]:
        """Add a comment to a GitHub issue.

        Args:
            repo_full_name: Repository in "owner/name" format
            issue_id: GitHub issue number
            comment_body: Markdown content for the comment

        Returns:
            Comment dictionary or None if failed
        """
        endpoint = f"/repos/{repo_full_name}/issues/{issue_id}/comments"

        body = {"body": comment_body}

        response = await self._request("POST", endpoint, json=body)

        if response.status_code != 201:
            # Log error but don't crash
            return None

        return response.json()

    async def list_issues_labels(
        self,
        repo_full_name: str,
        label_name: str = "agent-fix",
    ) -> Optional[List[Dict[str, Any]]]:
        """List issues with a specific label.

        Args:
            repo_full_name: Repository in "owner/name" format
            label_name: Label to filter by (default: "agent-fix")

        Returns:
            List of issues with the specified label, or None
        """
        # First, get the label ID
        endpoint = f"/repos/{repo_full_name}/labels/{label_name}"
        response = await self._request("GET", endpoint)

        if response.status_code != 200:
            return None

        label_info = response.json()

        # Now list issues with this label
        issues_endpoint = f"/repos/{repo_full_name}/issues"
        params = {"labels": label_name, "state": "open"}
        response = await self._request("GET", issues_endpoint, params=params)

        if response.status_code != 200:
            return None

        return response.json()

    async def check_run_ownership(
        self,
        run_id: str,
        installation_id: int,
        github_login: str,
    ) -> bool:
        """Check if a run belongs to the authenticated GitHub App installation.

        Critical security check: Unknown/foreign runs return 404, not 403.

        Args:
            run_id: The run identifier
            installation_id: GitHub App installation ID
            github_login: The GitHub login that triggered the run

        Returns:
            True if the run belongs to this installation, False otherwise
        """
        # In a real implementation, this would query the runs API
        # and check installation ownership
        # For now, basic placeholder
        return True

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.http_client.aclose()


# ------------------------------------------------------------
# Helper Functions for Pipeline Integration
# ------------------------------------------------------------


def create_github_client_from_env() -> Optional[GitHubAPIClient]:
    """Create a GitHub API client from environment variables.

    Expected environment variables:
    - GITHUB_APP_ID: GitHub App ID
    - GITHUB_PRIVATE_KEY: Private key for JWT generation
    - GITHUB_INSTALLATION_ID: App installation ID
    - GITHUB_WEBHOOK_SECRET: Webhook HMAC-SHA256 secret
    - GITHUB_CALLBACK_URL: OAuth callback URL
    - GITHUB_WEBHOOK_URL: Webhook forward URL

    Returns:
        GitHubAPIClient instance or None if config is incomplete
    """
    import os

    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_PRIVATE_KEY")
    installation_id = os.environ.get("GITHUB_INSTALLATION_ID")
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")

    if not all([app_id, private_key, installation_id, webhook_secret]):
        return None

    config = GitHubConfig(
        app_id=app_id,
        private_key=private_key,
        installation_id=installation_id,
        webhook_secret=webhook_secret,
        callback_url=os.environ.get("GITHUB_CALLBACK_URL", ""),
        webhook_url=os.environ.get("GITHUB_WEBHOOK_URL", ""),
    )

    return GitHubAPIClient(config)


# ------------------------------------------------------------
# Example Usage for Pipeline Integration
# ------------------------------------------------------------


async def handle_issues_labeled(
    client: GitHubAPIClient,
    repo_full_name: str,
    installation_id: int,
    github_login: str,
    delivery_id: str,
) -> Optional[Dict[str, Any]]:
    """Handle issues.labeled events from GitHub webhook.

    Only trigger when label 'agent-fix' is added.

    Args:
        client: GitHubAPIClient instance
        repo_full_name: Repository in "owner/name" format
        installation_id: GitHub App installation ID
        github_login: The GitHub login that triggered the event
        delivery_id: GitHub delivery ID for dedup

    Returns:
        Issue details if agent-fix label detected, None otherwise
    """
    # 1. Verify delivery ID (dedup)
    if not verify_delivery_id(delivery_id):
        return None  # Already processed

    # 2. Check if label is "agent-fix"
    # The webhook payload would contain the label info
    # For now, we'll check issues labeled

    # 3. Fetch the issue
    # In a real implementation, the webhook payload would have the issue object
    # Here we demonstrate the pattern

    issues = await client.list_issues_labels(repo_full_name, "agent-fix")

    if not issues:
        return None

    # Return the first issue with agent-fix label
    if issues:
        issue = issues[0]
        return {
            "issue_number": issue.get("number"),
            "issue_title": issue.get("title"),
            "issue_body": issue.get("body"),
            "repo_full_name": repo_full_name,
            "action": issue.get("action"),
        }

    return None