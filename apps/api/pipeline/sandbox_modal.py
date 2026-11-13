"""Hosted sandbox backend for platforms without a Docker daemon (e.g. Render).

Same contract as `pipeline.sandbox.run_workspace_tests`, but the tests run in a
Modal Sandbox (gVisor-isolated, disposable) instead of a local container:

1. create one sandbox that holds no secrets - it only ever receives the repo tar;
2. copy the workspace archive in and unpack it;
3. optionally install dependencies with network, then drop all outbound traffic;
4. run pytest and terminate the sandbox.

Select it with ``SANDBOX_BACKEND=modal``; the SDK authenticates from
``MODAL_TOKEN_ID`` / ``MODAL_TOKEN_SECRET``. Unlike the Docker backend the
tests run as root inside the sandbox, which is the isolation boundary here.
"""
from __future__ import annotations

import contextlib
import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pipeline.sandbox import (
    DEPS_DIR,
    WORKSPACE_DIR,
    SandboxConfig,
    SandboxError,
    SandboxResult,
    _archive,
    _environment_error,
    _requirements_file,
)

MODAL_APP = "bug-fix-agent-sandbox"
MODAL_MEMORY_MIB = 512  # matches DEFAULT_MEMORY of the Docker backend
ARCHIVE_PATH = "/tmp/workspace.tar"
SETUP_TIMEOUT_SECONDS = 120
TIMEOUT_EXIT_CODE = 124  # coreutils `timeout`, same code the Docker backend reports


def _exec(
    sandbox: Any,
    *cmd: str,
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run `cmd` under coreutils `timeout` so a hang always ends with exit 124."""
    process = sandbox.exec(
        "timeout", "--kill-after=5", str(timeout), *cmd,
        workdir=WORKSPACE_DIR,
        env=env,
        timeout=timeout + 30,  # backstop only; `timeout` above fires first
    )
    stdout = process.stdout.read()
    stderr = process.stderr.read()
    return int(process.wait()), str(stdout or ""), str(stderr or "")


def run_workspace_tests_modal(
    workspace: Path,
    config: SandboxConfig,
    container_name: str,
    *,
    install_dependencies: bool = True,
    test_paths: Sequence[str] = (),
) -> SandboxResult:
    """Copy `workspace` into one Modal Sandbox and run its tests offline."""
    root = Path(workspace)
    if not root.is_dir():
        raise SandboxError(f"Workspace {root} does not exist")

    requirements = _requirements_file(root) if install_dependencies else None
    # `block_network` cannot be lifted or combined with the runtime policy API,
    # so a sandbox that must install first starts open and is closed below.
    network: dict[str, Any] = (
        {"block_network": True}
        if requirements is None
        else {"outbound_domain_allowlist": ["*"], "outbound_cidr_allowlist": ["0.0.0.0/0"]}
    )
    lifetime = (
        SETUP_TIMEOUT_SECONDS + config.install_timeout_seconds + config.timeout_seconds
    )

    sandbox: Any = None
    try:
        modal: Any = importlib.import_module("modal")
        sandbox = modal.Sandbox.create(
            "sleep", "infinity",
            app=modal.App.lookup(MODAL_APP, create_if_missing=True),
            image=modal.Image.debian_slim(python_version="3.12").pip_install("pytest==8.3.4"),
            cpu=float(config.cpus),
            memory=MODAL_MEMORY_MIB,
            timeout=lifetime,
            **network,
        )
        sandbox.filesystem.write_bytes(_archive(root), ARCHIVE_PATH)
        sandbox.exec("mkdir", "-p", WORKSPACE_DIR).wait()
        code, _, stderr = _exec(
            sandbox, "tar", "-x", "-f", ARCHIVE_PATH, "-C", WORKSPACE_DIR,
            timeout=SETUP_TIMEOUT_SECONDS,
        )
        if code != 0:
            return _environment_error(
                "could not copy the workspace into the sandbox: "
                + (stderr.strip() or "tar extraction failed")
            )

        test_env: dict[str, str] | None = None
        if requirements is not None:
            code, _, stderr = _exec(
                sandbox,
                "python", "-m", "pip", "install",
                "--no-cache-dir", "--quiet", "--target", DEPS_DIR,
                "-r", f"{WORKSPACE_DIR}/{requirements.name}",
                timeout=config.install_timeout_seconds,
                env={"PIP_DISABLE_PIP_VERSION_CHECK": "1"},
            )
            if code != 0:
                return _environment_error(
                    "dependency installation failed: "
                    + (stderr.strip() or "pip install failed")
                )
            # Fail closed: if the network cannot be cut this raises and the run
            # is reported as an environment error instead of testing online.
            sandbox._experimental_set_outbound_network_policy(
                outbound_domain_allowlist=[],
                outbound_cidr_allowlist=[],
            )
            test_env = {"PYTHONPATH": DEPS_DIR}

        code, stdout, stderr = _exec(
            sandbox, *config.test_command, *test_paths,
            timeout=config.timeout_seconds,
            env=test_env,
        )
        return SandboxResult(
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            timed_out=code == TIMEOUT_EXIT_CODE,
        )
    except Exception as exc:  # noqa: BLE001 - SDK, auth and transport errors are all infrastructure
        return _environment_error(
            f"modal sandbox {container_name} failed: {type(exc).__name__}: {exc}"
        )
    finally:
        if sandbox is not None:
            with contextlib.suppress(Exception):  # its lifetime cap reaps it anyway
                sandbox.terminate()
