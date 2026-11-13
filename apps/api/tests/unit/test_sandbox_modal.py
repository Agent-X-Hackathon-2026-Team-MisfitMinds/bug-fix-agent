"""Modal sandbox backend, exercised against a fake `modal` module (no network)."""
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pipeline.sandbox import DEPS_DIR, SandboxConfig
from pipeline.sandbox_modal import run_workspace_tests_modal

CONFIG = SandboxConfig()


class FakeSandbox:
    """Records every call; `exit_codes` maps a command word to its exit code."""

    def __init__(self, exit_codes: dict[str, int], create_kwargs: dict[str, Any]) -> None:
        self.exit_codes = exit_codes
        self.create_kwargs = create_kwargs
        self.events: list[str] = []
        self.envs: dict[str, dict[str, str] | None] = {}
        self.terminated = False
        self.filesystem = SimpleNamespace(
            write_bytes=lambda data, path: self.events.append("upload")
        )

    def exec(self, *cmd: str, **kwargs: Any) -> Any:
        word = next(
            (name for name in ("pytest", "pip", "tar", "mkdir") if name in cmd), cmd[0]
        )
        self.events.append(word)
        self.envs[word] = kwargs.get("env")
        code = self.exit_codes.get(word, 0)
        stream = SimpleNamespace(read=lambda: f"{word} output")
        return SimpleNamespace(stdout=stream, stderr=stream, wait=lambda: code)

    def _experimental_set_outbound_network_policy(self, **policy: Any) -> None:
        assert policy == {"outbound_domain_allowlist": [], "outbound_cidr_allowlist": []}
        self.events.append("network-cut")

    def terminate(self) -> None:
        self.terminated = True


def install_fake_modal(
    monkeypatch: pytest.MonkeyPatch,
    exit_codes: dict[str, int] | None = None,
    create_error: Exception | None = None,
) -> list[FakeSandbox]:
    created: list[FakeSandbox] = []

    def create(*_: str, **kwargs: Any) -> FakeSandbox:
        if create_error is not None:
            raise create_error
        created.append(FakeSandbox(exit_codes or {}, kwargs))
        return created[-1]

    image = SimpleNamespace(pip_install=lambda *_: "image")
    fake = SimpleNamespace(
        Sandbox=SimpleNamespace(create=create),
        App=SimpleNamespace(lookup=lambda *_, **__: "app"),
        Image=SimpleNamespace(debian_slim=lambda **_: image),
    )
    monkeypatch.setitem(sys.modules, "modal", fake)
    return created


def workspace(tmp_path: Path, requirements: str | None = None) -> Path:
    (tmp_path / "test_x.py").write_text("def test_x():\n    assert True\n")
    if requirements is not None:
        (tmp_path / "requirements.txt").write_text(requirements)
    return tmp_path


def test_no_requirements_runs_fully_offline_and_terminates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = install_fake_modal(monkeypatch)
    result = run_workspace_tests_modal(
        workspace(tmp_path, "# comments only\n"), CONFIG, "bfa-1", test_paths=["test_x.py"]
    )
    (sandbox,) = created
    assert result.ok and result.stdout == "pytest output"
    assert sandbox.create_kwargs["block_network"] is True
    assert "outbound_cidr_allowlist" not in sandbox.create_kwargs
    assert sandbox.events == ["upload", "mkdir", "tar", "pytest"]
    assert sandbox.terminated


def test_requirements_install_then_network_is_cut_before_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = install_fake_modal(monkeypatch)
    result = run_workspace_tests_modal(workspace(tmp_path, "attrs==24.2.0\n"), CONFIG, "bfa-2")
    (sandbox,) = created
    assert result.ok
    assert "block_network" not in sandbox.create_kwargs
    assert sandbox.events == ["upload", "mkdir", "tar", "pip", "network-cut", "pytest"]
    assert sandbox.envs["pytest"] == {"PYTHONPATH": DEPS_DIR}


@pytest.mark.parametrize(
    ("exit_codes", "ok", "timed_out", "environment_error"),
    [
        ({"pytest": 1}, False, False, False),
        ({"pytest": 124}, False, True, False),
        ({"tar": 2}, False, False, True),
        ({"pip": 1}, False, False, True),
    ],
)
def test_exit_codes_map_to_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_codes: dict[str, int],
    ok: bool,
    timed_out: bool,
    environment_error: bool,
) -> None:
    created = install_fake_modal(monkeypatch, exit_codes)
    result = run_workspace_tests_modal(workspace(tmp_path, "attrs==24.2.0\n"), CONFIG, "bfa-3")
    assert (result.ok, result.timed_out, result.environment_error) == (
        ok, timed_out, environment_error,
    )
    # A failed setup step must never reach pytest.
    assert ("pytest" in created[0].events) == (not environment_error)
    assert created[0].terminated


def test_sdk_failure_is_an_environment_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_modal(monkeypatch, create_error=RuntimeError("token missing"))
    result = run_workspace_tests_modal(workspace(tmp_path), CONFIG, "bfa-4")
    assert result.environment_error
    assert "token missing" in result.stderr
