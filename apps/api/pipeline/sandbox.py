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
