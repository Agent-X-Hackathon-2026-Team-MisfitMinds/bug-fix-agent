import io
import subprocess
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pipeline.sandbox import (
    SANDBOX_GID,
    SANDBOX_UID,
    SandboxConfig,
    SandboxError,
    clone_and_test,
    prepare_workspace,
    repository_url,
    run_workspace_tests,
)

CONFIG = SandboxConfig(timeout_seconds=30)


class Recorder:
    """Fake docker/git CLI that records commands without touching Docker."""

    def __init__(
        self,
        *,
        fail: Callable[[list[str]], bool] | None = None,
        timeout: Callable[[list[str]], bool] | None = None,
    ) -> None:
        self.commands: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self._fail = fail or (lambda command: False)
        self._timeout = timeout or (lambda command: False)

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        self.commands.append(command)
        self.kwargs.append(kwargs)
        if self._timeout(command):
            raise subprocess.TimeoutExpired(command, 30, output="partial", stderr="hung")
        code = 1 if self._fail(command) else 0
        return subprocess.CompletedProcess(
            command,
            code,
            stdout="",
            stderr="failure" if code else "",
        )

    def exec_commands(self) -> list[list[str]]:
        return [command for command in self.commands if command[:2] == ["docker", "exec"]]


def make_workspace(tmp_path: Path, *, requirements: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    if requirements:
        (root / "requirements.txt").write_text("pytest==8.3.4\n", encoding="utf-8")
    return root


def test_repository_url_builds_anonymous_https_clone_url() -> None:
    assert repository_url("octo/demo") == "https://github.com/octo/demo.git"


@pytest.mark.parametrize("repository", ["octo", "octo/demo/extra", "../etc", "octo/.."])
def test_repository_url_rejects_malformed_names(repository: str) -> None:
    with pytest.raises(ValueError):
        repository_url(repository)


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:octo/demo.git",
        "https://user:token@github.com/octo/demo.git",
        "http://github.com/octo/demo.git",
        "https://github.com/octo/demo.git --upload-pack=evil",
    ],
)
def test_prepare_workspace_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError):
        prepare_workspace(url)


def test_prepare_workspace_disables_credentials_and_prompts(tmp_path: Path) -> None:
    destination = tmp_path / "clone"
    recorder = Recorder()

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        destination.mkdir()
        return recorder(command, **kwargs)

    workspace = prepare_workspace(
        "https://github.com/octo/demo.git",
        destination=destination,
        runner=runner,
    )

    assert workspace == destination
    command = recorder.commands[0]
    assert command[:4] == ["git", "-c", "credential.helper=", "clone"]
    assert "--depth" in command
    env = recorder.kwargs[0]["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_prepare_workspace_surfaces_clone_failure(tmp_path: Path) -> None:
    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 128, stdout="", stderr="repository not found")

    with pytest.raises(SandboxError, match="repository not found"):
        prepare_workspace(
            "https://github.com/octo/missing.git",
            destination=tmp_path / "clone",
            runner=runner,
        )


def test_child_process_env_drops_secrets_but_keeps_the_host_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "super-secret")
    monkeypatch.setenv("BFA_HARMLESS_FLAG", "1")
    destination = tmp_path / "clone"
    recorder = Recorder()

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        destination.mkdir()
        return recorder(command, **kwargs)

    prepare_workspace(
        "https://github.com/octo/demo.git",
        destination=destination,
        runner=runner,
    )

    env = recorder.kwargs[0]["env"]
    assert "GITHUB_APP_PRIVATE_KEY" not in env
    assert env["BFA_HARMLESS_FLAG"] == "1"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_workspace_tests_reject_an_invalid_container_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_workspace_tests(
            make_workspace(tmp_path, requirements=False),
            CONFIG,
            "--privileged",
        )


