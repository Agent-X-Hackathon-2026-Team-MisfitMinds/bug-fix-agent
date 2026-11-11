"""Thin wrapper around the Docker sandbox for running pytest suites."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.sandbox import run_workspace_tests_async


@dataclass
class PytestResult:
    passed: bool
    output: str
    exit_code: int


class PytestRunner:
    def __init__(self, workspace: Path | None = None, timeout: int = 120) -> None:
        self.workspace = workspace
        self.timeout = timeout

    async def run(self, test_file: str, timeout: int | None = None) -> PytestResult:
        # Placeholder: real impl should run the specific test file in sandbox.
        return PytestResult(passed=False, output="", exit_code=1)

    async def run_suite(self, timeout: int | None = None) -> PytestResult:
        if self.workspace is None:
            return PytestResult(passed=False, output="", exit_code=1)
        result = await run_workspace_tests_async(self.workspace, self.workspace / "tests")
        return PytestResult(passed=getattr(result, "ok", False), output=getattr(result, "stdout", ""), exit_code=getattr(result, "exit_code", 1))
PY