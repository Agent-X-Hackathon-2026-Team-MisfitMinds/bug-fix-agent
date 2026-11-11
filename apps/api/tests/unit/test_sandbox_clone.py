import base64
import subprocess
from pathlib import Path
from typing import Any

import pytest

from pipeline.sandbox import (
    PreparationError,
    SandboxConfig,
    clone_and_test,
    clone_repo,
    render_run_dockerfile,
    validate_ref,
    validate_repo_url,
)

REPO_URL = "https://github.com/octocat/Hello-World"
TOKEN = "ghs_do_not_leak_me"


class Recorder:
    """Fake subprocess runner that records argv/env and replays return codes."""

    def __init__(self, outcomes: list[int | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return subprocess.CompletedProcess(cmd, outcome, stdout="", stderr="")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/octocat/Hello-World",
        "https://github.com/octocat/Hello-World.git",
        "https://www.github.com/octocat/Hello-World",
    ],
)
def test_validate_repo_url_accepts_github_https(url: str) -> None:
    assert validate_repo_url(url) in {"github.com", "www.github.com"}


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/octocat/Hello-World",
        "git@github.com:octocat/Hello-World.git",
        "ssh://git@github.com/octocat/Hello-World.git",
        "https://gitlab.com/octocat/Hello-World",
        "https://user:pass@github.com/octocat/Hello-World",
        "https://github.com/octocat/Hello-World/tree/main",
        "https://github.com/octocat/Hello-World?ref=main",
        "file:///etc/passwd",
    ],
)
def test_validate_repo_url_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_repo_url(url)


@pytest.mark.parametrize("ref", ["-c", "--upload-pack=evil", "main..evil", "a//b", "refs/../x", ""])
def test_validate_ref_rejects_flag_like_and_malformed_refs(ref: str) -> None:
    with pytest.raises(ValueError):
        validate_ref(ref)


def test_validate_ref_accepts_branch_and_tag_names() -> None:
    validate_ref("main")
    validate_ref("release/1.2.3")
    validate_ref("v1.0.0-rc.1")


