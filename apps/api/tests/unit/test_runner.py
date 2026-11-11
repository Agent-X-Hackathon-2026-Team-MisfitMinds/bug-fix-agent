"""`pipeline.runner.handle_run` must execute the real pipeline end to end."""
import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from data.run_repo import RunRepo
from main import app
from pipeline import runner
from pipeline.pytest_runner import PytestResult
from pipeline.queue import load_handler
from schemas import ConfidenceLevel, PipelineStep, Run, RunStatus, StepStatus

DETAILED_BODY = (
    "Steps to reproduce: call calculate_discount(100, 20). "
    "Expected behaviour: returns 80. Actual behaviour: returns 81."
)
REPRO_CODE = (
    "import os\n"
    "import sys\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))\n"
    "from app import calculate_discount\n\n"
    "def test_discount_is_exact():\n"
    "    assert calculate_discount(100, 20) == 80\n"
)
BUGGY_SOURCE = (
    "def calculate_discount(price, discount_percent):\n"
    "    discount = price * (discount_percent / 100)\n"
    "    return price - discount + 1\n"
)
FIXED_SOURCE = BUGGY_SOURCE.replace(
    "    return price - discount + 1\n",
    "    return price - discount\n",
)
DIAGNOSIS: dict[str, Any] = {
    "root_cause": "The discount function adds one to every result.",
    "evidence": ["calculate_discount(100, 20) returns 81 instead of 80"],
    "likely_file": "src/app.py",
    "likely_line": 3,
}
PATCH: dict[str, Any] = {
    "file_path": "src/app.py",
    "old_code": "    return price - discount + 1\n",
    "new_code": "    return price - discount\n",
    "description": "Drop the off-by-one addition.",
}
PR_URL = "https://github.com/fixie-demo/seeded-repo/pull/12"


