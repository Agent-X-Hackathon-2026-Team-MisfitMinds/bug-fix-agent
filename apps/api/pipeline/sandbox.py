"""Docker sandbox wrapper for untrusted repository tests.

The command never mounts the host filesystem, never receives tokens or
secrets, runs as a non-root user with capped CPU/memory/PIDs, and has no
network access after dependencies are baked into the image.

`clone_and_test()` glues the two halves together: the repository is cloned on
the host with the caller's token, baked into a throwaway image (dependency
install runs while the image build still has network), and only then executed
with the locked-down flags below. The token never enters the container.
"""
import base64
import os
import re
import secrets
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SANDBOX_IMAGE = "bug-fix-agent-sandbox:latest"
SANDBOX_USER = "nonroot"
RUN_IMAGE_PREFIX = "bug-fix-agent-run"
DEFAULT_TIMEOUT_SECONDS = 300
CLONE_TIMEOUT_SECONDS = 120
BUILD_TIMEOUT_SECONDS = 180
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = "1.0"
GIT_HOSTS = frozenset({"github.com", "www.github.com"})

Runner = Callable[..., subprocess.CompletedProcess[str]]

_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_IMAGE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$")
_REF = re.compile(r"^(?!-)[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")

_PREPARATION_MESSAGES = {
    "clone": "reproduction failed - could not clone repository",
    "build": "reproduction failed - could not prepare dependencies",
}

_RUN_DOCKERFILE = """FROM {base_image}
USER root
COPY repo/ /workspace/
RUN chown -R {user}:{user} /workspace \\
    && if [ -f /workspace/requirements.txt ]; then \\
        python -m pip install --no-cache-dir -r /workspace/requirements.txt; \\
    fi
USER {user}
WORKDIR /workspace
"""


class PreparationError(RuntimeError):
    """Raised when the repository cannot be cloned or baked into an image."""

    def __init__(self, stage: str, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.stage = stage
        self.timed_out = timed_out


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
    stage: str = "tests"

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.environment_error

    def message(self) -> str:
        if self.timed_out:
            if self.stage == "tests":
                return "sandbox timed out after five minutes"
            return f"sandbox timed out during {self.stage}"
        if self.environment_error:
            if self.stage == "tests":
                return "reproduction failed - environment issue"
            return _PREPARATION_MESSAGES.get(
                self.stage, f"reproduction failed - {self.stage} error"
            )
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


def validate_repo_url(repo_url: str) -> str:
    """Return the hostname of a safe GitHub HTTPS clone URL."""
    try:
        parsed = urlsplit(repo_url)
    except ValueError as exc:
        raise ValueError("Invalid repository URL") from exc
    if parsed.scheme != "https":
        raise ValueError("Repository URL must use https")
    host = (parsed.hostname or "").lower()
    if host not in GIT_HOSTS:
        raise ValueError("Repository URL must point at github.com")
    if parsed.username or parsed.password:
        raise ValueError("Repository URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Repository URL must not include a query or fragment")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if path.count("/") != 1 or not all(path.split("/")):
        raise ValueError("Repository URL must include an owner and repository")
    return host


def validate_ref(ref: str) -> None:
    if not _REF.fullmatch(ref) or ".." in ref or "//" in ref:
        raise ValueError("Invalid git ref")


def _cli_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }


