"""`pipeline.runner.handle_run` must load, read the real run and end honestly."""
import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from data.run_repo import RunRepo
from main import app
from pipeline import runner
from pipeline.queue import load_handler
from pipeline.sandbox import SandboxResult
from schemas import PipelineStep, Run, RunStatus, StepStatus

DETAILED_BODY = (
    "Steps to reproduce: call calculate_discount(100, 20). "
    "Expected behaviour: returns 80. Actual behaviour: returns 81."
)


@pytest.fixture
def repo() -> RunRepo:
    return cast(RunRepo, app.state.run_repo)


def make_run(repo: RunRepo, body: str) -> Run:
    return repo.create(
        installation_id=123,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=1,
        issue_title="calculate_discount returns 1 more than the discounted price",
        issue_body=body,
        triggered_by="alice",
    )


def fake_sandbox(monkeypatch: pytest.MonkeyPatch, result: SandboxResult) -> list[str]:
    urls: list[str] = []

    async def clone_and_test(url: str, *_: Any, **__: Any) -> tuple[SandboxResult, bool]:
        urls.append(url)
        return result, result.ok

    monkeypatch.setattr(runner, "clone_and_test_async", clone_and_test)
    return urls


def test_queue_discovers_the_handler() -> None:
    assert load_handler() is runner.handle_run


