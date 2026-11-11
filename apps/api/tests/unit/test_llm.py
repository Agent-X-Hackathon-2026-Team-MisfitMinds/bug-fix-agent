"""The Gemini REST wrapper must parse real payloads and never fake an answer."""
import asyncio
import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import pytest

from pipeline.llm import LLMWrapper, PromptCache, RateLimitError, parse_fallback_models


def gemini_reply(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}}]},
    )


def ask(wrapper: LLMWrapper, prompt: str = "diagnose") -> str:
    return asyncio.run(wrapper.ask(prompt, "title", "body"))


def make_wrapper(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "test-key",
    fallback_models: Sequence[str] = (),
) -> LLMWrapper:
    return LLMWrapper(
        api_key=api_key,
        model_name="test-model",
        fallback_models=list(fallback_models),
        transport=httpx.MockTransport(handler),
        cache=PromptCache(),
    )


def test_missing_key_raises_instead_of_answering() -> None:
    wrapper = LLMWrapper(api_key="", model_name="test-model")
    with pytest.raises(RuntimeError, match="API key is not configured"):
        ask(wrapper)


def test_unsupported_provider_raises() -> None:
    wrapper = LLMWrapper(provider="groq", api_key="k", model_name="test-model")
    with pytest.raises(RuntimeError, match="Unsupported LLM provider"):
        ask(wrapper)


def test_request_uses_the_rest_endpoint_and_returns_text() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return gemini_reply("the cause is an off-by-one")

    wrapper = make_wrapper(handler)
    assert ask(wrapper, "find the bug") == "the cause is an off-by-one"

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith("/v1beta/models/test-model:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key"
    body = json.loads(request.content)
    assert body["contents"][0]["parts"][0]["text"] == "find the bug"
    assert body["generationConfig"]["temperature"] == 0.1


def test_cached_answer_is_used_for_the_exact_prompt_only() -> None:
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = str(body["contents"][0]["parts"][0]["text"])
        prompts.append(prompt)
        return gemini_reply(f"answer:{prompt}")

    wrapper = make_wrapper(handler)
    assert ask(wrapper, "diagnose") == "answer:diagnose"
    assert ask(wrapper, "diagnose") == "answer:diagnose"
    assert ask(wrapper, "fix") == "answer:fix"
    assert prompts == ["diagnose", "fix"]


def test_ask_json_accepts_a_fenced_object_and_requests_json_mode() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return gemini_reply('```json\n{"root_cause": "boundary check"}\n```')

    wrapper = make_wrapper(handler)
    result = asyncio.run(wrapper.ask_json("diagnose", "title", "body"))

    assert result == {"root_cause": "boundary check"}
    assert bodies[0]["generationConfig"]["responseMimeType"] == "application/json"


def test_ask_code_extracts_a_python_fence() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return gemini_reply(
            "Here is the test:\n```python\n"
            "from app import validate_age\n\n"
            "def test_accepts_65():\n"
            "    assert validate_age(65) is True\n"
            "```\n"
        )

    wrapper = make_wrapper(handler)
    code = asyncio.run(wrapper.ask_code("write a test", "title", "body"))

    assert code.startswith("from app import validate_age")
    assert "def test_accepts_65" in code


def test_ask_code_rejects_a_response_without_a_test() -> None:
    wrapper = make_wrapper(lambda _: gemini_reply("I cannot write tests."))
    with pytest.raises(RuntimeError, match="did not return a pytest file"):
        asyncio.run(wrapper.ask_code("write a test", "title", "body"))


def test_ask_json_rejects_invalid_json() -> None:
    wrapper = make_wrapper(lambda _: gemini_reply("not json"))
    with pytest.raises(RuntimeError, match="valid JSON"):
        asyncio.run(wrapper.ask_json("diagnose", "title", "body"))


def test_429_becomes_a_rate_limit_error_with_retry_after() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "7"},
            json={"error": {"message": "quota exceeded"}},
        )

    wrapper = make_wrapper(handler)
    with pytest.raises(RateLimitError) as caught:
        ask(wrapper)
    assert caught.value.retry_after == 7


