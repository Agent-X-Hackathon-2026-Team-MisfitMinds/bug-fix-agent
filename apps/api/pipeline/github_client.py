"""GitHub REST client used by the pipeline: read issues, open draft PRs.

Authenticates as the GitHub App installation (see `github_app.py`). Branch
creation goes through the Git Data API so the agent never clones with write
access and never needs to run `git push`.
"""
import re
from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import quote

import httpx

from config import get_settings
from github_app import GITHUB_API, API_VERSION, GitHubAppAuth, auth_from_settings

_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_REF = re.compile(r"^(?!-)[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_AGENT_BRANCH_PREFIX = "agent/"
_MAX_COMMENT_CHARS = 65_000


class GitHubAPIError(RuntimeError):
    """Raised when GitHub rejects a request or returns an unusable payload."""


def _validate_repo(repository: str) -> str:
    if not _REPO.fullmatch(repository) or repository.count("/") != 1:
        raise GitHubAPIError("Repository must be in owner/name form")
    return repository


def _validate_ref(ref: str) -> str:
    if not _REF.fullmatch(ref) or ".." in ref or "//" in ref or ref.endswith("/"):
        raise GitHubAPIError(f"Invalid git ref: {ref!r}")
    return ref


def _validate_files(files: Mapping[str, str]) -> dict[str, str]:
    if not files:
        raise GitHubAPIError("At least one file is required to open a pull request")
    checked: dict[str, str] = {}
    for path, content in files.items():
        if not path or path.startswith("/") or "\\" in path or ".." in path.split("/"):
            raise GitHubAPIError(f"Invalid file path: {path!r}")
        checked[path] = content
    return checked


def _payload(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise GitHubAPIError(f"GitHub returned a non-JSON response ({response.status_code})") from exc
    if not isinstance(body, dict):
        raise GitHubAPIError(f"GitHub returned an unexpected payload ({response.status_code})")
    return cast(dict[str, Any], body)


def _nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            raise GitHubAPIError(f"GitHub payload is missing {'.'.join(keys)}")
        current = current.get(key)
    if not isinstance(current, str) or not current:
        raise GitHubAPIError(f"GitHub payload is missing {'.'.join(keys)}")
    return current


def _describe(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    message = body.get("message") if isinstance(body, dict) else None
    errors = body.get("errors") if isinstance(body, dict) else None
    detail = message or "request failed"
    if errors:
        detail = f"{detail}: {errors}"
    return f"HTTP {response.status_code}: {detail}"


class GitHubClient:
    """REST client bound to one App installation and one repository."""

    def __init__(
        self,
        auth: GitHubAppAuth,
        installation_id: int,
        repository: str,
        *,
        api_base: str = GITHUB_API,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        if installation_id <= 0:
            raise GitHubAPIError("A positive installation id is required")
        self._auth = auth
        self.installation_id = installation_id
        self.repository = _validate_repo(repository)
        self._api_base = api_base.rstrip("/")
        self._transport = transport
        self._timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in (0, 1):
            headers = {
                "Authorization": f"Bearer {self._auth.installation_token(self.installation_id)}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
            }
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    f"{self._api_base}{path}",
                    headers=headers,
                    json=json_body,
                )
            if response.status_code != 401 or attempt == 1:
                return response
            self._auth.invalidate(self.installation_id)
        if response is None:
            raise GitHubAPIError("GitHub request was never sent")
        return response

    async def _expect(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        allowed: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        response = await self._request(method, path, json_body=json_body)
        if response.status_code not in allowed:
            raise GitHubAPIError(_describe(response))
        return _payload(response)

    async def get_issue(self, number: int, repository: str | None = None) -> dict[str, Any]:
        repo = _validate_repo(repository or self.repository)
        if number <= 0:
            raise GitHubAPIError("Issue number must be positive")
        return await self._expect("GET", f"/repos/{repo}/issues/{number}")

    async def add_issue_comment(
        self,
        number: int,
        body: str,
        repository: str | None = None,
    ) -> dict[str, Any]:
        """Post a markdown comment on an issue (used for honest failure notes)."""
        repo = _validate_repo(repository or self.repository)
        if number <= 0:
            raise GitHubAPIError("Issue number must be positive")
        text = body.strip()
        if not text:
            raise GitHubAPIError("Comment body is required")
        return await self._expect(
            "POST",
            f"/repos/{repo}/issues/{number}/comments",
            json_body={"body": text[:_MAX_COMMENT_CHARS]},
            allowed=(201,),
        )

    async def get_repo(self, repository: str | None = None) -> dict[str, Any]:
        repo = _validate_repo(repository or self.repository)
        return await self._expect("GET", f"/repos/{repo}")

    async def base_commit(self, ref: str = "main", repository: str | None = None) -> tuple[str, str]:
        repo = _validate_repo(repository or self.repository)
        branch = _validate_ref(ref)
        reference = await self._expect("GET", f"/repos/{repo}/git/ref/heads/{quote(branch, safe='/')}")
        commit_sha = _nested_str(reference, "object", "sha")
        commit = await self._expect("GET", f"/repos/{repo}/git/commits/{commit_sha}")
        return commit_sha, _nested_str(commit, "tree", "sha")

    async def _create_or_update_ref(self, repo: str, branch: str, commit_sha: str) -> None:
        response = await self._request(
            "POST",
            f"/repos/{repo}/git/refs",
            json_body={"ref": f"refs/heads/{branch}", "sha": commit_sha},
        )
        if response.status_code == 201:
            return
        if response.status_code != 422:
            raise GitHubAPIError(_describe(response))
        if not branch.startswith(_AGENT_BRANCH_PREFIX):
            raise GitHubAPIError(
                f"Branch {branch!r} already exists and is not owned by the agent"
            )
        updated = await self._request(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{quote(branch, safe='/')}",
            json_body={"sha": commit_sha, "force": True},
        )
        if updated.status_code != 200:
            raise GitHubAPIError(_describe(updated))

    async def _open_pull(
        self,
        repo: str,
        branch: str,
        base: str,
        title: str,
        body: str,
        maintainer_can_modify: bool,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json_body={
                "title": title,
                "head": branch,
                "base": base,
                "body": body,
                "draft": True,
                "maintainer_can_modify": maintainer_can_modify,
            },
        )
        if response.status_code == 201:
            return _payload(response)
        if response.status_code == 422:
            owner = repo.split("/")[0]
            query = f"head={quote(f'{owner}:{branch}', safe='')}&state=open"
            existing = await self._request("GET", f"/repos/{repo}/pulls?{query}")
            if existing.status_code == 200:
                pulls = existing.json()
                if isinstance(pulls, list) and pulls and isinstance(pulls[0], dict):
                    return cast(dict[str, Any], pulls[0])
        raise GitHubAPIError(_describe(response))

    async def push_branch_and_open_draft_pr(
        self,
        *,
        branch_name: str,
        pr_title: str,
        pr_body: str,
        files: Mapping[str, str],
        base_branch: str = "main",
        maintainer_can_modify: bool = True,
        commit_message: str | None = None,
        repository: str | None = None,
    ) -> dict[str, Any]:
        """Commit `files` on a new branch and open a draft pull request."""
        if not pr_title.strip():
            raise GitHubAPIError("Pull request title is required")
        repo = _validate_repo(repository or self.repository)
        branch = _validate_ref(branch_name)
        base = _validate_ref(base_branch)
        contents = _validate_files(files)

        base_sha, base_tree = await self.base_commit(base, repo)
        entries = []
        for path, content in contents.items():
            blob = await self._expect(
                "POST",
                f"/repos/{repo}/git/blobs",
                json_body={"content": content, "encoding": "utf-8"},
                allowed=(201,),
            )
            entries.append(
                {"path": path, "mode": "100644", "type": "blob", "sha": _nested_str(blob, "sha")}
            )
        tree = await self._expect(
            "POST",
            f"/repos/{repo}/git/trees",
            json_body={"base_tree": base_tree, "tree": entries},
            allowed=(201,),
        )
        commit = await self._expect(
            "POST",
            f"/repos/{repo}/git/commits",
            json_body={
                "message": commit_message or f"Fix: {pr_title}",
                "tree": _nested_str(tree, "sha"),
                "parents": [base_sha],
            },
            allowed=(201,),
        )
        commit_sha = _nested_str(commit, "sha")
        await self._create_or_update_ref(repo, branch, commit_sha)
        pull = await self._open_pull(repo, branch, base, pr_title, pr_body, maintainer_can_modify)
        return {
            "pr_url": _nested_str(pull, "html_url"),
            "pr_number": pull.get("number"),
            "branch": branch,
            "commit": commit_sha,
        }


_default_client: GitHubClient | None = None


def default_client() -> GitHubClient:
    """Process-wide client built from `.env`; the pipeline calls this lazily."""
    global _default_client
    if _default_client is None:
        settings = get_settings()
        if not settings.github_repository.strip():
            raise GitHubAPIError("GITHUB_DEMO_REPO is not configured")
        _default_client = GitHubClient(
            auth_from_settings(settings),
            settings.github_installation_id,
            settings.github_repository,
        )
    return _default_client


def reset_default_client() -> None:
    global _default_client
    _default_client = None


async def get_issue(issue_id: int) -> dict[str, Any]:
    return await default_client().get_issue(issue_id)


async def add_issue_comment(issue_number: int, body: str) -> dict[str, Any]:
    return await default_client().add_issue_comment(issue_number, body)


async def get_repo(repo_name: str | None = None) -> dict[str, Any]:
    return await default_client().get_repo(repo_name)


async def push_branch_and_open_draft_pr(
    *,
    branch_name: str,
    pr_title: str,
    pr_body: str,
    files: Mapping[str, str],
    base_branch: str = "main",
    maintainer_can_modify: bool = True,
    commit_message: str | None = None,
) -> dict[str, Any]:
    return await default_client().push_branch_and_open_draft_pr(
        branch_name=branch_name,
        pr_title=pr_title,
        pr_body=pr_body,
        files=files,
        base_branch=base_branch,
        maintainer_can_modify=maintainer_can_modify,
        commit_message=commit_message,
    )
