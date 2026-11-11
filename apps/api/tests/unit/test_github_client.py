import asyncio
import json
from typing import Any, cast

import httpx
import pytest

from github_app import GitHubAppAuth
from pipeline.github_client import GitHubAPIError, GitHubClient


class StaticAuth(GitHubAppAuth):
    """Auth double: the token exchange itself is covered by test_github_app.py."""

    def __init__(self, token: str = "ghs_test") -> None:
        self.token = token
        self.invalidations = 0

    def installation_token(self, installation_id: int) -> str:
        return self.token

    def invalidate(self, installation_id: int) -> None:
        self.invalidations += 1
        self.token = f"{self.token}-refreshed"


class Recorder:
    def __init__(self, responses: dict[tuple[str, str], list[httpx.Response]]) -> None:
        self._responses = responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.path)
        queued = self._responses.get(key)
        if not queued:
            return httpx.Response(404, json={"message": f"unexpected {key}"})
        return queued.pop(0) if len(queued) > 1 else queued[0]


def _client(recorder: Recorder, auth: StaticAuth | None = None) -> GitHubClient:
    return GitHubClient(
        auth or StaticAuth(),
        42,
        "octo/repo",
        transport=httpx.MockTransport(recorder),
        timeout=5.0,
    )


def _body(request: httpx.Request) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(request.content))


def test_get_issue_uses_token_and_repository_path() -> None:
    recorder = Recorder(
        {("GET", "/repos/octo/repo/issues/1"): [httpx.Response(200, json={"number": 1})]}
    )

    issue = asyncio.run(_client(recorder).get_issue(1))

    assert issue["number"] == 1
    request = recorder.requests[0]
    assert str(request.url) == "https://api.github.com/repos/octo/repo/issues/1"
    assert request.headers["Authorization"] == "Bearer ghs_test"


def test_get_repo_rejects_malformed_name() -> None:
    recorder = Recorder({})
    with pytest.raises(GitHubAPIError):
        asyncio.run(_client(recorder).get_repo("../../etc/passwd"))
    assert recorder.requests == []


def test_add_issue_comment_posts_trimmed_markdown() -> None:
    recorder = Recorder(
        {("POST", "/repos/octo/repo/issues/4/comments"): [httpx.Response(201, json={"id": 9})]}
    )

    comment = asyncio.run(
        _client(recorder).add_issue_comment(4, "  Could not reproduce this issue.\n")
    )

    assert comment["id"] == 9
    request = recorder.requests[0]
    assert str(request.url) == "https://api.github.com/repos/octo/repo/issues/4/comments"
    assert _body(request) == {"body": "Could not reproduce this issue."}


def test_add_issue_comment_rejects_an_empty_body() -> None:
    recorder = Recorder({})

    with pytest.raises(GitHubAPIError):
        asyncio.run(_client(recorder).add_issue_comment(4, "   "))

    assert recorder.requests == []


def _happy_path(extra: dict[tuple[str, str], list[httpx.Response]]) -> Recorder:
    responses: dict[tuple[str, str], list[httpx.Response]] = {
        ("GET", "/repos/octo/repo/git/ref/heads/main"): [
            httpx.Response(200, json={"object": {"sha": "base-sha"}})
        ],
        ("GET", "/repos/octo/repo/git/commits/base-sha"): [
            httpx.Response(200, json={"tree": {"sha": "base-tree"}})
        ],
        ("POST", "/repos/octo/repo/git/blobs"): [httpx.Response(201, json={"sha": "blob-sha"})],
        ("POST", "/repos/octo/repo/git/trees"): [httpx.Response(201, json={"sha": "new-tree"})],
        ("POST", "/repos/octo/repo/git/commits"): [httpx.Response(201, json={"sha": "commit-sha"})],
        ("POST", "/repos/octo/repo/git/refs"): [httpx.Response(201, json={"ref": "refs/heads/x"})],
        ("POST", "/repos/octo/repo/pulls"): [
            httpx.Response(
                201,
                json={"html_url": "https://github.com/octo/repo/pull/7", "number": 7},
            )
        ],
    }
    responses.update(extra)
    return Recorder(responses)


