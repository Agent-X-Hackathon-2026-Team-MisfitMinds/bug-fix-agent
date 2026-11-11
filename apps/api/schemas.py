"""Pydantic contracts for the bug-fix agent API.

Field names and enum values mirror `packages/shared/types.ts` and the
logical schema in `docs/06-data-api.md`.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    pending = "pending"
    reproducing = "reproducing"
    fixing = "fixing"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    could_not_reproduce = "could_not_reproduce"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class PipelineStep(str, Enum):
    read = "read"
    reproduce = "reproduce"
    diagnose = "diagnose"
    fix = "fix"
    verify = "verify"
    pr = "pr"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class RunStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    step: PipelineStep
    status: StepStatus = StepStatus.pending
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Run(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    installation_id: int
    repository_full_name: str
    issue_number: int
    issue_title: str
    issue_body: str
    status: RunStatus = RunStatus.pending
    confidence: ConfidenceLevel | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    test_output: str | None = None
    root_cause: str | None = None
    repo_language: str = "python"
    triggered_by: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None


class RunDetail(Run):
    steps: list[RunStep] = Field(default_factory=list)


class RunSummary(BaseModel):
    id: UUID
    repository_full_name: str
    issue_number: int
    issue_title: str
    status: RunStatus
    confidence: ConfidenceLevel | None = None
    pr_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ListRunsParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=256)
    status: RunStatus | None = None


class RunListResponse(BaseModel):
    data: list[RunSummary]
    next_cursor: str | None
    has_more: bool


class RetryResponse(BaseModel):
    status: str = "retry_queued"
    run_id: UUID


class SessionInfo(BaseModel):
    authenticated: bool
    github_login: str | None = None
    github_user_id: int | None = None


class LogoutResponse(BaseModel):
    status: str = "logged_out"


class GitHubWebhookPayload(BaseModel):
    action: str
    issue: dict[str, Any] | None = None
    repository: dict[str, Any]
    sender: dict[str, Any]
    installation: dict[str, Any] | None = None


class SSEEvent(BaseModel):
    event: str
    data: dict[str, Any]


# ------------------------------------------------------------
# LangGraph Run State - must match TS types in packages/shared/types.ts
# ------------------------------------------------------------


class RunState(BaseModel):
    """Typed graph state shared across all pipeline nodes.

    Kept in sync with packages/shared/types.ts:
    - status: RunStatus enum
    - confidence: ConfidenceLevel enum
    - step: PipelineStep enum
    """

    # Identification
    run_id: str = Field(
        default_factory=lambda: f"run-{__import__('hashlib').sha256(
            __import__('uuid').uuid4().encode
        ).hexdigest()[:12]}"
    )
    issue_id: int = Field(..., description="GitHub issue number")
    repo_name: str = Field(..., description="Repository in owner/name format")
    branch: str = Field(
        default="agent-fix",
        description="Working branch name",
    )

    # Status & Step Tracking
    status: RunStatus = Field(
        default=RunStatus.pending,
        description="Current run status",
    )
    step: PipelineStep = Field(
        default=PipelineStep.read,
        description="Current pipeline step",
    )
    confidence: Optional[ConfidenceLevel] = Field(
        default=None,
        description="Confidence in current result: high/medium/low",
    )

    # Issue Details
    issue_title: Optional[str] = Field(
        default=None,
        description="Issue title from GitHub",
    )
    issue_body: Optional[str] = Field(
        default=None,
        description="Issue body/description",
    )
    reproduction_steps: Optional[str] = Field(
        default=None,
        description="Extracted reproduction steps from issue",
    )

    # Before Fix Evidence
    before_test_output: Optional[str] = Field(
        default=None,
        description="Test output before the fix was applied",
    )
    before_exit_code: Optional[int] = Field(
        default=None,
        description="Exit code before the fix",
    )

    # After Fix Evidence
    after_test_output: Optional[str] = Field(
        default=None,
        description="Test output after the fix was applied",
    )
    after_exit_code: Optional[int] = Field(
        default=None,
        description="Exit code after the fix",
    )

    # Root Cause & Patch
    root_cause: Optional[str] = Field(
        default=None,
        description="Plain-English root cause diagnosis",
    )
    patch: Optional[dict[str, str]] = Field(
        default=None,
        description="Applied patch: {file_path, old_code, new_code, description}",
    )
    likely_file: Optional[str] = Field(
        default=None,
        description="Likely file containing the bug",
    )
    likely_line: Optional[int] = Field(
        default=None,
        description="Likely line number containing the bug",
    )

    # Evidence & Errors
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence for root cause",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages encountered during run",
    )

    # PR & Branch Information
    pr_url: Optional[str] = Field(
        default=None,
        description="Draft PR URL if opened",
    )
    branch_name: Optional[str] = Field(
        default=None,
        description="Git branch name where patch was applied",
    )

    # Metadata
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts for this run",
    )
    created_at: str = Field(
        default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat()
        + "Z",
        description="ISO timestamp when run was created",
    )
    updated_at: str = Field(
        default_factory=lambda: __import__('datetime').utcnow().isoformat() + "Z",
        description="ISO timestamp when run was last updated",
    )
