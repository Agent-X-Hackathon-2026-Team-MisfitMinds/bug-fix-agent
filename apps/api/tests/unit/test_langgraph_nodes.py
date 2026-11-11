"""Each pipeline node must do real work and fail honestly on bad input."""
import asyncio
from pathlib import Path
from typing import Any


from pipeline.langgraph import (
    diagnose_node,
    fix_node,
    pr_node,
    read_node,
    reproduce_node,
    verify_node,
)
from pipeline.pytest_runner import PytestResult
from schemas import ConfidenceLevel, PipelineStep, RunState, RunStatus

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


class FakeLLM:
    def __init__(
        self,
        *,
        code: str = REPRO_CODE,
        code_error: Exception | None = None,
        responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.code_error = code_error
        self.responses = list(responses or [])

    async def ask_code(self, prompt: str, issue_title: str, issue_body: str) -> str:
        if self.code_error is not None:
            raise self.code_error
        assert "UNTRUSTED DATA" in prompt
        return self.code

    async def ask_json(
        self, prompt: str, issue_title: str, issue_body: str
    ) -> dict[str, Any]:
        assert prompt
        if not self.responses:
            raise AssertionError("unexpected ask_json call")
        return self.responses.pop(0)


class FakeRunner:
    def __init__(self, results: list[PytestResult]) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    async def run(self, test_file: str, timeout: int | None = None) -> PytestResult:
        self.calls.append(f"run:{test_file}")
        return self.results.pop(0)

    async def run_suite(self, timeout: int | None = None) -> PytestResult:
        self.calls.append("suite")
        return self.results.pop(0)


class FakeGitHub:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.base_branch: str | None = None
        self.branch_name: str | None = None

    async def get_repo(self) -> dict[str, Any]:
        return {"default_branch": "trunk"}

    async def push_branch_and_open_draft_pr(self, **kwargs: Any) -> dict[str, Any]:
        self.files = dict(kwargs["files"])
        self.base_branch = str(kwargs["base_branch"])
        self.branch_name = str(kwargs["branch_name"])
        return {
            "pr_url": "https://github.com/demo/repo/pull/12",
            "pr_number": 12,
            "branch": kwargs["branch_name"],
        }


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "repo"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir()
    (workspace / "src" / "app.py").write_text(BUGGY_SOURCE, encoding="utf-8")
    (workspace / "tests" / "test_app.py").write_text(
        "def test_existing():\n    assert True\n", encoding="utf-8"
    )
    return workspace


def make_state() -> RunState:
    return RunState(
        issue_id=1,
        repo_name="demo/repo",
        issue_title="calculate_discount returns one more than expected",
        issue_body=(
            "Steps to reproduce: call calculate_discount(100, 20). "
            "Expected behaviour: 80. Actual behaviour: 81."
        ),
        status=RunStatus.reproducing,
    )


def test_read_node_accepts_a_reproducible_issue() -> None:
    state = asyncio.run(read_node(make_state()))

    assert state.status is RunStatus.reproducing
    assert state.step is PipelineStep.reproduce
    assert state.reproduction_steps


def test_read_node_refuses_a_thin_issue_with_a_comment() -> None:
    state = make_state()
    state.issue_body = "It crashes for some users. Please fix."
    state = asyncio.run(read_node(state))

    assert state.status is RunStatus.could_not_reproduce
    assert "reproduction steps" in (state.comment or "")


def test_reproduce_requires_a_green_baseline(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    runner = FakeRunner([PytestResult(False, "1 failed", 1)])
    state = asyncio.run(reproduce_node(make_state(), workspace, runner, FakeLLM()))

    assert state.status is RunStatus.failed
    assert "Baseline suite is not green" in state.errors[-1]
    assert not (workspace / "tests" / "test_agent_repro_1.py").exists()


def test_reproduce_writes_the_generated_test_and_records_a_red_run(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    runner = FakeRunner(
        [
            PytestResult(True, "7 passed", 0),
            PytestResult(False, "1 failed: expected 80, got 81", 1),
        ]
    )
    state = asyncio.run(reproduce_node(make_state(), workspace, runner, FakeLLM()))

    assert state.status is RunStatus.reproducing
    assert state.step is PipelineStep.diagnose
    assert state.reproduction_test_path == "tests/test_agent_repro_1.py"
    assert state.reproduction_test_code == REPRO_CODE
    assert state.before_output == "1 failed: expected 80, got 81"
    assert (workspace / "tests" / "test_agent_repro_1.py").read_text(encoding="utf-8") == REPRO_CODE
    assert runner.calls == ["suite", "run:tests/test_agent_repro_1.py"]


def test_reproduce_reports_could_not_reproduce_when_the_test_passes(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    runner = FakeRunner([PytestResult(True, "7 passed", 0), PytestResult(True, "1 passed", 0)])
    state = asyncio.run(reproduce_node(make_state(), workspace, runner, FakeLLM()))

    assert state.status is RunStatus.could_not_reproduce
    assert "could not be reproduced" in state.errors[-1]


def test_reproduce_fails_when_the_llm_cannot_generate_a_test(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    runner = FakeRunner([PytestResult(True, "7 passed", 0)])
    llm = FakeLLM(code_error=RuntimeError("API key is not configured"))
    state = asyncio.run(reproduce_node(make_state(), workspace, runner, llm))

    assert state.status is RunStatus.failed
    assert "API key is not configured" in state.errors[-1]


def test_diagnose_validates_the_file_and_stores_evidence(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.reproduction_test_code = REPRO_CODE
    state.before_output = "1 failed"
    state = asyncio.run(
        diagnose_node(state, FakeLLM(responses=[DIAGNOSIS]), workspace)
    )

    assert state.status is RunStatus.fixing
    assert state.step is PipelineStep.fix
    assert state.likely_file == "src/app.py"
    assert state.likely_line == 3
    assert state.root_cause == DIAGNOSIS["root_cause"]


def test_diagnose_rejects_a_file_outside_the_repository(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.reproduction_test_code = REPRO_CODE
    state.before_output = "1 failed"
    bad = dict(DIAGNOSIS, likely_file="../../etc/passwd")
    state = asyncio.run(diagnose_node(state, FakeLLM(responses=[bad]), workspace))

    assert state.status is RunStatus.failed
    assert "not in the repository" in state.errors[-1]


def test_fix_applies_one_exact_patch_and_keeps_the_full_file(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.likely_file = "src/app.py"
    state.root_cause = DIAGNOSIS["root_cause"]
    state = asyncio.run(fix_node(state, FakeLLM(responses=[PATCH]), workspace))

    assert state.status is RunStatus.verifying
    assert state.step is PipelineStep.verify
    assert state.patch == PATCH
    assert state.patched_file_content == FIXED_SOURCE
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == FIXED_SOURCE


def test_fix_rejects_a_patch_that_does_not_match(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.likely_file = "src/app.py"
    bad = dict(PATCH, old_code="return price + 1\n")
    state = asyncio.run(fix_node(state, FakeLLM(responses=[bad]), workspace))

    # Unusable patch: nothing is written and the node asks for another attempt.
    assert state.status is RunStatus.fixing
    assert state.patch is None
    assert "not found" in state.errors[-1]
    assert "not found" in (state.verification_feedback or "")
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == BUGGY_SOURCE


def test_fix_retry_restores_pristine_code_before_applying_the_new_patch(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.likely_file = "src/app.py"
    state.root_cause = DIAGNOSIS["root_cause"]
    llm = FakeLLM(responses=[PATCH, PATCH])
    state = asyncio.run(fix_node(state, llm, workspace))
    state.verification_feedback = "still failing"
    state = asyncio.run(fix_node(state, llm, workspace))

    assert state.patched_file_content == FIXED_SOURCE
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == FIXED_SOURCE


def test_verify_requires_red_to_green_and_a_green_full_suite(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.reproduction_test_path = "tests/test_agent_repro_1.py"
    state.reproduction_test_code = REPRO_CODE
    runner = FakeRunner([PytestResult(True, "1 passed", 0), PytestResult(True, "8 passed", 0)])
    state = asyncio.run(verify_node(state, workspace, runner))

    assert state.status is RunStatus.verifying
    assert state.step is PipelineStep.pr
    assert state.after_test_output == "8 passed"
    assert state.verification_feedback is None
    assert runner.calls == ["run:tests/test_agent_repro_1.py", "suite"]


def test_verify_returns_to_fix_when_the_reproduction_test_is_still_red(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.reproduction_test_path = "tests/test_agent_repro_1.py"
    state.reproduction_test_code = REPRO_CODE
    runner = FakeRunner([PytestResult(False, "expected 80, got 81", 1)])
    state = asyncio.run(verify_node(state, workspace, runner))

    assert state.status is RunStatus.fixing
    assert state.step is PipelineStep.fix
    assert state.verification_feedback == "expected 80, got 81"


def test_verify_returns_to_fix_when_the_full_suite_is_red(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = make_state()
    state.reproduction_test_path = "tests/test_agent_repro_1.py"
    state.reproduction_test_code = REPRO_CODE
    runner = FakeRunner([PytestResult(True, "1 passed", 0), PytestResult(False, "2 failed", 1)])
    state = asyncio.run(verify_node(state, workspace, runner))

    assert state.status is RunStatus.fixing
    assert "Full test suite is red" in state.errors[-1]


def test_pr_uploads_the_full_source_file_and_the_reproduction_test() -> None:
    state = make_state()
    state.status = RunStatus.verifying
    state.root_cause = DIAGNOSIS["root_cause"]
    state.patch = {key: str(value) for key, value in PATCH.items()}
    state.patched_file_content = FIXED_SOURCE
    state.reproduction_test_path = "tests/test_agent_repro_1.py"
    state.reproduction_test_code = REPRO_CODE
    state.confidence = ConfidenceLevel.high
    state.confidence_reasons = ["baseline green", "red then green"]
    fake = FakeGitHub()

    state = asyncio.run(pr_node(state, fake))

    assert state.status is RunStatus.completed
    assert state.pr_url == "https://github.com/demo/repo/pull/12"
    assert state.pr_number == 12
    assert fake.base_branch == "trunk"
    assert fake.files["src/app.py"] == FIXED_SOURCE
    assert fake.files["tests/test_agent_repro_1.py"] == REPRO_CODE
    assert fake.branch_name is not None and fake.branch_name.startswith("agent/fix-1-")


def test_pr_refuses_to_run_before_verification_passes() -> None:
    state = make_state()
    state.status = RunStatus.fixing
    fake = FakeGitHub()

    state = asyncio.run(pr_node(state, fake))

    assert state.status is RunStatus.failed
    assert fake.files == {}