def test_push_branch_and_open_draft_pr_uses_git_data_api() -> None:
    recorder = _happy_path({})

    result = asyncio.run(
        _client(recorder).push_branch_and_open_draft_pr(
            branch_name="agent/fix-1-abcd1234",
            pr_title="Fix discount",
            pr_body="red -> green",
            files={"src/app.py": "print(1)\n", "tests/test_app.py": "def test(): pass\n"},
        )
    )

    assert result == {
        "pr_url": "https://github.com/octo/repo/pull/7",
        "pr_number": 7,
        "branch": "agent/fix-1-abcd1234",
        "commit": "commit-sha",
    }
    paths = [(request.method, request.url.path) for request in recorder.requests]
    assert paths == [
        ("GET", "/repos/octo/repo/git/ref/heads/main"),
        ("GET", "/repos/octo/repo/git/commits/base-sha"),
        ("POST", "/repos/octo/repo/git/blobs"),
        ("POST", "/repos/octo/repo/git/blobs"),
        ("POST", "/repos/octo/repo/git/trees"),
        ("POST", "/repos/octo/repo/git/commits"),
        ("POST", "/repos/octo/repo/git/refs"),
        ("POST", "/repos/octo/repo/pulls"),
    ]
    tree_body = _body(recorder.requests[4])
    assert tree_body["base_tree"] == "base-tree"
    assert [entry["path"] for entry in tree_body["tree"]] == ["src/app.py", "tests/test_app.py"]
    commit_body = _body(recorder.requests[5])
    assert commit_body["parents"] == ["base-sha"]
    pull_body = _body(recorder.requests[7])
    assert pull_body["draft"] is True
    assert pull_body["head"] == "agent/fix-1-abcd1234"
    assert pull_body["base"] == "main"
    assert pull_body["maintainer_can_modify"] is True


def test_existing_agent_branch_is_force_updated() -> None:
    recorder = _happy_path(
        {
            ("POST", "/repos/octo/repo/git/refs"): [
                httpx.Response(422, json={"message": "Reference already exists"})
            ],
            ("PATCH", "/repos/octo/repo/git/refs/heads/agent/fix-1-abcd1234"): [
                httpx.Response(200, json={"ref": "refs/heads/agent/fix-1-abcd1234"})
            ],
        }
    )

    result = asyncio.run(
        _client(recorder).push_branch_and_open_draft_pr(
            branch_name="agent/fix-1-abcd1234",
            pr_title="Fix discount",
            pr_body="red -> green",
            files={"src/app.py": "print(1)\n"},
        )
    )

    assert result["pr_number"] == 7
    patch = next(request for request in recorder.requests if request.method == "PATCH")
    assert _body(patch) == {"sha": "commit-sha", "force": True}


def test_existing_non_agent_branch_is_rejected() -> None:
    recorder = _happy_path(
        {
            ("POST", "/repos/octo/repo/git/refs"): [
                httpx.Response(422, json={"message": "Reference already exists"})
            ]
        }
    )

    with pytest.raises(GitHubAPIError):
        asyncio.run(
            _client(recorder).push_branch_and_open_draft_pr(
                branch_name="release",
                pr_title="Fix discount",
                pr_body="red -> green",
                files={"src/app.py": "print(1)\n"},
            )
        )

    assert not any(request.method == "PATCH" for request in recorder.requests)


def test_existing_pull_request_is_reused() -> None:
    recorder = _happy_path(
        {
            ("POST", "/repos/octo/repo/pulls"): [
                httpx.Response(
                    422,
                    json={"message": "A pull request already exists for octo:agent/fix-1"},
                )
            ],
            ("GET", "/repos/octo/repo/pulls"): [
                httpx.Response(
                    200,
                    json=[{"html_url": "https://github.com/octo/repo/pull/9", "number": 9}],
                )
            ],
        }
    )

    result = asyncio.run(
        _client(recorder).push_branch_and_open_draft_pr(
            branch_name="agent/fix-1",
            pr_title="Fix discount",
            pr_body="red -> green",
            files={"src/app.py": "print(1)\n"},
        )
    )

    assert result["pr_url"] == "https://github.com/octo/repo/pull/9"


def test_api_error_is_surfaced_without_the_token() -> None:
    recorder = Recorder(
        {("GET", "/repos/octo/repo/issues/4"): [httpx.Response(404, json={"message": "Not Found"})]}
    )

    with pytest.raises(GitHubAPIError) as error:
        asyncio.run(_client(recorder).get_issue(4))

    assert "404" in str(error.value)
    assert "Not Found" in str(error.value)


def test_empty_files_are_rejected_before_any_request() -> None:
    recorder = Recorder({})

    with pytest.raises(GitHubAPIError):
        asyncio.run(
            _client(recorder).push_branch_and_open_draft_pr(
                branch_name="agent/fix-1",
                pr_title="Fix discount",
                pr_body="red -> green",
                files={},
            )
        )

    assert recorder.requests == []


def test_401_refreshes_the_token_once() -> None:
    recorder = Recorder(
        {
            ("GET", "/repos/octo/repo/issues/1"): [
                httpx.Response(401, json={"message": "Bad credentials"}),
                httpx.Response(200, json={"number": 1}),
            ]
        }
    )
    auth = StaticAuth()

    issue = asyncio.run(_client(recorder, auth).get_issue(1))

    assert issue["number"] == 1
    assert auth.invalidations == 1
    assert recorder.requests[1].headers["Authorization"] == "Bearer ghs_test-refreshed"
