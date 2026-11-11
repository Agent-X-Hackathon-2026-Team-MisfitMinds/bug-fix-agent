"""End-to-end sandbox run against the public demo repository.

Opt in with RUN_DOCKER_TESTS=1 after building
apps/api/docker/sandbox.Dockerfile as bug-fix-agent-sandbox:latest.

This is the only test that proves the flow the pipeline depends on:
anonymous clone -> isolated container -> pytest -> cleanup. Every other
sandbox test injects a fake `runner`, so they cannot catch Docker-level
regressions (the original bug was `git clone` inside `--network=none`).
"""
import os

import pytest

from pipeline.sandbox import (
    SandboxConfig,
    clone_and_test,
    container_name,
    repository_url,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_TESTS") != "1",
    reason="set RUN_DOCKER_TESTS=1 and build the sandbox image to run Docker integration tests",
)

DEMO_REPO = "Agent-X-Hackathon-2026-Team-MisfitMinds/seeded-demo-repo"


def test_the_demo_repository_clones_and_passes_its_suite() -> None:
    result, passed = clone_and_test(
        repository_url(DEMO_REPO),
        SandboxConfig(timeout_seconds=180),
        container_name("demo"),
    )

    assert result.environment_error is False, result.stderr
    assert result.timed_out is False
    assert passed is True, result.stdout + result.stderr
    assert result.exit_code == 0
    assert "passed" in result.stdout
    assert "error" not in result.stdout.lower()


def test_a_missing_repository_is_an_environment_error_not_a_red_baseline() -> None:
    result, passed = clone_and_test(
        repository_url("Agent-X-Hackathon-2026-Team-MisfitMinds/definitely-not-a-repo"),
        SandboxConfig(timeout_seconds=60),
        container_name("missing"),
    )

    assert result.environment_error is True
    assert passed is False
