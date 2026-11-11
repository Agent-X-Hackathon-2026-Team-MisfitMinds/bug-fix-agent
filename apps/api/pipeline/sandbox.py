"""Docker sandbox wrapper for untrusted repository tests.

Each run is a single, disposable container created from ``bug-fix-agent-sandbox``:

1. shallow-clone the public repository on the host (anonymous HTTPS, no prompts,
   no stored credentials);
2. start one container with a tmpfs workspace, a read-only root filesystem, no
   host mounts, no secrets and capped CPU/memory/PIDs;
3. stream the tree into the container as a tar archive owned by ``nonroot``;
4. optionally install dependencies *with* network, then disconnect the
   container from its network so tests always run offline;
5. run pytest as ``nonroot`` and delete the container, network and workspace.

`clone_and_test` is the entry point the pipeline calls. It is synchronous (it
shells out to Docker); asyncio callers use `clone_and_test_async`.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

SANDBOX_IMAGE = "bug-fix-agent-sandbox:latest"
SANDBOX_USER = "nonroot"
SANDBOX_UID = 10001
SANDBOX_GID = 10001
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_INSTALL_TIMEOUT_SECONDS = 180
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = "1.0"

WORKSPACE_DIR = "/workspace"
DEPS_DIR = f"{WORKSPACE_DIR}/.deps"
_ARCHIVE_SKIP = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"})

_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_SECRET_ENV = re.compile(
    r"(GITHUB|SESSION|LLM|WEBHOOK|TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)",
    re.IGNORECASE,
)

DockerRunner = Callable[..., Any]


class SandboxError(RuntimeError):
    """Raised when the workspace cannot be prepared or is unusable."""


@dataclass(frozen=True)
class SandboxConfig:
    image: str = SANDBOX_IMAGE
    memory: str = DEFAULT_MEMORY
    cpus: str = DEFAULT_CPUS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    install_timeout_seconds: int = DEFAULT_INSTALL_TIMEOUT_SECONDS
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
    """Inherit the host environment minus anything secret-shaped.

    Windows needs ``SystemRoot``/``windir`` for DNS and sockets, so stripping
    the environment down to PATH+HOME silently breaks `git clone`. Dropping
    secret-looking variables keeps tokens out of every child process.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not _SECRET_ENV.search(key)
    }


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _docker(
    cmd: list[str],
    *,
    timeout: int,
    runner: DockerRunner | None = None,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[Any]:
    execute = runner or subprocess.run
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "timeout": timeout,
        "check": False,
        "env": _cli_env(),
    }
    if input_bytes is None:
        kwargs["text"] = True
    else:
        kwargs["input"] = input_bytes
    return cast(subprocess.CompletedProcess[Any], execute(cmd, **kwargs))


def _force_remove(container_name: str, *, runner: DockerRunner | None = None) -> None:
    execute = runner or subprocess.run
    try:
        execute(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=_cli_env(),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _environment_error(message: str) -> SandboxResult:
    return SandboxResult(
        exit_code=1,
        stdout="",
        stderr=message,
        environment_error=True,
    )


def run_sandbox(
    config: SandboxConfig,
    container_name: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> SandboxResult:
    """Run the configured command in a throwaway container with no workspace."""
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
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr),
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
        stdout=_text(completed.stdout),
        stderr=_text(completed.stderr),
        environment_error=completed.returncode == 125,
    )


def install_command(package: str = ".") -> tuple[str, ...]:
    """Dependency install runs while the image still has network access."""
    return ("python", "-m", "pip", "install", "--no-cache-dir", package)


def repository_url(repository: str) -> str:
    """Build the anonymous HTTPS clone URL for an ``owner/name`` repository."""
    if not _REPOSITORY.fullmatch(repository) or ".." in repository:
        raise ValueError("Repository must be in owner/name form")
    return f"https://github.com/{repository}.git"


def container_name(issue_id: int | str, *, suffix: str | None = None) -> str:
    """Unique, Docker-valid container name for one pipeline run.

    Retries and concurrent runs must not reuse a name: a leftover container
    would make the next ``docker run`` fail with a name conflict.
    """
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "-", str(issue_id))[:40]
    return f"bfa-{sanitized}-{(suffix or uuid4().hex)[:8]}"[:63]


def _validate_repo_url(repo_url: str) -> str:
    if repo_url.startswith("-") or any(character.isspace() for character in repo_url):
        raise ValueError("repo_url must be a plain https URL")
    if not repo_url.startswith("https://"):
        raise ValueError("repo_url must use https")
    authority = repo_url[len("https://"):].split("/", 1)[0]
    if not authority or "@" in authority:
        raise ValueError("repo_url must not carry credentials")
    return repo_url