def test_clone_passes_token_through_env_not_argv(tmp_path: Path) -> None:
    runner = Recorder([0])
    clone_repo(REPO_URL, tmp_path / "repo", token=TOKEN, runner=runner)

    cmd = runner.calls[0]
    assert cmd[:5] == ["git", "clone", "--depth", "1", "--single-branch"]
    assert "--branch" in cmd and "main" in cmd
    assert cmd[-2:] == [REPO_URL, str(tmp_path / "repo")]
    assert TOKEN not in " ".join(cmd)

    env = runner.kwargs[0]["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    header = env["GIT_CONFIG_VALUE_0"].removeprefix("AUTHORIZATION: basic ")
    assert base64.b64decode(header).decode() == f"x-access-token:{TOKEN}"


def test_clone_env_keeps_windows_system_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    runner = Recorder([0])
    clone_repo(REPO_URL, tmp_path / "repo", runner=runner)
    assert runner.kwargs[0]["env"]["SYSTEMROOT"] == r"C:\Windows"


def test_clone_without_token_sends_no_authorization(tmp_path: Path) -> None:
    runner = Recorder([0])
    clone_repo(REPO_URL, tmp_path / "repo", runner=runner)
    assert "GIT_CONFIG_KEY_0" not in runner.kwargs[0]["env"]


def test_clone_runs_no_git_command_for_a_bad_url(tmp_path: Path) -> None:
    runner = Recorder([0])
    with pytest.raises(ValueError):
        clone_repo("https://evil.example/octocat/Hello-World", tmp_path / "repo", runner=runner)
    assert runner.calls == []


def test_clone_failure_is_a_preparation_error_and_redacts_token(tmp_path: Path) -> None:
    class Failing(Recorder):
        def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            self.calls.append(cmd)
            self.kwargs.append(kwargs)
            return subprocess.CompletedProcess(
                cmd, 128, stdout="", stderr=f"fatal: auth {TOKEN} rejected"
            )

    with pytest.raises(PreparationError) as excinfo:
        clone_repo(REPO_URL, tmp_path / "repo", token=TOKEN, runner=Failing([]))
    assert excinfo.value.stage == "clone"
    assert not excinfo.value.timed_out
    assert TOKEN not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_clone_timeout_is_flagged(tmp_path: Path) -> None:
    runner = Recorder([subprocess.TimeoutExpired(["git", "clone"], 120)])
    with pytest.raises(PreparationError) as excinfo:
        clone_repo(REPO_URL, tmp_path / "repo", runner=runner)
    assert excinfo.value.timed_out
    assert excinfo.value.stage == "clone"


def test_render_run_dockerfile_installs_dependencies_and_drops_root() -> None:
    dockerfile = render_run_dockerfile()
    lines = [line.strip() for line in dockerfile.splitlines()]
    assert lines[0] == "FROM bug-fix-agent-sandbox:latest"
    assert lines[1] == "USER root"
    assert "COPY repo/ /workspace/" in lines
    assert "pip install --no-cache-dir -r /workspace/requirements.txt" in dockerfile
    assert lines[-2] == "USER nonroot"
    assert lines[-1] == "WORKDIR /workspace"


def test_render_run_dockerfile_rejects_an_injected_image() -> None:
    with pytest.raises(ValueError):
        render_run_dockerfile("alpine\nRUN evil")


def test_clone_and_test_bakes_repo_then_runs_locked_down() -> None:
    runner = Recorder([0, 0, 0])
    result = clone_and_test(REPO_URL, container_name="sandbox-abc", runner=runner)

    assert result.ok
    assert result.stage == "tests"
    assert [cmd[0] for cmd in runner.calls] == ["git", "docker", "docker"]
    assert runner.calls[1][:2] == ["docker", "build"]

    run_cmd = runner.calls[2]
    assert "bug-fix-agent-run:sandbox-abc" in run_cmd
    assert "--network=none" in run_cmd
    assert "--read-only" in run_cmd
    assert "--user=nonroot" in run_cmd
    assert run_cmd[-6:] == ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def test_clone_and_test_reports_clone_failure_as_environment_error() -> None:
    runner = Recorder([128])
    result = clone_and_test(REPO_URL, container_name="sandbox-abc", runner=runner)

    assert not result.ok
    assert result.environment_error
    assert result.stage == "clone"
    assert result.message() == "reproduction failed - could not clone repository"
    assert len(runner.calls) == 1


def test_clone_and_test_reports_build_failure_as_environment_error() -> None:
    runner = Recorder([0, 1])
    result = clone_and_test(REPO_URL, container_name="sandbox-abc", runner=runner)

    assert result.environment_error
    assert result.stage == "build"
    assert result.message() == "reproduction failed - could not prepare dependencies"
    assert len(runner.calls) == 2


def test_clone_and_test_reports_clone_timeout_without_running_tests() -> None:
    runner = Recorder([subprocess.TimeoutExpired(["git", "clone"], 120)])
    result = clone_and_test(REPO_URL, container_name="sandbox-abc", runner=runner)

    assert result.timed_out
    assert result.exit_code == 124
    assert result.stage == "clone"
    assert result.message() == "sandbox timed out during clone"
    assert len(runner.calls) == 1


def test_clone_and_test_rejects_an_invalid_container_name() -> None:
    with pytest.raises(ValueError):
        clone_and_test(REPO_URL, container_name="--privileged", runner=Recorder([]))


def test_custom_test_command_is_used() -> None:
    runner = Recorder([0, 0, 0])
    config = SandboxConfig(test_command=("python", "-m", "pytest", "tests/test_bug.py"))
    clone_and_test(REPO_URL, container_name="sandbox-abc", config=config, runner=runner)

    assert runner.calls[2][-4:] == ["python", "-m", "pytest", "tests/test_bug.py"]
