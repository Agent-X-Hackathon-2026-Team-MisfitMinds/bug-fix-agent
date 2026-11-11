"""Workspace helpers for reading files and applying patches in the sandbox."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def repo_structure(workspace: Path) -> dict[str, Any]:
    files = []
    for p in workspace.rglob("*"):
        if p.is_file():
            files.append(str(p.relative_to(workspace)).as_posix())
    return {"root": str(workspace), "files": files}


async def read_file(workspace: Path, path: str) -> str:
    target = (workspace / path).resolve()
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8")


async def apply_patch(workspace: Path, patch: str) -> bool:
    # Minimal: write patch to a file for later application; real impl should git apply.
    (workspace / ".agent.patch").write_text(patch, encoding="utf-8")
    return True