def prepare_workspace(
    repo_url: str,
    *,
    destination: Path | None = None,
    timeout: int = 120,
    runner: DockerRunner | None = None,
) -> Path:
    """Shallow-clone `repo_url` on the host and return the workspace path.

    The clone is anonymous: credential helpers are disabled and git is told not
    to prompt, so a missing/invalid repository fails fast instead of hanging.
    """
    url = _validate_repo_url(repo_url)
    target = Path(destination) if destination is not None else Path(
        tempfile.mkdtemp(prefix="bfa-workspace-")
    )
    created_here = destination is None
    cmd = [
        "git",
        "-c", "credential.helper=",
        "clone",
        "--depth", "1",
        "--no-tags",
        "--single-branch",
        url,
        str(target),
    ]
    env = {**_cli_env(), "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}
    execute = runner or subprocess.run
    try:
        completed = execute(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        if created_here:
            shutil.rmtree(target, ignore_errors=True)
        raise SandboxError(f"git clone failed: {exc}") from exc
    if completed.returncode != 0:
        stderr = _text(completed.stderr).strip() or "git clone failed"
        if created_here:
            shutil.rmtree(target, ignore_errors=True)
        raise SandboxError(stderr)
    return target


def _requirements_file(workspace: Path) -> Path | None:
    """Return ``requirements.txt`` only when it pins at least one package.

    The seeded demo repo ships a comments-only file; installing from it needs a
    network round-trip for nothing, so treat it as "no dependencies".
    """
    candidate = workspace / "requirements.txt"
    if not candidate.is_file():
        return None
    for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            return candidate
    return None


def _archive(workspace: Path) -> bytes:
    """Pack the workspace with sandbox-user ownership and safe modes.

    Symlinks are never followed or stored: they could point outside the
    workspace, and the container only needs regular files.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for dirpath, dirnames, filenames in os.walk(workspace, followlinks=False):
            directory = Path(dirpath)
            dirnames[:] = sorted(name for name in dirnames if name not in _ARCHIVE_SKIP)
            entries = [directory / name for name in dirnames]
            entries += [directory / name for name in sorted(filenames)]
            for path in entries:
                relative = path.relative_to(workspace)
                if path.is_symlink() or any(part in _ARCHIVE_SKIP for part in relative.parts):
                    continue
                info = archive.gettarinfo(str(path), arcname=relative.as_posix())
                info.uid = SANDBOX_UID
                info.gid = SANDBOX_GID
                info.uname = SANDBOX_USER
                info.gname = SANDBOX_USER
                info.mode = 0o755 if info.isdir() else 0o644
                if path.is_file():
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)
                elif info.isdir():
                    archive.addfile(info)
    return buffer.getvalue()


def _network_name(container_name: str) -> str:
    return f"bfa-{container_name}"[:63]


def run_workspace_tests(
    workspace: Path,
    config: SandboxConfig,
    container_name: str,
    *,
    install_dependencies: bool = True,
    test_paths: Sequence[str] = (),
    runner: DockerRunner | None = None,
) -> SandboxResult:
    """Copy `workspace` into one sandbox container and run its tests.

    Dependencies in a root ``requirements.txt`` are installed first with network
    access; the network is then disconnected before pytest runs, so the tested
    code can never make outbound calls. A failed install is reported as an
    environment error and pytest is never started.
    """
    if not _CONTAINER_NAME.fullmatch(container_name):
        raise ValueError("Invalid container name")
    root = Path(workspace)
    if not root.is_dir():
        raise SandboxError(f"Workspace {root} does not exist")

    requirements = _requirements_file(root) if install_dependencies else None
    network = _network_name(container_name)
    network_created = False
    timeout = config.timeout_seconds

    try:
        if requirements is not None:
            created = _docker(
                ["docker", "network", "create", "--label", "app=bug-fix-agent", network],
                timeout=60,
                runner=runner,
            )
            if created.returncode != 0:
                return _environment_error(
                    "could not create sandbox network: "
                    + (_text(created.stderr).strip() or "docker network create failed")
                )
            network_created = True

        container = _docker(
            [
                "docker", "run",
                "--detach",
                "--name", container_name,
                f"--network={network if network_created else 'none'}",
                f"--user={SANDBOX_USER}",
                f"--memory={config.memory}",
                f"--cpus={config.cpus}",
                "--read-only",
                "--tmpfs", f"{WORKSPACE_DIR}:rw,exec,nosuid,size=256m,mode=1777",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                "--security-opt", "no-new-privileges",
                "--cap-drop", "ALL",
                "--pids-limit", "128",
                config.image,
                "sleep", "infinity",
            ],
            timeout=60,
            runner=runner,
        )
        if container.returncode != 0:
            return _environment_error(
                "could not start sandbox container: "
                + (_text(container.stderr).strip() or "docker run failed")
            )

        extracted = _docker(
            [
                "docker", "exec", "-i",
                f"--user={SANDBOX_USER}",
                "--workdir", WORKSPACE_DIR,
                container_name,
                "tar", "-x", "-C", WORKSPACE_DIR,
            ],
            timeout=120,
            runner=runner,
            input_bytes=_archive(root),
        )
        if extracted.returncode != 0:
            return _environment_error(
                "could not copy the workspace into the sandbox: "
                + (_text(extracted.stderr).strip() or "tar extraction failed")
            )

        test_env: list[str] = []
        if requirements is not None:
            install = _docker(
                [
                    "docker", "exec",
                    f"--user={SANDBOX_USER}",
                    "--workdir", WORKSPACE_DIR,
                    "--env", "PIP_DISABLE_PIP_VERSION_CHECK=1",
                    container_name,
                    "python", "-m", "pip", "install",
                    "--no-cache-dir", "--quiet", "--target", DEPS_DIR,
                    "-r", f"{WORKSPACE_DIR}/{requirements.name}",
                ],
                timeout=config.install_timeout_seconds,
                runner=runner,
            )
            if install.returncode != 0:
                return _environment_error(
                    "dependency installation failed: "
                    + (_text(install.stderr).strip() or "pip install failed")
                )
            test_env = ["--env", f"PYTHONPATH={DEPS_DIR}"]
            disconnected = _docker(
                ["docker", "network", "disconnect", network, container_name],
                timeout=30,
                runner=runner,
            )
            if disconnected.returncode != 0:
                return _environment_error(
                    "could not disable network before tests: "
                    + (_text(disconnected.stderr).strip() or "network disconnect failed")
                )

        tests = _docker(
            [
                "docker", "exec",
                f"--user={SANDBOX_USER}",
                "--workdir", WORKSPACE_DIR,
                *test_env,
                container_name,
                *config.test_command,
                *test_paths,
            ],
            timeout=timeout,
            runner=runner,
        )
        return SandboxResult(
            exit_code=tests.returncode,
            stdout=_text(tests.stdout),
            stderr=_text(tests.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        _force_remove(container_name, runner=runner)
        return SandboxResult(
            exit_code=124,
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr),
            timed_out=True,
        )
    except FileNotFoundError:
        return SandboxResult(
            exit_code=127,
            stdout="",
            stderr="docker executable not found",
            environment_error=True,
        )
    finally:
        _force_remove(container_name, runner=runner)
        if network_created:
            try:
                _docker(["docker", "network", "rm", network], timeout=30, runner=runner)
            except (OSError, subprocess.SubprocessError):
                pass


def clone_and_test(
    repo_url: str,
    config: SandboxConfig,
    container_name: str,
    *,
    install_first: bool = True,
    runner: DockerRunner | None = None,
) -> tuple[SandboxResult, bool]:
    """Clone `repo_url`, run its suite in the sandbox and clean up.

    Returns ``(result, passed)`` where ``passed`` is true only when pytest
    exited zero. Infrastructure problems (clone, docker, install, timeout) are
    reported as ``environment_error``/``timed_out`` so callers never confuse
    them with a red baseline.
    """
    workspace: Path | None = None
    try:
        workspace = prepare_workspace(repo_url, runner=runner)
        result = run_workspace_tests(
            workspace,
            config,
            container_name,
            install_dependencies=install_first,
            runner=runner,
        )
    except SandboxError as exc:
        return _environment_error(str(exc)), False
    finally:
        if workspace is not None:
            shutil.rmtree(workspace, ignore_errors=True)
    return result, result.ok


async def run_workspace_tests_async(
    workspace: Path,
    config: SandboxConfig,
    container_name: str,
    *,
    install_dependencies: bool = True,
    test_paths: Sequence[str] = (),
) -> SandboxResult:
    """`run_workspace_tests` without blocking the API event loop."""
    return await asyncio.to_thread(
        run_workspace_tests,
        Path(workspace),
        config,
        container_name,
        install_dependencies=install_dependencies,
        test_paths=test_paths,
    )


async def clone_and_test_async(
    repo_url: str,
    config: SandboxConfig,
    container_name: str,
    *,
    install_first: bool = True,
) -> tuple[SandboxResult, bool]:
    """Awaitable form of `clone_and_test` for the async pipeline."""
    return await asyncio.to_thread(
        clone_and_test,
        repo_url,
        config,
        container_name,
        install_first=install_first,
    )
