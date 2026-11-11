"""Safe helpers for reading and editing a cloned repository workspace.

Every path is resolved inside the workspace root. Absolute paths, ``..``
segments and symlinks that escape the root are rejected. Patches are applied
atomically and only when the target snippet occurs exactly once, so the agent
can never silently rewrite an unrelated part of the repository.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)
_TEXT_SUFFIXES = frozenset(
    {
        ".cfg",
        ".ini",
        ".md",
        ".py",
        ".pyi",
        ".rst",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)
MAX_SNAPSHOT_FILES = 40
MAX_SNAPSHOT_BYTES = 40_000


class WorkspaceError(RuntimeError):
    """Base error for workspace operations."""


class WorkspaceSecurityError(WorkspaceError):
    """Raised when a path would escape the workspace root."""


class PatchError(WorkspaceError):
    """Raised when an exact-match patch cannot be applied."""


def _relative(path: str) -> PurePosixPath:
    if not path or "\x00" in path:
        raise WorkspaceSecurityError("A non-empty relative path is required")
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or candidate.drive:
        raise WorkspaceSecurityError(f"Absolute paths are not allowed: {path!r}")
    if any(part == ".." for part in candidate.parts):
        raise WorkspaceSecurityError(f"Path traversal is not allowed: {path!r}")
    if ".git" in candidate.parts:
        raise WorkspaceSecurityError(f"Git metadata is not writable by the agent: {path!r}")
    return candidate


def _resolve(workspace: Path, path: str) -> Path:
    relative = _relative(path)
    root = Path(workspace).resolve()
    try:
        target = (root / relative).resolve()
    except OSError as exc:  # pragma: no cover - platform-specific failures
        raise WorkspaceSecurityError(f"Could not resolve {path!r}") from exc
    if target != root and root not in target.parents:
        raise WorkspaceSecurityError(f"Path escapes the workspace: {path!r}")
    if target == root:
        raise WorkspaceSecurityError("Target path must name a file")
    return target


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def repo_structure(workspace: Path) -> dict[str, Any]:
    """Return the repository's tracked-looking files, without caches or VCS data."""
    root = Path(workspace).resolve()
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in relative.parts):
            continue
        files.append(relative.as_posix())
    return {"root": str(root), "files": files}


async def read_file(workspace: Path, path: str) -> str:
    """Read a UTF-8 file from inside the workspace."""
    target = _resolve(workspace, path)
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8")


async def write_file(workspace: Path, path: str, content: str) -> Path:
    """Atomically write a UTF-8 file inside the workspace."""
    target = _resolve(workspace, path)
    if target.is_dir():
        raise IsADirectoryError(path)
    _atomic_write(target, content)
    return target


async def apply_patch(workspace: Path, file_path: str, old_code: str, new_code: str) -> str:
    """Replace one exact snippet and return the complete patched file.

    The newline style of the original file is preserved because the snippet is
    replaced verbatim. A snippet that is missing or ambiguous aborts the patch.
    """
    if not old_code:
        raise PatchError("old_code must not be empty")
    if old_code == new_code:
        raise PatchError("old_code and new_code are identical")

    target = _resolve(workspace, file_path)
    if not target.is_file():
        raise FileNotFoundError(file_path)
    original = target.read_text(encoding="utf-8")
    occurrences = original.count(old_code)
    if occurrences == 0:
        raise PatchError(f"old_code was not found in {file_path}")
    if occurrences > 1:
        raise PatchError(f"old_code occurs {occurrences} times in {file_path}; refusing an ambiguous patch")

    patched = original.replace(old_code, new_code, 1)
    _atomic_write(target, patched)
    return patched


def repo_snapshot(
    workspace: Path,
    *,
    max_files: int = MAX_SNAPSHOT_FILES,
    max_bytes: int = MAX_SNAPSHOT_BYTES,
) -> dict[str, Any]:
    """Return a bounded text snapshot for LLM prompts.

    Binary and oversized files are skipped. All paths are repository-relative
    and are treated as untrusted data by the prompt builders.
    """
    root = Path(workspace).resolve()
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= max_files:
            break
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        files.append({"path": relative.as_posix(), "content": content})
    return {"root": str(root), "files": files}
