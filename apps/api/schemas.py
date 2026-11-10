"""Pydantic schemas and request/response types for the bug-fix agent API."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


# ============================================================================
# Run State Contract - must match TS types in packages/shared/
# ============================================================================

class RunStatus(str, Enum):
    """Current run status - must match TS RunStatus."""
    pending = "pending"
    reproducing = "reproducing"
    fixing = "fixing"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    could_not_reproduce = "could_not_reproduce"


class ConfidenceLevel(str, Enum):
    """Confidence level in the result."""
    high = "high"
    medium = "medium"
    low = "low"


class PipelineStep(str, Enum):
    """Current pipeline step - must match TS PipelineStep."""
    read = "read"
    reproduce = "reproduce"
    diagnose = "diagnose"
    fix = "fix"
    verify = "verify"
    pr = "pr"


# Run payload models

class RunCreate(BaseModel):
    """Create a new run record."""
    issue_id: int = Field(..., description="GitHub issue number")
    repo_name: str = Field(..., description="Repository name in owner/name format")
    branch: str = Field(default="agent-fix", description="Working branch name")


class RunResponse(BaseModel):
    """Response returned when creating/retrieving a run."""
    run_id: str = Field(..., description="Unique run identifier")
    status: RunStatus = Field(..., description="Current run status")
    step: PipelineStep = Field(..., description="Current pipeline step")
    confidence: Optional[ConfidenceLevel] = Field(
        default=None, 
        description="Confidence in current result"
    )
    issue_id: int = Field(..., description="GitHub issue number")
    repo_name: str = Field(..., description="Repository name")
    branch: str = Field(..., description="Working branch name")
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")


# Issue models

class IssueSummary(BaseModel):
    """Summary of a GitHub issue."""
    issue_id: int = Field(..., description="GitHub issue number")
    title: str = Field(..., description="Issue title")
    body: str = Field(..., description="Issue body/description")
    labels: List[str] = Field(
        default_factory=list, 
        description="Issue labels"
    )
    repository: str = Field(
        ..., 
        description="Repository in owner/name format"
    )


# GitHub webhook models

class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload (simplified)."""
    action: str
    issue: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Issue object from webhook"
    )
    repository: Dict[str, Any] = Field(
        ..., 
        description="Repository object from webhook"
    )
    sender: Dict[str, Any] = Field(
        ..., 
        description="Sender object from webhook"
    )
    delivery_id: str = Field(
        ..., 
        description="GitHub delivery ID for dedup"
    )


# API error model

class ApiError(BaseModel):
    """Standard API error response."""
    detail: str = Field(..., description="Human-readable error message")
    code: str = Field(
        default="api_error", 
        description="Machine-readable error code"
    )
    status_code: int = Field(
        default=400, 
        description="HTTP status code"
    )


# Authentication models

class OAuthStart(BaseModel):
    """Start OAuth flow."""
    redirect_url: str = Field(..., description="URL to redirect user to")


class SessionInfo(BaseModel):
    """Session information for authenticated requests."""
    user_id: str = Field(..., description="Authenticated user ID")
    session_id: str = Field(..., description="Session cookie ID")
    expires_at: str = Field(..., description="ISO expiration timestamp")


# Rate limiting

class RateLimitError(ApiError):
    """Rate limit exceeded error."""
    retry_after: Optional[int] = Field(
        default=None, 
        description="Seconds to wait before retrying"
    )


# Request/response wrappers

class successResponse(BaseModel):
    """Standard success response wrapper."""
    success: bool = Field(default=True)
    data: Optional[Any] = Field(default=None, description="Response data")
    message: Optional[str] = Field(
        default=None, 
        description="Optional success message"
    )


# Run event SSE model

class RunEvent(BaseModel):
    """SSE event for run status updates."""
    run_id: str = Field(..., description="Run identifier")
    status: RunStatus = Field(..., description="New status")
    step: Optional[PipelineStep] = Field(
        default=None, 
        description="New step"
    )
    confidence: Optional[ConfidenceLevel] = Field(
        default=None, 
        description="New confidence"
    )
    timestamp: str = Field(
        ..., 
        description="ISO event timestamp"
    )


# Deduplication model

class DedupKey(BaseModel):
    """Key for deduping GitHub webhook deliveries."""
    installation_id: int = Field(
        ..., 
        description="GitHub App installation ID"
    )
    delivery_id: str = Field(
        ..., 
        description="GitHub delivery ID"
    )