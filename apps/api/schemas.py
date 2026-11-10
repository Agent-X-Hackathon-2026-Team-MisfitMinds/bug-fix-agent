"""Pydantic contracts for the bug-fix agent API.

Field names and enum values mirror `packages/shared/types.ts` and the
logical schema in `docs/06-data-api.md`.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
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
