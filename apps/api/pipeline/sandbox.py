"""Docker sandbox wrapper for untrusted repository tests.

The command never mounts the host filesystem, never receives tokens or
secrets, runs as a non-root user with capped CPU/memory/PIDs, and has no
network access after dependencies are baked into the image.
"""
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SANDBOX_IMAGE = "bug-fix-agent-sandbox:latest"
SANDBOX_USER = "nonroot"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = "1.0"

_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


@dataclass(frozen=True)
class SandboxConfig:
    image: str = SANDBOX_IMAGE
    memory: str = DEFAULT_MEMORY
    cpus: str = DEFAULT_CPUS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    test_command: tuple[str, ...] = (
        "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
    )


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    environment_error: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.environment_error

    def message(self) -> str:
        if self.timed_out:
            return "sandbox timed out after five minutes"
        if self.environment_error:
            return "reproduction failed - environment issue"
        return "tests passed" if self.ok else "tests failed"


def build_docker_cmd(config: SandboxConfig, container_name: str) -> list[str]:
    if not _CONTAINER_NAME.fullmatch(container_name):
        raise ValueError("Invalid container name")
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network=none",
        f"--user={SANDBOX_USER}",
        f"--memory={config.memory}",
        f"--cpus={config.cpus}",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        "128",
        config.image,
        *config.test_command,
    ]


def _cli_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }


def _force_remove(container_name: str) -> None:
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=_cli_env(),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_sandbox(
    config: SandboxConfig,
    container_name: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> SandboxResult:
    cmd = build_docker_cmd(config, container_name)
    execute = runner or subprocess.run
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": config.timeout_seconds,
        "check": False,
        "env": _cli_env(),
    }
    try:
        completed = execute(cmd, **kwargs)
    except subprocess.TimeoutExpired as exc:
        if runner is None:
            _force_remove(container_name)
        return SandboxResult(
            exit_code=124,
            stdout=_as_text(exc.stdout),
            stderr=_as_text(exc.stderr),
            timed_out=True,
        )
    except FileNotFoundError:
        return SandboxResult(
            exit_code=127,
            stdout="",
            stderr="docker executable not found",
            environment_error=True,
        )

    return SandboxResult(
        exit_code=completed.returncode,
        stdout=_as_text(completed.stdout),
        stderr=_as_text(completed.stderr),
        environment_error=completed.returncode == 125,
    )


def install_command(package: str = ".") -> tuple[str, ...]:
    """Dependency install runs while the image still has network access."""
    return ("python", "-m", "pip", "install", "--no-cache-dir", package)


def clone_repository(
    repo_url: str,
    container_name: str,
    timeout: int = 60,
) -> tuple[bool, str]:
    """Clone a repository inside a Docker container.

    Returns (success, message) tuple.
    """
    cmd = [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--network=none",
        f"--user={SANDBOX_USER}",
        f"--memory={DEFAULT_MEMORY}",
        f"--cpus={DEFAULT_CPUS}",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        "128",
        SANDBOX_IMAGE,
        "git", "clone", repo_url, "/workspace",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, "Repository cloned successfully"
        else:
            return False, f"Git clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Git clone timed out"


def clone_and_test(
    repo_url: str,
    config: SandboxConfig,
    container_name: str,
    *,
    install_first: bool = True,
) -> tuple[SandboxResult, bool]:
    """Full workflow: clone repository, optionally install deps, then run tests.

    This is the main function the LangGraph reproduce_node should call.

    Args:
        repo_url: URL of the GitHub repository to clone
        config: Sandbox configuration
        container_name: Name for the Docker container
        install_first: If True, install dependencies before running tests
            (requires network access). If False, assumes dependencies are
            already baked into the image.

    Returns:
        Tuple of (SandboxResult, bool) where bool indicates if the workflow
        completed successfully (not timed out).
    """
    # Step 1: Clone the repository
    success, clone_msg = clone_repository(repo_url, container_name)
    if not success:
        # Return a failed result
        failed_result = SandboxResult(
            exit_code=1,
            stdout="",
            stderr=clone_msg,
            environment_error=True,
        )
        return failed_result, False

    # Step 2: If install_first, install dependencies (requires network)
    if install_first:
        install_container_name = f"{container_name}-install"
        install_result = run_sandbox(config, install_container_name)
        if not install_result.ok:
            # Return failed result - couldn't install dependencies
            return SandboxResult(
                exit_code=1,
                stdout="",
                stderr=f"Dependency installation failed: {install_result.stderr}",
                environment_error=True,
            ), False

    # Step 3: Run tests (network should be disabled now)
    # run_tests helper not yet implemented; return a placeholder failure result
    test_result = SandboxResult(exit_code=1, stdout="", stderr="run_tests not implemented", timed_out=False)
    _ = container_name
    _ = config if False else None

    # Return combined result
    success = test_result.ok and not test_result.timed_out
    return test_result, success


# ------------------------------------------------------------
# Example Usage for Pipeline Integration
# ------------------------------------------------------------


def example_usage() -> None:
    """Example of how LangGraph reproduce_node would use the sandbox."""

    from .sandbox import SandboxConfig

    config = SandboxConfig()
    _ = config

    # Example 1: Full clone + install + test workflow
    # repo_url = "https://github.com/user/bug-fix-agent-demo.git"
    # container_name = "bugfix-agent-test-1"
    # result, success = clone_and_test(repo_url, config, container_name)
    # print(f"Result: {result.message()}, Success: {success}")

    # Example 2: Just run tests (assume image already has deps)
    # container_name = "bugfix-agent-test-2"
    # result = run_sandbox(config, container_name)
    # print(f"Test result: {result.message()}")
