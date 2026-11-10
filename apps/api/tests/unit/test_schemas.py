import pytest
from pydantic import ValidationError

from schemas import ListRunsParams, RunStatus


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
