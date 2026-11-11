"""Workspace helpers must stay inside the clone and apply only exact patches."""
import asyncio
from pathlib import Path

import pytest

from pipeline.workspace import (
    PatchError,
    WorkspaceSecurityError,
    apply_patch,
    read_file,
    repo_snapshot,
    repo_structure,
    write_file,
)


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text(
        "def calculate_discount(price, discount):\n"
        "    return price - discount + 1\n",
        encoding="utf-8",
    )
    return workspace


def test_read_file_returns_workspace_content(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    assert "calculate_discount" in asyncio.run(read_file(workspace, "src/app.py"))


@pytest.mark.parametrize("path", ["../secret.txt", "src/../../secret.txt"])
def test_read_file_rejects_path_traversal(tmp_path: Path, path: str) -> None:
    workspace = make_workspace(tmp_path)
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(WorkspaceSecurityError):
        asyncio.run(read_file(workspace, path))


def test_read_file_rejects_absolute_paths(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(WorkspaceSecurityError):
        asyncio.run(read_file(workspace, str(outside)))


def test_git_metadata_is_never_readable(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".git").mkdir()
    (workspace / ".git" / "config").write_text("[core]", encoding="utf-8")
    with pytest.raises(WorkspaceSecurityError):
        asyncio.run(read_file(workspace, ".git/config"))


def test_write_file_creates_parent_directories(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    target = asyncio.run(write_file(workspace, "tests/test_new.py", "def test_x():\n    pass\n"))
    assert target == workspace / "tests" / "test_new.py"
    assert target.read_text(encoding="utf-8") == "def test_x():\n    pass\n"


def test_apply_patch_replaces_one_exact_snippet_and_returns_full_content(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    patched = asyncio.run(
        apply_patch(
            workspace,
            "src/app.py",
            "    return price - discount + 1\n",
            "    return price - discount\n",
        )
    )
    assert patched == (
        "def calculate_discount(price, discount):\n"
        "    return price - discount\n"
    )
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == patched


def test_apply_patch_rejects_missing_snippet(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    with pytest.raises(PatchError, match="not found"):
        asyncio.run(apply_patch(workspace, "src/app.py", "missing", "replacement"))


def test_apply_patch_rejects_ambiguous_snippet(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / "src" / "app.py").write_text(
        "value = 1\nvalue = 1\n", encoding="utf-8"
    )
    with pytest.raises(PatchError, match="occurs 2 times"):
        asyncio.run(apply_patch(workspace, "src/app.py", "value = 1", "value = 2"))


def test_apply_patch_rejects_a_no_op(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    with pytest.raises(PatchError, match="identical"):
        asyncio.run(apply_patch(workspace, "src/app.py", "return 1", "return 1"))


def test_repo_structure_omits_caches_and_vcs_data(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / ".git").mkdir()
    (workspace / ".git" / "config").write_text("x", encoding="utf-8")
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "app.pyc").write_bytes(b"x")
    (workspace / "README.md").write_text("hello", encoding="utf-8")

    structure = repo_structure(workspace)

    assert structure["files"] == ["README.md", "src/app.py"]


def test_snapshot_is_bounded_and_contains_text_files(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / "README.md").write_text("read me", encoding="utf-8")
    (workspace / "logo.png").write_bytes(b"\x89PNG")
    (workspace / "big.py").write_text("x" * 200, encoding="utf-8")

    snapshot = repo_snapshot(workspace, max_bytes=100)

    paths = [item["path"] for item in snapshot["files"]]
    assert paths == ["README.md", "src/app.py"]
    assert snapshot["files"][1]["content"].startswith("def calculate_discount")
