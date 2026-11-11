"""Thin wrapper around the Docker sandbox for running pytest suites."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.sandbox import (
    SandboxConfig,
    SandboxResult,
    container_name,
    run_workspace_tests_async,
)


@dataclass
class PytestResult:
    passed: bool
    output: str
    exit_code: int
    timed_out: bool = False
    environment_error: bool = False


class PytestRunner:
    """Run pytest for a workspace inside the Docker sandbox."""

    def __init__(
        self,
        workspace: Path | None = None,
        timeout: int = 120,
        issue_id: int = 0,
    ) -> None:
        self.workspace = workspace
        self.timeout = timeout
        self.issue_id = issue_id

    def _config(self, timeout: int | None) -> SandboxConfig:
        return SandboxConfig(timeout_seconds=timeout if timeout is not None else self.timeout)

    def _container(self) -> str:
        return container_name(self.issue_id)

    @staticmethod
    def _result(result: SandboxResult) -> PytestResult:
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n{result.stderr.strip()}".strip()
        return PytestResult(
            passed=result.ok,
            output=output or result.message(),
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            environment_error=result.environment_error,
        )

    def _no_workspace(self) -> PytestResult:
        return PytestResult(
            passed=False,
            output="no workspace configured",
            exit_code=1,
            environment_error=True,
        )

    @staticmethod
    def _test_path(test_file: str) -> str:
        path = test_file.replace("\\", "/")
        if path.startswith("/") or any(part == ".." for part in path.split("/")):
            raise ValueError("test_file must be a workspace-relative path")
        return path

    async def run(self, test_file: str, timeout: int | None = None) -> PytestResult:
        """Run a single test file inside the sandbox workspace."""
        if self.workspace is None:
            return self._no_workspace()
        result = await run_workspace_tests_async(
            self.workspace,
            self._config(timeout),
            self._container(),
            test_paths=[self._test_path(test_file)],
        )
        return self._result(result)

    async def run_suite(self, timeout: int | None = None) -> PytestResult:
        """Run the full test suite inside the sandbox workspace."""
        if self.workspace is None:
            return self._no_workspace()
        result = await run_workspace_tests_async(
            self.workspace,
            self._config(timeout),
            self._container(),
        )
        return self._result(result)