def _git_env(token: str | None, host: str) -> dict[str, str]:
    """Token travels in an env-var gitconfig, never in argv or the URL."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    # Git for Windows resolves DNS through libraries under %SystemRoot%.
    for name in ("SYSTEMROOT", "WINDIR"):
        if os.environ.get(name):
            env[name] = os.environ[name]
    if token:
        credential = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": f"http.https://{host}/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credential}",
            }
        )
    return env


def _redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def _tail(text: str, limit: int = 1000) -> str:
    text = text.strip()
    return text if len(text) <= limit else "..." + text[-limit:]


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


def _remove_image(tag: str) -> None:
    try:
        subprocess.run(
            ["docker", "image", "rm", "-f", tag],
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
    runner: Runner | None = None,
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


def clone_repo(
    repo_url: str,
    dest: Path,
    *,
    ref: str = "main",
    token: str | None = None,
    timeout_seconds: int = CLONE_TIMEOUT_SECONDS,
    runner: Runner | None = None,
) -> None:
    """Shallow-clone one branch on the host, before anything is containerized."""
    host = validate_repo_url(repo_url)
    validate_ref(ref)
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--branch",
        ref,
        "--no-tags",
        "--no-recurse-submodules",
        "--",
        repo_url,
        str(dest),
    ]
    execute = runner or subprocess.run
    try:
        completed = execute(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=_git_env(token, host),
        )
    except subprocess.TimeoutExpired:
        raise PreparationError("clone", "git clone timed out", timed_out=True) from None
    except FileNotFoundError:
        raise PreparationError("clone", "git executable not found") from None
    if completed.returncode != 0:
        detail = _redact(_as_text(completed.stderr), token)
        raise PreparationError("clone", _tail(detail) or "git clone failed")


def render_run_dockerfile(base_image: str = SANDBOX_IMAGE) -> str:
    if not _IMAGE_REFERENCE.fullmatch(base_image):
        raise ValueError("Invalid base image")
    return _RUN_DOCKERFILE.format(base_image=base_image, user=SANDBOX_USER)


def build_repo_image(
    context: Path,
    tag: str,
    *,
    base_image: str = SANDBOX_IMAGE,
    timeout_seconds: int = BUILD_TIMEOUT_SECONDS,
    runner: Runner | None = None,
) -> None:
    """Bake `context/repo` into an image; dependency install needs network."""
    if not _IMAGE_REFERENCE.fullmatch(tag):
        raise ValueError("Invalid image tag")
    (context / "Dockerfile").write_text(render_run_dockerfile(base_image), encoding="utf-8")
    (context / ".dockerignore").write_text("repo/.git\n**/.git\n", encoding="utf-8")
    cmd = ["docker", "build", "--file", str(context / "Dockerfile"), "--tag", tag, str(context)]
    execute = runner or subprocess.run
    try:
        completed = execute(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=_cli_env(),
        )
    except subprocess.TimeoutExpired:
        raise PreparationError("build", "docker build timed out", timed_out=True) from None
    except FileNotFoundError:
        raise PreparationError("build", "docker executable not found") from None
    if completed.returncode != 0:
        detail = _as_text(completed.stderr)
        raise PreparationError("build", _tail(detail) or "docker build failed")


def clone_and_test(
    repo_url: str,
    *,
    ref: str = "main",
    container_name: str | None = None,
    config: SandboxConfig = SandboxConfig(),
    token: str | None = None,
    runner: Runner | None = None,
) -> SandboxResult:
    """Clone a GitHub repository and run its tests in the isolated sandbox."""
    name = container_name or f"sandbox-{secrets.token_hex(6)}"
    if not _CONTAINER_NAME.fullmatch(name):
        raise ValueError("Invalid container name")
    tag = f"{RUN_IMAGE_PREFIX}:{name}"
    try:
        with tempfile.TemporaryDirectory(prefix="bug-fix-sandbox-") as tmp:
            context = Path(tmp)
            try:
                clone_repo(repo_url, context / "repo", ref=ref, token=token, runner=runner)
                build_repo_image(context, tag, base_image=config.image, runner=runner)
            except PreparationError as exc:
                return SandboxResult(
                    exit_code=124 if exc.timed_out else 1,
                    stdout="",
                    stderr=str(exc),
                    timed_out=exc.timed_out,
                    environment_error=not exc.timed_out,
                    stage=exc.stage,
                )
            return run_sandbox(replace(config, image=tag), name, runner=runner)
    finally:
        if runner is None:
            _remove_image(tag)


def install_command(package: str = ".") -> tuple[str, ...]:
    """Dependency install runs while the image still has network access."""
    return ("python", "-m", "pip", "install", "--no-cache-dir", package)
