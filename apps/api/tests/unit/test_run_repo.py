from uuid import uuid4

import pytest

from data.run_repo import Caller, RunRepo, decode_cursor
from errors import ConflictError, NotFoundError, ValidationFailed
from schemas import RunStatus


def make(repo: RunRepo, login: str = "alice", inst: int = 1, n: int = 1):
    return repo.create(installation_id=inst, repository_full_name="o/r", issue_number=n,
                       issue_title="t", issue_body="b", triggered_by=login)


def test_owner_can_get() -> None:
    repo = RunRepo()
    run = make(repo)
    assert repo.get(Caller(1, "alice"), run.id).id == run.id


def test_foreign_user_gets_404() -> None:
    repo = RunRepo()
    run = make(repo)
    with pytest.raises(NotFoundError):
        repo.get(Caller(1, "mallory"), run.id)


def test_foreign_installation_gets_404() -> None:
    repo = RunRepo()
    run = make(repo)
    with pytest.raises(NotFoundError):
        repo.get(Caller(2, "alice"), run.id)


def test_unknown_id_404() -> None:
    with pytest.raises(NotFoundError):
        RunRepo().get(Caller(1, "alice"), uuid4())


def test_list_only_own_and_paginates() -> None:
    repo = RunRepo()
    for i in range(5):
        make(repo, n=i)
    make(repo, login="bob")
    caller = Caller(1, "alice")
    page1, nxt = repo.list(caller, limit=3)
    assert len(page1) == 3 and nxt is not None
    page2, nxt2 = repo.list(caller, limit=3, cursor=nxt)
    assert len(page2) == 2 and nxt2 is None


def test_status_filter() -> None:
    repo = RunRepo()
    r = make(repo)
    repo.update_status(r.id, RunStatus.failed)
    make(repo, n=2)
    runs, _ = repo.list(Caller(1, "alice"), status=RunStatus.failed)
    assert len(runs) == 1


def test_retry_only_failed_states() -> None:
    repo = RunRepo()
    r = make(repo)
    caller = Caller(1, "alice")
    with pytest.raises(ConflictError):
        repo.check_retryable(caller, r.id)
    repo.update_status(r.id, RunStatus.could_not_reproduce)
    assert repo.check_retryable(caller, r.id).id == r.id


def test_bad_cursor() -> None:
    with pytest.raises(ValidationFailed):
        decode_cursor("!!!")