def test_thin_issue_ends_as_could_not_reproduce_and_comments(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    comments: list[tuple[int, str, int, str]] = []

    class FakeClient:
        def __init__(self, installation_id: int, repository: str) -> None:
            self.where = (installation_id, repository)

        async def add_issue_comment(self, number: int, body: str) -> dict[str, Any]:
            comments.append((number, body, *self.where))
            return {}

    monkeypatch.setattr(runner, "client_for", FakeClient)
    urls = fake_sandbox(monkeypatch, SandboxResult(0, "", ""))
    run = make_run(repo, "It crashes for some users. Please fix.")

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.could_not_reproduce
    assert comments == [(1, runner.NEED_MORE_INFO, 123, "fixie-demo/seeded-repo")]
    assert urls == []  # nothing is cloned for an issue that cannot be reproduced
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [(PipelineStep.read, StepStatus.completed)]
    assert "comment posted" in (steps[0].output or "")


def test_thin_issue_still_ends_honestly_when_the_comment_cannot_be_posted(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_app(*_: Any) -> Any:
        raise RuntimeError("GitHub App credentials are not configured")

    monkeypatch.setattr(runner, "client_for", no_app)
    run = make_run(repo, "broken")

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.could_not_reproduce
    assert "comment not posted (RuntimeError)" in (repo.get_steps_by_id(run.id)[0].output or "")


def test_green_baseline_stops_at_diagnose_without_inventing_a_result(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = fake_sandbox(monkeypatch, SandboxResult(0, "7 passed in 0.04s", ""))
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    assert stored.test_output == "7 passed in 0.04s"
    assert urls == ["https://github.com/fixie-demo/seeded-repo.git"]
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.failed),
    ]
    assert steps[2].error == runner.NOT_AVAILABLE


def test_sandbox_environment_error_fails_the_run_at_reproduce(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_sandbox(monkeypatch, SandboxResult(125, "", "docker missing", environment_error=True))
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert steps[-1].status is StepStatus.failed
    assert steps[-1].error == "reproduction failed - environment issue"


# ---------------------------------------------------------------------------
# The LLM pipeline: diagnose -> fix -> verify -> draft PR.
# Every test pins `runner.get_llm` explicitly so results never depend on the
# ambient GEMINI_API_KEY environment.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_llm_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No LLM and no real Docker unless a test opts in."""
    monkeypatch.setattr(runner, "get_llm", lambda: None)

    async def baseline(*_: Any, **__: Any) -> tuple[SandboxResult, bool]:
        return SandboxResult(0, "7 passed in 0.04s", ""), True

    monkeypatch.setattr(runner, "clone_and_test_async", baseline)


BUGGY_SOURCE = (
    "def calculate_discount(price: int, discount: int) -> int:\n"
    "    discount_amount = price * discount // 100\n"
    "    return price - discount_amount + 1\n"
)
FIXED_MARKER = "# bfa-fixed"
REPRO_TEST = (
    "from discount import calculate_discount\n\n\n"
    "def test_repro() -> None:\n"
    "    assert calculate_discount(100, 10) == 90\n"
)
PATCH_JSON = (
    '{"root_cause": "off-by-one", "file_path": "discount.py", '
    '"new_code": "def calculate_discount(price: int, discount: int) -> int:\\n'
    '    discount_amount = price * discount // 100\\n'
    '    return price - discount_amount\\n' + FIXED_MARKER + '\\n", '
    '"description": "removed the stray +1"}'
)


class FakeLLM:
    def __init__(self, answers: list[str]) -> None:
        self.prompts: list[str] = []
        self._answers = list(answers)

    async def ask(self, prompt: str, *_: Any, **__: Any) -> str:
        self.prompts.append(prompt)
        return self._answers.pop(0)


class FakeFullClient:
    def __init__(self) -> None:
        self.comments: list[tuple[int, str]] = []
        self.prs: list[dict[str, Any]] = []

    async def add_issue_comment(self, number: int, body: str) -> dict[str, Any]:
        self.comments.append((number, body))
        return {}

    async def push_branch_and_open_draft_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.prs.append(kwargs)
        return {
            "pr_url": "https://github.com/fixie-demo/seeded-repo/pull/9",
            "pr_number": 9,
            "branch": kwargs.get("branch_name"),
            "commit": "abc123",
        }


def fake_llm_client(monkeypatch: pytest.MonkeyPatch) -> FakeFullClient:
    client = FakeFullClient()
    monkeypatch.setattr(runner, "client_for", lambda *_, **__: client)
    return client


@pytest.fixture
def demo_workspace(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "discount.py").write_text(BUGGY_SOURCE, encoding="utf-8")
    (tmp_path / "tests" / "test_discount.py").write_text(
        "def test_smoke() -> None:\n    assert True\n", encoding="utf-8"
    )
    return tmp_path


def fake_prepare(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    async def prepare(*_: Any, **__: Any) -> Path:
        return workspace

    monkeypatch.setattr(runner, "prepare_workspace_async", prepare)


class FakeSuite:
    """Red until the fixed source is on disk, green afterwards."""

    def __init__(self, workspace: Path, *, always_green: bool = False) -> None:
        self.workspace = workspace
        self.always_green = always_green
        self.calls: list[tuple[str, ...]] = []

    async def __call__(
        self,
        _: Path,
        __: Any,
        name: str,
        *,
        install_dependencies: bool = True,
        test_paths: tuple[str, ...] = (),
        **___: Any,
    ) -> SandboxResult:
        self.calls.append(tuple(test_paths))
        source = (self.workspace / "discount.py").read_text(encoding="utf-8")
        if self.always_green or FIXED_MARKER in source:
            return SandboxResult(0, "8 passed in 0.01s", "")
        return SandboxResult(1, "1 failed - assert 91 == 90", "")


def fake_suite(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> FakeSuite:
    suite = FakeSuite(workspace)
    monkeypatch.setattr(runner, "run_workspace_tests_async", suite)
    return suite


def wire_llm(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> FakeLLM:
    llm = FakeLLM(answers)
    monkeypatch.setattr(runner, "get_llm", lambda: llm)
    return llm


def test_llm_pipeline_diagnoses_fixes_verifies_and_opens_a_draft_pr(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, demo_workspace: Path
) -> None:
    fake_prepare(monkeypatch, demo_workspace)
    suite = fake_suite(monkeypatch, demo_workspace)
    client = fake_llm_client(monkeypatch)
    wire_llm(monkeypatch, [REPRO_TEST, PATCH_JSON])
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.completed
    assert stored.pr_url == "https://github.com/fixie-demo/seeded-repo/pull/9"
    assert stored.pr_number == 9
    assert stored.root_cause == "off-by-one"
    assert stored.test_output == "8 passed in 0.01s"
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.completed),
        (PipelineStep.fix, StepStatus.completed),
        (PipelineStep.verify, StepStatus.completed),
        (PipelineStep.pr, StepStatus.completed),
    ]
    assert len(suite.calls) == 2  # red reproduction run, then the full suite
    assert suite.calls[0] == ("tests/test_agent_repro.py",)
    assert len(client.prs) == 1
    pr = client.prs[0]
    assert pr["branch_name"].startswith("agent/issue-1-")
    assert pr["files"]["discount.py"].endswith(FIXED_MARKER + "\n")
    assert pr["files"]["tests/test_agent_repro.py"] == REPRO_TEST
    assert "Human review required" in pr["pr_body"]
    # the disposable workspace is removed once the run finishes
    assert not demo_workspace.exists()


def test_llm_pipeline_reports_could_not_reproduce_when_repro_already_passes(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, demo_workspace: Path
) -> None:
    fake_prepare(monkeypatch, demo_workspace)
    suite = fake_suite(monkeypatch, demo_workspace)
    suite.always_green = True
    client = fake_llm_client(monkeypatch)
    wire_llm(monkeypatch, [REPRO_TEST, PATCH_JSON])
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.could_not_reproduce
    assert stored.pr_url is None
    assert client.prs == []
    assert client.comments == [(1, runner._CANT_REPRODUCE_NOTE)]


def test_llm_pipeline_reverts_the_patch_and_never_opens_a_pr_when_verify_stays_red(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class AlwaysRed(FakeSuite):
        async def __call__(
            self,
            _: Path,
            __: Any,
            name: str,
            *,
            install_dependencies: bool = True,
            test_paths: tuple[str, ...] = (),
            **___: Any,
        ) -> SandboxResult:
            self.calls.append(tuple(test_paths))
            return SandboxResult(1, "1 failed - still red", "")

    (tmp_path / "discount.py").write_text(BUGGY_SOURCE, encoding="utf-8")
    fake_prepare(monkeypatch, tmp_path)
    suite = AlwaysRed(tmp_path)
    monkeypatch.setattr(runner, "run_workspace_tests_async", suite)
    # keep the workspace on disk so the reverted file can be inspected
    monkeypatch.setattr(runner, "rmtree", lambda *_, **__: None)
    fake_llm_client(monkeypatch)
    wire_llm(monkeypatch, [REPRO_TEST, PATCH_JSON])
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    assert (tmp_path / "discount.py").read_text(encoding="utf-8") == BUGGY_SOURCE
    steps = repo.get_steps_by_id(run.id)
    assert [(s.step, s.status) for s in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.completed),
        (PipelineStep.fix, StepStatus.completed),
        (PipelineStep.verify, StepStatus.failed),
    ]


def test_llm_pipeline_fails_honestly_when_the_llm_is_unreachable(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, demo_workspace: Path
) -> None:
    class BrokenLLM(FakeLLM):
        async def ask(self, prompt: str, *_: Any, **__: Any) -> str:
            self.prompts.append(prompt)
            raise RuntimeError("LLM API key is not configured (GEMINI_API_KEY)")

    fake_prepare(monkeypatch, demo_workspace)
    fake_suite(monkeypatch, demo_workspace)
    fake_llm_client(monkeypatch)
    broken = BrokenLLM([])
    monkeypatch.setattr(runner, "get_llm", lambda: broken)
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.diagnose
    assert steps[-1].status is StepStatus.failed
    assert "LLM unavailable:" in (steps[-1].error or "")


def test_llm_pipeline_fails_honestly_on_an_unparseable_patch(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, demo_workspace: Path
) -> None:
    fake_prepare(monkeypatch, demo_workspace)
    fake_suite(monkeypatch, demo_workspace)
    fake_llm_client(monkeypatch)
    wire_llm(monkeypatch, [REPRO_TEST, "this is not json at all"])
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.diagnose
    assert steps[-1].error == "LLM returned an unparseable patch"


def test_llm_pipeline_fails_honestly_when_the_repro_test_is_not_python(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch, demo_workspace: Path
) -> None:
    fake_prepare(monkeypatch, demo_workspace)
    fake_suite(monkeypatch, demo_workspace)
    fake_llm_client(monkeypatch)
    wire_llm(monkeypatch, ["sorry, I cannot write tests"])
    run = make_run(repo, DETAILED_BODY)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.diagnose
    assert steps[-1].error == "LLM could not produce a valid reproduction test"