def test_provider_error_is_raised_with_the_provider_message() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "model is invalid"}})

    wrapper = make_wrapper(handler)
    with pytest.raises(RuntimeError, match="model is invalid"):
        ask(wrapper)


def test_empty_response_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    wrapper = make_wrapper(handler)
    with pytest.raises(RuntimeError, match="empty response"):
        ask(wrapper)


def test_blocked_prompt_reports_the_reason() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"promptFeedback": {"blockReason": "SAFETY"}},
        )

    wrapper = make_wrapper(handler)
    with pytest.raises(RuntimeError, match="SAFETY"):
        ask(wrapper)


def test_rehearsed_answer_is_served_for_its_exact_prompt() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return gemini_reply("live answer")

    wrapper = make_wrapper(handler)
    wrapper.cache_rehearsed_issues(
        [{"title": "title", "body": "body", "prompt": "diagnose", "expected_response": "rehearsed"}]
    )

    assert ask(wrapper, "diagnose") == "rehearsed"
    assert calls == []


def test_fallback_model_setting_is_parsed_as_csv() -> None:
    assert parse_fallback_models("gemini-3.5-flash, gemini-2.5-flash") == [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
    ]
    assert parse_fallback_models("") == []
    assert parse_fallback_models(" , ") == []


def test_healthy_first_model_never_touches_fallbacks() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return gemini_reply("primary answer")

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    assert ask(wrapper) == "primary answer"
    assert paths == ["/v1beta/models/test-model:generateContent"]


def test_5xx_falls_over_to_the_next_model() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("test-model:generateContent"):
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return gemini_reply("recovered")

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    assert ask(wrapper) == "recovered"
    assert paths == [
        "/v1beta/models/test-model:generateContent",
        "/v1beta/models/backup-model:generateContent",
    ]


def test_timeout_falls_over_to_the_next_model() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("test-model:generateContent"):
            raise httpx.ConnectTimeout("model hung", request=request)
        return gemini_reply("recovered after timeout")

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    assert ask(wrapper) == "recovered after timeout"
    assert paths == [
        "/v1beta/models/test-model:generateContent",
        "/v1beta/models/backup-model:generateContent",
    ]


def test_404_falls_over_to_the_next_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("test-model:generateContent"):
            return httpx.Response(404, json={"error": {"message": "model not found"}})
        return gemini_reply("fallback knows the answer")

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    assert ask(wrapper) == "fallback knows the answer"


def test_429_falls_over_to_a_model_with_quota_left() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("test-model:generateContent"):
            return httpx.Response(
                429, headers={"Retry-After": "3"}, json={"error": {"message": "quota"}}
            )
        return gemini_reply("quota recovered")

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    assert ask(wrapper) == "quota recovered"


def test_rate_limit_on_every_model_raises_rate_limit_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, headers={"Retry-After": "9"}, json={"error": {"message": "quota"}}
        )

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    with pytest.raises(RateLimitError) as caught:
        ask(wrapper)
    assert caught.value.retry_after == 9


def test_400_fails_fast_without_trying_fallbacks() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(400, json={"error": {"message": "model is invalid"}})

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    with pytest.raises(RuntimeError, match="model is invalid"):
        ask(wrapper)
    assert paths == ["/v1beta/models/test-model:generateContent"]


def test_403_fails_fast_without_trying_fallbacks() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(403, json={"error": {"message": "permission denied"}})

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    with pytest.raises(RuntimeError, match="permission denied"):
        ask(wrapper)
    assert paths == ["/v1beta/models/test-model:generateContent"]


def test_all_models_failing_raises_the_last_error() -> None:
    statuses = iter((503, 500))

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), json={"error": {"message": "down"}})

    wrapper = make_wrapper(handler, fallback_models=["backup-model"])

    with pytest.raises(RuntimeError, match="HTTP 500"):
        ask(wrapper)