def test_workspace_tests_require_an_existing_workspace(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        run_workspace_tests(tmp_path / "missing", CONFIG, "sandbox-abc")


def test_workspace_flow_installs_then_disconnects_before_tests(tmp_path: Path) -> None:
    recorder = Recorder()

    result = run_workspace_tests(make_workspace(tmp_path), CONFIG, "sandbox-abc", runner=recorder)

    assert result.ok
    assert [command[:2] for command in recorder.commands] == [
        ["docker", "network"],
        ["docker", "run"],
        ["docker", "exec"],
        ["docker", "exec"],
        ["docker", "network"],
        ["docker", "exec"],
        ["docker", "rm"],
        ["docker", "network"],
    ]

    run_command = recorder.commands[1]
    assert "--network=bfa-sandbox-abc" in run_command
    assert "--user=nonroot" in run_command
    assert "--read-only" in run_command
    assert "--cap-drop" in run_command
    assert any("/workspace:rw,exec,nosuid,size=256m,mode=1777" == arg for arg in run_command)

    extract, install, tests = recorder.exec_commands()
    assert extract[-4:] == ["tar", "-x", "-C", "/workspace"]
    assert "--target" in install
    assert install[install.index("--target") + 1] == "/workspace/.deps"
    disconnect = recorder.commands[4]
    assert disconnect[:3] == ["docker", "network", "disconnect"]
    assert "--env" in tests and "PYTHONPATH=/workspace/.deps" in tests
    assert tests[-6:] == ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    assert ["docker", "rm", "-f", "sandbox-abc"] in recorder.commands


def test_workspace_archive_is_owned_by_sandbox_user(tmp_path: Path) -> None:
    recorder = Recorder()

    run_workspace_tests(make_workspace(tmp_path), CONFIG, "sandbox-abc", runner=recorder)

    archive_bytes = recorder.kwargs[2]["input"]
    assert isinstance(archive_bytes, bytes)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        members = {member.name: member for member in archive.getmembers()}
    assert "src/app.py" in members
    assert "tests/test_app.py" in members
    assert members["src/app.py"].uid == SANDBOX_UID
    assert members["src/app.py"].gid == SANDBOX_GID
    assert members["src/app.py"].mode == 0o644
    assert members["src"].mode == 0o755
    assert ".git" not in members


def test_workspace_without_requirements_runs_offline(tmp_path: Path) -> None:
    recorder = Recorder()

    result = run_workspace_tests(
        make_workspace(tmp_path, requirements=False),
        CONFIG,
        "sandbox-abc",
        runner=recorder,
    )

    assert result.ok
    run_command = next(command for command in recorder.commands if command[:2] == ["docker", "run"])
    assert "--network=none" in run_command
    assert not any("pip" in command for command in recorder.commands)
    assert not any("disconnect" in command for command in recorder.commands)
    assert len(recorder.exec_commands()) == 2


def test_dependency_install_failure_is_an_environment_error(tmp_path: Path) -> None:
    recorder = Recorder(fail=lambda command: "pip" in command)

    result = run_workspace_tests(make_workspace(tmp_path), CONFIG, "sandbox-abc", runner=recorder)

    assert result.environment_error
    assert not result.ok
    assert "dependency installation failed" in result.stderr
    assert not any("pytest" in command for command in recorder.commands)


def test_timeout_removes_the_container_and_reports_timed_out(tmp_path: Path) -> None:
    recorder = Recorder(timeout=lambda command: "pytest" in command)

    result = run_workspace_tests(make_workspace(tmp_path), CONFIG, "sandbox-abc", runner=recorder)

    assert result.timed_out
    assert result.exit_code == 124
    assert ["docker", "rm", "-f", "sandbox-abc"] in recorder.commands
    assert ["docker", "network", "rm", "bfa-sandbox-abc"] in recorder.commands


def test_workspace_tests_append_extra_test_paths(tmp_path: Path) -> None:
    recorder = Recorder()

    run_workspace_tests(
        make_workspace(tmp_path),
        CONFIG,
        "sandbox-abc",
        test_paths=("tests/test_app.py",),
        runner=recorder,
    )

    tests = recorder.exec_commands()[-1]
    assert tests[-1] == "tests/test_app.py"


def test_clone_and_test_reports_clone_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object, **__: object) -> Path:
        raise SandboxError("repository not found")

    monkeypatch.setattr("pipeline.sandbox.prepare_workspace", boom)

    result, passed = clone_and_test(
        "https://github.com/octo/missing.git", CONFIG, "sandbox-abc", runner=Recorder()
    )

    assert result.environment_error
    assert passed is False


def test_clone_and_test_removes_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = make_workspace(tmp_path)
    monkeypatch.setattr("pipeline.sandbox.prepare_workspace", lambda *_, **__: workspace)

    result, passed = clone_and_test(
        "https://github.com/octo/demo.git", CONFIG, "sandbox-abc", runner=Recorder()
    )

    assert result.ok and passed
    assert not workspace.exists()
