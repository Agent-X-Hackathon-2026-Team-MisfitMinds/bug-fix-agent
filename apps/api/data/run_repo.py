"""In-memory run repository (ADR-006: no database in v1).

Every read is ownership-guarded: installation_id + triggered_by must match the caller.
Foreign runs raise NotFoundError (404), never Forbidden, to prevent IDOR enumeration.
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from errors import ConflictError, NotFoundError, ValidationFailed
from schemas import Run, RunStatus, RunStep

RETRYABLE = {RunStatus.failed, RunStatus.could_not_reproduce}


@dataclass(frozen=True)
class Caller:
    installation_id: int
    github_login: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        value = int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise ValidationFailed("Invalid cursor") from exc
    if value < 0:
        raise ValidationFailed("Invalid cursor")
    return value


class RunRepo:
    def __init__(self) -> None:
        self._runs: dict[UUID, Run] = {}
        self._steps: dict[UUID, list[RunStep]] = {}

    def get_by_id(self, run_id: UUID) -> Run:
        """Worker accessor: runs are looked up by id, without an HTTP caller."""
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        return run

    def get_steps_by_id(self, run_id: UUID) -> list[RunStep]:
        """Worker accessor for a run's steps; validates that the run exists."""
        self.get_by_id(run_id)
        return list(self._steps.get(run_id, []))

    def create(self, *, installation_id: int, repository_full_name: str, issue_number: int,
               issue_title: str, issue_body: str, triggered_by: str) -> Run:
        now = _now()
        run = Run(id=uuid4(), installation_id=installation_id,
                  repository_full_name=repository_full_name, issue_number=issue_number,
                  issue_title=issue_title, issue_body=issue_body, triggered_by=triggered_by,
                  created_at=now, updated_at=now)
        self._runs[run.id] = run
        self._steps[run.id] = []
        return run

    def _owned(self, caller: Caller, run: Run | None) -> Run:
        if run is None or run.installation_id != caller.installation_id \
                or run.triggered_by != caller.github_login:
            raise NotFoundError("Run not found")
        return run

    def get(self, caller: Caller, run_id: UUID) -> Run:
        return self._owned(caller, self._runs.get(run_id))

    def get_steps(self, caller: Caller, run_id: UUID) -> list[RunStep]:
        self.get(caller, run_id)
        return list(self._steps[run_id])

    def list(self, caller: Caller, *, limit: int = 20, cursor: str | None = None,
             status: RunStatus | None = None) -> tuple[list[Run], str | None]:
        runs = [r for r in self._runs.values()
                if r.installation_id == caller.installation_id
                and r.triggered_by == caller.github_login
                and (status is None or r.status == status)]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        start = decode_cursor(cursor) if cursor else 0
        page = runs[start:start + limit]
        nxt = encode_cursor(start + limit) if start + limit < len(runs) else None
        return page, nxt

    def update_status(self, run_id: UUID, status: RunStatus, **fields: object) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        data = run.model_dump()
        data.update(fields)
        data["status"] = status
        data["updated_at"] = _now()
        if status in {RunStatus.completed, RunStatus.failed, RunStatus.could_not_reproduce}:
            data["completed_at"] = _now()
        updated = Run(**data)
        self._runs[run_id] = updated
        return updated

    def add_step(self, step: RunStep) -> None:
        self._steps.setdefault(step.run_id, []).append(step)

    def update_step(self, step: RunStep) -> RunStep:
        steps = self._steps.setdefault(step.run_id, [])
        for idx, existing in enumerate(steps):
            if existing.id == step.id:
                steps[idx] = step
                return step
        # Unknown step: append it.
        steps.append(step)
        return step

    def check_retryable(self, caller: Caller, run_id: UUID) -> Run:
        run = self.get(caller, run_id)
        if run.status not in RETRYABLE:
            raise ConflictError("This run cannot be retried in its current state")
        return run

    def reset_for_retry(self, run_id: UUID) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        data = run.model_dump()
        data.update(status=RunStatus.pending, updated_at=_now(), completed_at=None,
                    confidence=None, pr_url=None, pr_number=None)
        updated = Run(**data)
        self._runs[run_id] = updated
        self._steps[run_id] = []
        return updated

    def delete_all_for_user(self, github_login: str) -> int:
        ids = [i for i, r in self._runs.items() if r.triggered_by == github_login]
        for i in ids:
            del self._runs[i]
            self._steps.pop(i, None)
        return len(ids)
