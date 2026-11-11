"""Runs the real sandbox image. Opt in with RUN_DOCKER_TESTS=1 after
building apps/api/docker/sandbox.Dockerfile as bug-fix-agent-sandbox:latest.
"""
import os
import subprocess

import pytest

from pipeline.sandbox import SandboxConfig, clone_and_test, run_sandbox

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_TESTS") != "1",
    reason="set RUN_DOCKER_TESTS=1 and build the sandbox image to run Docker integration tests",
)

PROBE = "\n".join(
    [
        "import os, socket",
        "print('uid', os.getuid())",
        "s = socket.socket(); s.settimeout(2)",
        "try:",
        "    s.connect(('1.1.1.1', 53)); print('NETWORK_OPEN')",
        "except OSError:",
        "    print('NETWORK_BLOCKED')",
        "try:",
        "    open('/etc/hostname', 'a').write('x'); print('WRITE_ALLOWED')",
        "except OSError:",
        "    print('WRITE_BLOCKED')",
    ]
)


def test_sandbox_isolates_network_user_and_filesystem() -> None:
    result = run_sandbox(SandboxConfig(test_command=("python", "-c", PROBE)), "test-isolation")

    assert result.exit_code == 0
    assert "uid 10001" in result.stdout
    assert "NETWORK_BLOCKED" in result.stdout
    assert "NETWORK_OPEN" not in result.stdout
    assert "WRITE_BLOCKED" in result.stdout
    assert "WRITE_ALLOWED" not in result.stdout


CLONE_PROBE = "\n".join(
    [
        "import os, pathlib",
        "print('uid', os.getuid())",
        "print(sorted(p.name for p in pathlib.Path('/workspace').iterdir()))",
    ]
)


def test_clone_and_test_runs_a_real_repository() -> None:
    result = clone_and_test(
        "https://github.com/octocat/Hello-World",
        ref="master",
        container_name="test-clone",
        config=SandboxConfig(test_command=("python", "-c", CLONE_PROBE)),
    )

    assert result.ok
    assert "uid 10001" in result.stdout
    assert "README" in result.stdout

    images = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "bug-fix-agent-run:test-clone" not in images.stdout


def test_sandbox_times_out_and_removes_container() -> None:
    result = run_sandbox(
        SandboxConfig(
            timeout_seconds=5,
            test_command=("python", "-c", "import time; time.sleep(600)"),
        ),
        "test-timeout",
    )

    assert result.exit_code == 124
    assert result.timed_out
    assert result.message() == "sandbox timed out after five minutes"

    leftovers = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=test-timeout", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert leftovers.stdout.strip() == ""