class FakeLLM:
    def __init__(
        self,
        *,
        code: str = REPRO_CODE,
        code_error: Exception | None = None,
        json_responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.code_error = code_error
        self.json_responses = list(json_responses or [])
        self.code_calls = 0
        self.json_calls = 0

    async def ask_code(self, prompt: str, issue_title: str, issue_body: str) -> str:
        del prompt, issue_title, issue_body
        self.code_calls += 1
        if self.code_error is not None:
            raise self.code_error
        return self.code

    async def ask_json(
        self, prompt: str, issue_title: str, issue_body: str
    ) -> dict[str, Any]:
        del prompt, issue_title, issue_body
        self.json_calls += 1
        if not self.json_responses:
            raise AssertionError("unexpected ask_json call")
        return self.json_responses.pop(0)


class FakeRunner:
    def __init__(self, results: list[PytestResult]) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    async def run(self, test_file: str, timeout: int | None = None) -> PytestResult:
        del timeout
        self.calls.append(f"run:{test_file}")
        return self.results.pop(0)

    async def run_suite(self, timeout: int | None = None) -> PytestResult:
        del timeout
        self.calls.append("suite")
        return self.results.pop(0)


class FakeClient:
    def __init__(self) -> None:
        self.comments: list[tuple[int, str]] = []
        self.files: dict[str, str] = {}
        self.base_branch: str | None = None
        self.pr_error: Exception | None = None

    async def add_issue_comment(
        self, number: int, body: str, repository: str | None = None
    ) -> dict[str, Any]:
        del repository
        self.comments.append((number, body))
        return {}

    async def get_repo(self, repository: str | None = None) -> dict[str, Any]:
        del repository
        return {"default_branch": "main"}

    async def push_branch_and_open_draft_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.files = dict(kwargs["files"])
        self.base_branch = str(kwargs["base_branch"])
        if self.pr_error is not None:
            raise self.pr_error
        return {
            "pr_url": PR_URL,
            "pr_number": 12,
            "branch": kwargs["branch_name"],
        }


@pytest.fixture
def repo() -> RunRepo:
    return cast(RunRepo, app.state.run_repo)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(BUGGY_SOURCE, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_existing():\n    assert True\n", encoding="utf-8"
    )
    return tmp_path


def make_run(repo: RunRepo, body: str = DETAILED_BODY) -> Run:
    return repo.create(
        installation_id=123,
        repository_full_name="fixie-demo/seeded-repo",
        issue_number=1,
        issue_title="calculate_discount returns 1 more than the discounted price",
        issue_body=body,
        triggered_by="alice",
    )


def passed(output: str = "7 passed") -> PytestResult:
    return PytestResult(True, output, 0)


def failed(output: str = "1 failed") -> PytestResult:
    return PytestResult(False, output, 1)


class Installed:
    def __init__(
        self,
        llm: FakeLLM,
        test_runner: FakeRunner,
        client: FakeClient,
        clones: list[str],
    ) -> None:
        self.llm = llm
        self.test_runner = test_runner
        self.client = client
        self.clones = clones


def install(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
    *,
    results: list[PytestResult],
    json_responses: list[dict[str, Any]] | None = None,
    code: str = REPRO_CODE,
    code_error: Exception | None = None,
    pr_error: Exception | None = None,
) -> Installed:
    llm = FakeLLM(code=code, code_error=code_error, json_responses=json_responses)
    test_runner = FakeRunner(results)
    client = FakeClient()
    client.pr_error = pr_error
    clones: list[str] = []

    def prepare(url: str, **_: Any) -> Path:
        clones.append(url)
        return workspace

    monkeypatch.setattr(runner, "prepare_workspace", prepare)
    monkeypatch.setattr(runner, "LLMWrapper", lambda **_: llm)
    monkeypatch.setattr(runner, "PytestRunner", lambda **_: test_runner)
    monkeypatch.setattr(runner, "client_for", lambda *_: client)
    return Installed(llm, test_runner, client, clones)


def test_queue_discovers_the_handler() -> None:
    assert load_handler() is runner.handle_run


def test_full_pipeline_opens_a_draft_pr_with_source_and_test(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed(), passed("1 passed"), passed("8 passed")],
        json_responses=[DIAGNOSIS, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.completed
    assert stored.confidence is ConfidenceLevel.high
    assert stored.pr_url == PR_URL
    assert stored.pr_number == 12
    assert stored.root_cause == DIAGNOSIS["root_cause"]
    assert stored.test_output == "8 passed"

    steps = repo.get_steps_by_id(run.id)
    assert [(step.step, step.status) for step in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.completed),
        (PipelineStep.fix, StepStatus.completed),
        (PipelineStep.verify, StepStatus.completed),
        (PipelineStep.pr, StepStatus.completed),
    ]
    assert all(step.started_at is not None for step in steps)
    assert all(step.completed_at is not None for step in steps)

    assert installed.clones == ["https://github.com/fixie-demo/seeded-repo.git"]
    assert installed.test_runner.calls == [
        "suite",
        "run:tests/test_agent_repro_1.py",
        "run:tests/test_agent_repro_1.py",
        "suite",
    ]
    assert installed.client.files["src/app.py"] == FIXED_SOURCE
    assert installed.client.files["tests/test_agent_repro_1.py"] == REPRO_CODE
    assert installed.client.base_branch == "main"
    assert installed.llm.code_calls == 1
    assert installed.llm.json_calls == 2


def test_thin_issue_ends_as_could_not_reproduce_and_comments(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient()
    monkeypatch.setattr(runner, "client_for", lambda *_: client)
    clones: list[str] = []

    def prepare(url: str, **_: Any) -> Path:
        clones.append(url)
        raise AssertionError("thin issues must not be cloned")

    monkeypatch.setattr(runner, "prepare_workspace", prepare)
    run = make_run(repo, "It crashes for some users. Please fix.")

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.could_not_reproduce
    assert client.comments == [(1, runner.NEED_MORE_INFO)]
    assert clones == []
    steps = repo.get_steps_by_id(run.id)
    assert [(step.step, step.status) for step in steps] == [
        (PipelineStep.read, StepStatus.completed)
    ]
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
    assert "comment not posted (RuntimeError)" in (
        repo.get_steps_by_id(run.id)[0].output or ""
    )


def test_red_baseline_fails_without_diagnosing_or_patching(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[failed("3 failed before the agent touched anything")],
        json_responses=[DIAGNOSIS, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    assert stored.test_output == "3 failed before the agent touched anything"
    assert installed.llm.code_calls == 0
    steps = repo.get_steps_by_id(run.id)
    assert [(step.step, step.status) for step in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.failed),
    ]
    assert "Baseline suite is not green" in (steps[-1].error or "")


def test_reproduction_test_that_passes_is_could_not_reproduce(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(
        monkeypatch,
        workspace,
        results=[passed(), passed("1 passed")],
        json_responses=[DIAGNOSIS, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.could_not_reproduce
    assert stored.pr_url is None
    steps = repo.get_steps_by_id(run.id)
    assert [(step.step, step.status) for step in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
    ]
    assert "could not be reproduced" in (steps[-1].output or "")


def test_sandbox_environment_error_fails_the_run_at_reproduce(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(
        monkeypatch,
        workspace,
        results=[PytestResult(False, "docker missing", 125, environment_error=True)],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert steps[-1].status is StepStatus.failed
    assert steps[-1].error == "docker missing"


def test_llm_failure_fails_the_run_without_inventing_a_test(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[passed()],
        code_error=RuntimeError("LLM API key is not configured (GEMINI_API_KEY)"),
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert steps[-1].status is StepStatus.failed
    assert "API key is not configured" in (steps[-1].error or "")
    assert installed.llm.json_calls == 0
    assert not (workspace / "tests" / "test_agent_repro_1.py").exists()


def test_patch_that_never_applies_is_retried_then_fails_without_verification(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_patch = dict(PATCH, old_code="return price + 1\n")
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed()],
        json_responses=[DIAGNOSIS, bad_patch, bad_patch, bad_patch],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    assert installed.llm.json_calls == 1 + runner.MAX_PATCH_ATTEMPTS
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.fix
    assert steps[-1].status is StepStatus.failed
    assert "not found" in (steps[-1].error or "")
    assert all(step.step is not PipelineStep.verify for step in steps)
    assert installed.client.files == {}


def test_unusable_patch_is_retried_and_the_second_patch_completes_the_run(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_patch = dict(PATCH, old_code="return price + 1\n")
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed(), passed("1 passed"), passed("8 passed")],
        json_responses=[DIAGNOSIS, bad_patch, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.completed
    assert stored.confidence is ConfidenceLevel.medium
    assert installed.client.files["src/app.py"] == FIXED_SOURCE


def test_broken_generated_test_is_not_treated_as_a_reproduction(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collection_error = PytestResult(False, "ERROR collecting tests/test_agent_repro_1.py", 2)
    installed = install(monkeypatch, workspace, results=[passed(), collection_error])
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert "could not run (pytest exit 2)" in (steps[-1].error or "")
    assert installed.llm.json_calls == 0


@pytest.mark.parametrize("target", ["tests/test_app.py", ".github/workflows/ci.yml"])
def test_diagnosis_pointing_at_a_test_or_ci_file_is_refused(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    # The runner removes the workspace after every run, so one target per test.
    (workspace / ".github" / "workflows").mkdir(parents=True)
    (workspace / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed()],
        json_responses=[dict(DIAGNOSIS, likely_file=target)],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.diagnose
    assert "not a source file the agent may patch" in (steps[-1].error or "")
    assert installed.client.files == {}


def test_opened_pr_is_announced_on_the_issue(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed(), passed("1 passed"), passed("8 passed")],
        json_responses=[DIAGNOSIS, PATCH],
    )

    asyncio.run(runner.handle_run(make_run(repo).id))

    assert len(installed.client.comments) == 1
    assert PR_URL in installed.client.comments[0][1]


def test_unreproducible_issue_gets_an_honest_comment(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(monkeypatch, workspace, results=[passed(), passed()])

    asyncio.run(runner.handle_run(make_run(repo).id))

    assert installed.client.comments == [(1, runner.COULD_NOT_REPRODUCE)]


def test_verification_failure_is_retried_then_completed_with_medium_confidence(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[
            passed(),
            failed("expected 80, got 81"),
            failed("expected 80, got 81"),
            passed("1 passed"),
            passed("8 passed"),
        ],
        json_responses=[DIAGNOSIS, PATCH, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.completed
    assert stored.confidence is ConfidenceLevel.medium
    assert stored.pr_url == PR_URL
    assert installed.llm.json_calls == 3
    assert installed.client.files["src/app.py"] == FIXED_SOURCE
    steps = repo.get_steps_by_id(run.id)
    assert [(step.step, step.status) for step in steps] == [
        (PipelineStep.read, StepStatus.completed),
        (PipelineStep.reproduce, StepStatus.completed),
        (PipelineStep.diagnose, StepStatus.completed),
        (PipelineStep.fix, StepStatus.completed),
        (PipelineStep.verify, StepStatus.completed),
        (PipelineStep.pr, StepStatus.completed),
    ]


def test_verification_is_bounded_and_never_opens_a_pr(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[
            passed(),
            failed("expected 80, got 81"),
            failed("expected 80, got 81"),
            failed("expected 80, got 81"),
            failed("expected 80, got 81"),
        ],
        json_responses=[DIAGNOSIS, PATCH, PATCH, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    assert installed.llm.json_calls == 4
    assert installed.client.files == {}
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.verify
    assert steps[-1].status is StepStatus.failed
    assert steps[-2].step is PipelineStep.fix
    assert steps[-2].status is StepStatus.failed


def test_red_full_suite_after_the_patch_is_retried_and_then_failed(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[
            passed(),
            failed("expected 80, got 81"),
            passed("1 passed"),
            failed("2 failed in the existing suite"),
            passed("1 passed"),
            failed("2 failed in the existing suite"),
            passed("1 passed"),
            failed("2 failed in the existing suite"),
        ],
        json_responses=[DIAGNOSIS, PATCH, PATCH, PATCH],
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.test_output == "2 failed in the existing suite"
    assert installed.llm.json_calls == 4
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.verify
    assert "Full test suite is red" in (steps[-1].error or "")


def test_github_failure_at_pr_marks_the_run_failed(
    repo: RunRepo, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = install(
        monkeypatch,
        workspace,
        results=[passed(), failed(), passed("1 passed"), passed("8 passed")],
        json_responses=[DIAGNOSIS, PATCH],
        pr_error=RuntimeError("GitHub is unavailable"),
    )
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    stored = repo.get_by_id(run.id)
    assert stored.status is RunStatus.failed
    assert stored.pr_url is None
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.pr
    assert steps[-1].status is StepStatus.failed
    assert "GitHub is unavailable" in (steps[-1].error or "")
    assert installed.client.files["src/app.py"] == FIXED_SOURCE


def test_clone_failure_fails_at_reproduce(
    repo: RunRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_clone(url: str, **_: Any) -> Path:
        raise RuntimeError("clone refused")

    monkeypatch.setattr(runner, "prepare_workspace", broken_clone)
    monkeypatch.setattr(runner, "LLMWrapper", lambda: FakeLLM())
    run = make_run(repo)

    asyncio.run(runner.handle_run(run.id))

    assert repo.get_by_id(run.id).status is RunStatus.failed
    steps = repo.get_steps_by_id(run.id)
    assert steps[-1].step is PipelineStep.reproduce
    assert steps[-1].status is StepStatus.failed
    assert "workspace clone failed" in (steps[-1].error or "")
