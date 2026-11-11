import pytest
from pydantic import ValidationError

from schemas import ListRunsParams, RunState, RunStatus


def test_defaults() -> None:
    p = ListRunsParams()
    assert p.limit == 20 and p.cursor is None and p.status is None


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_limit_out_of_range(limit: int) -> None:
    with pytest.raises(ValidationError):
        ListRunsParams(limit=limit)


def test_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ListRunsParams(status="bogus")  # type: ignore[arg-type]


def test_status_values() -> None:
    assert {s.value for s in RunStatus} == {
        "pending", "reproducing", "fixing", "verifying",
        "completed", "failed", "could_not_reproduce"}


def test_run_state_has_working_id_and_timestamp_defaults() -> None:
    state = RunState(issue_id=1, repo_name="octo/demo")

    assert state.run_id.startswith("run-")
    assert len(state.run_id) == 16
    assert state.created_at.endswith("Z")
    assert state.updated_at.endswith("Z")
    assert state.status == RunStatus.pending
