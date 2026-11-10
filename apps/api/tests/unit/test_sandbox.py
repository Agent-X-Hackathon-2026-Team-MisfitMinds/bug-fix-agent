import subprocess
from typing import Any

import pytest

from pipeline.sandbox import (
    SandboxConfig,
    build_docker_cmd,
    install_command,
    run_sandbox,
)

CONFIG = SandboxConfig()


def test_build_command_has_isolation_flags() -> None:
    cmd = build_docker_cmd(CONFIG, "sandbox-abc")
    assert "--network=none" in cmd
    assert "--user=nonroot" in cmd
    assert "--memory=512m" in cmd
    assert "--cpus=1.0" in cmd
    assert "--read-only" in cmd
    assert "--cap-drop" in cmd
    assert "--pids-limit" in cmd
    assert "no-new-privileges" in cmd


def test_build_command_has_no_mounts_or_secrets() -> None:
    cmd = build_docker_cmd(CONFIG, "sandbox-abc")
    joined = " ".join(cmd)
    assert "-v" not in cmd
    assert "--mount" not in cmd
    assert "--privileged" not in cmd
    assert "--env" not in cmd
    assert "-e" not in cmd
    for secret_name in ("GITHUB", "SESSION_SECRET", "LLM_API_KEY", "WEBHOOK"):
        assert secret_name not in joined


def test_build_command_appends_test_command() -> None:
    config = SandboxConfig(test_command=("python", "-m", "pytest", "tests/test_x.py"))
    cmd = build_docker_cmd(config, "sandbox-abc")
    assert cmd[-4:] == ["python", "-m", "pytest", "tests/test_x.py"]


def test_invalid_container_name_rejected() -> None:
    with pytest.raises(ValueError):
        build_docker_cmd(CONFIG, "--privileged")


def test_successful_run_is_ok() -> None:
    def runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="2 passed", stderr="")

    result = run_sandbox(CONFIG, "sandbox-abc", runner=runner)
    assert result.ok
    assert result.exit_code == 0
    assert result.stdout == "2 passed"
    assert result.message() == "tests passed"


def test_failed_tests_are_not_ok() -> None:
    def runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="1 failed", stderr="")

    result = run_sandbox(CONFIG, "sandbox-abc", runner=runner)
    assert not result.ok
    assert result.message() == "tests failed"


def test_timeout_reports_structured_result() -> None:
    def runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 300, output="partial", stderr="hung")

    result = run_sandbox(CONFIG, "sandbox-abc", runner=runner)
    assert result.timed_out
    assert result.exit_code == 124
    assert result.stdout == "partial"
    assert "timed out" in result.message()


def test_docker_startup_failure_is_environment_error() -> None:
    def runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 125, stdout="", stderr="daemon down")

    result = run_sandbox(CONFIG, "sandbox-abc", runner=runner)
    assert result.environment_error
    assert not result.ok
    assert result.message() == "reproduction failed - environment issue"


def test_missing_docker_is_environment_error() -> None:
    def runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    result = run_sandbox(CONFIG, "sandbox-abc", runner=runner)
    assert result.environment_error
    assert result.exit_code == 127


def test_install_command_does_not_use_a_shell() -> None:
    command = install_command("pytest==8.3.4")
    assert command[0] == "python"
    assert "pytest==8.3.4" in command
    assert "sh" not in command
