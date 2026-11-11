"""Async Gemini REST wrapper with prompt caching and no fabricated answers.

The provider is called over HTTPS with the existing ``httpx`` dependency; there
is no LLM SDK to install. Responses are cached by a SHA-256 of the issue text
and the exact prompt, so two different nodes can never share an answer.

When the primary model is overloaded (5xx), unknown (404), rate limited (429)
or unreachable (timeout), the wrapper fails over to GEMINI_FALLBACK_MODELS.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, cast

import httpx

from config import get_settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_CODE_FENCE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_CODE_START = ("import ", "from ", "@", "def ", '"""', "'''", "#")


class RateLimitError(Exception):
    """Raised when the LLM provider rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")


class PromptCache:
    """Cache LLM prompts by SHA-256 hash of issue content, version and prompt."""

    def __init__(self, ttl_hours: int = 24) -> None:
        self._cache: dict[str, tuple[str, float]] = {}
        self.ttl = ttl_hours * 3600

    def _hash(
        self, issue_title: str, issue_body: str, prompt_version: str = "v1", prompt: str = ""
    ) -> str:
        combined = f"{issue_title}|{issue_body}|{prompt_version}|{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(
        self, issue_title: str, issue_body: str, prompt_version: str = "v1", prompt: str = ""
    ) -> str | None:
        key = self._hash(issue_title, issue_body, prompt_version, prompt)
        entry = self._cache.get(key)
        if entry is None:
            return None
        result, timestamp = entry
        if time.time() - timestamp < self.ttl:
            return result
        del self._cache[key]
        return None

    def set(
        self,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        result: str = "",
        prompt: str = "",
    ) -> None:
        key = self._hash(issue_title, issue_body, prompt_version, prompt)
        self._cache[key] = (result, time.time())

    def cleanup(self) -> None:
        now = time.time()
        expired = [key for key, (_, stamp) in self._cache.items() if now - stamp > self.ttl]
        for key in expired:
            del self._cache[key]


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, accepting a fenced or lightly wrapped response."""
    candidate = text.strip()
    fenced = _JSON_FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        value: Any = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("LLM did not return valid JSON") from None
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("LLM returned JSON that is not an object")
    return cast(dict[str, Any], value)


def extract_code(text: str) -> str:
    """Return one complete pytest file from a fenced or raw response."""
    blocks = [match.group(1).strip() for match in _CODE_FENCE.finditer(text)]
    for block in blocks:
        if "def test_" in block:
            return block
    candidate = text.strip()
    lines = candidate.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(_CODE_START):
            candidate = "\n".join(lines[index:]).strip()
            break
    if "def test_" not in candidate:
        raise RuntimeError("LLM did not return a pytest file")
    return candidate


def parse_fallback_models(raw: str) -> list[str]:
    """Split a comma separated GEMINI_FALLBACK_MODELS value into model names."""
    return [model.strip() for model in raw.split(",") if model.strip()]


class LLMWrapper:
    """Gemini client with caching, JSON/code adapters, failover and bounded failure."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str | None = None,
        cache: PromptCache | None = None,
        model_name: str | None = None,
        fallback_models: list[str] | None = None,
        base_url: str = GEMINI_BASE_URL,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = provider
        self.api_key = (
            api_key if api_key is not None else settings.gemini_api_key.get_secret_value()
        )
        self.model_name = model_name or settings.gemini_model
        self.fallback_models = (
            list(fallback_models)
            if fallback_models is not None
            else parse_fallback_models(settings.gemini_fallback_models)
        )
        self.cache = cache or PromptCache()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._rate_limit_time = 0.0
        self._rate_limit_seconds = 60

    def _check_rate_limit(self) -> bool:
        return time.time() - self._rate_limit_time >= self._rate_limit_seconds

    def _enforce_rate_limit(self) -> None:
        self._rate_limit_time = time.time()

    async def ask(
        self,
        prompt: str,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        force_cache: bool = False,
        node_name: str | None = None,
    ) -> str:
        """Ask Gemini for plain text, using the prompt cache when possible."""
        del node_name  # kept for existing call sites
        return await self._ask(
            prompt,
            issue_title,
            issue_body,
            prompt_version=prompt_version,
            force_cache=force_cache,
            response_json=False,
        )

    async def ask_json(
        self,
        prompt: str,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        force_cache: bool = False,
    ) -> dict[str, Any]:
        """Ask Gemini for a JSON object and validate that it is one."""
        text = await self._ask(
            prompt,
            issue_title,
            issue_body,
            prompt_version=prompt_version,
            force_cache=force_cache,
            response_json=True,
        )
        return parse_json_object(text)

    async def ask_code(
        self,
        prompt: str,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        force_cache: bool = False,
    ) -> str:
        """Ask Gemini for a pytest file and extract the code block."""
        text = await self._ask(
            prompt,
            issue_title,
            issue_body,
            prompt_version=prompt_version,
            force_cache=force_cache,
            response_json=False,
        )
        return extract_code(text)

    async def _ask(
        self,
        prompt: str,
        issue_title: str,
        issue_body: str,
        *,
        prompt_version: str,
        force_cache: bool,
        response_json: bool,
    ) -> str:
        cached = self.cache.get(issue_title, issue_body, prompt_version, prompt)
        if cached is not None and not force_cache:
            return cached
        if not self._check_rate_limit():
            raise RateLimitError(retry_after=self._rate_limit_seconds)
        try:
            response = await self._call_provider(prompt, response_json=response_json)
        except RateLimitError:
            self._enforce_rate_limit()
            raise
        self.cache.set(issue_title, issue_body, prompt_version, response, prompt)
        return response

    async def _call_provider(self, prompt: str, *, response_json: bool) -> str:
        if self.provider != "gemini":
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")
        if not self.api_key:
            raise RuntimeError("LLM API key is not configured (GEMINI_API_KEY)")
        if not self.model_name:
            raise RuntimeError("GEMINI_MODEL is not configured")

        generation_config: dict[str, Any] = {
            "temperature": 0.1,
            # Reasoning models spend output tokens on thinking; 4096 truncated answers.
            "maxOutputTokens": 8192,
        }
        if response_json:
            generation_config["responseMimeType"] = "application/json"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        # Try the configured model first, then fall back when it is unavailable.
        last_error: Exception | None = None
        for model in [self.model_name, *self.fallback_models]:
            url = f"{self._base_url}/v1beta/models/{model}:generateContent"
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=self._timeout
                ) as client:
                    response = await client.post(
                        url,
                        headers={"x-goog-api-key": self.api_key},
                        json=body,
                    )
            except httpx.HTTPError as exc:
                # Timeout or connection failure: this model is unreachable right now.
                last_error = RuntimeError(f"Gemini request failed: {exc}")
                continue

            if response.status_code == 429:
                # Quotas are per model, so another candidate may still have headroom.
                last_error = RateLimitError(retry_after=_retry_after(response))
                continue
            if response.status_code in (400, 401, 403):
                # Bad request or auth failure: every model would fail the same way.
                raise RuntimeError(
                    "Gemini request failed with HTTP "
                    f"{response.status_code}: {_error_detail(response)}"
                )
            if response.status_code >= 400:
                # 404 (unknown model) and 5xx (overloaded) are worth failing over.
                last_error = RuntimeError(
                    "Gemini request failed with HTTP "
                    f"{response.status_code} for model {model!r}: "
                    f"{_error_detail(response)}"
                )
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError("Gemini returned a non-JSON response") from exc
            if not isinstance(payload, dict):
                raise RuntimeError("Gemini returned an unexpected response")
            payload = cast(dict[str, Any], payload)

            candidates = payload.get("candidates")
            if isinstance(candidates, list) and candidates:
                candidate = candidates[0]
                if isinstance(candidate, dict):
                    content = candidate.get("content")
                    if isinstance(content, dict):
                        parts = content.get("parts")
                        if isinstance(parts, list):
                            texts: list[str] = []
                            for part in parts:
                                if not isinstance(part, dict):
                                    continue
                                value = part.get("text")
                                if isinstance(value, str):
                                    texts.append(value)
                            text = "".join(texts)
                            if text.strip():
                                return text
            feedback = payload.get("promptFeedback")
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                raise RuntimeError(f"Gemini blocked the prompt: {feedback['blockReason']}")
            reason = ""
            if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
                reason = str(candidates[0].get("finishReason") or "")
            raise RuntimeError(
                "LLM returned an empty response" + (f" (finishReason: {reason})" if reason else "")
            )

        if last_error is None:  # pragma: no cover - the first candidate always exists
            raise RuntimeError("no Gemini model was tried")
        raise last_error

    def cache_rehearsed_issues(self, rehearsed_issues: list[dict[str, str]]) -> None:
        """Pre-cache exact prompt/response pairs for a rehearsal."""
        for issue_data in rehearsed_issues:
            title = issue_data.get("title", "")
            body = issue_data.get("body", "")
            prompt = issue_data.get("prompt", "")
            expected = issue_data.get("expected_response", "")
            if title and body and prompt:
                self.cache.set(title, body, result=expected, prompt=prompt)


def _retry_after(response: httpx.Response) -> int:
    value = response.headers.get("Retry-After", "")
    try:
        return max(1, int(value))
    except ValueError:
        return 60


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300] or "request failed"
    if not isinstance(payload, dict):
        return "request failed"
    message = payload.get("error")
    if isinstance(message, dict):
        detail = message.get("message")
        if isinstance(detail, str):
            return detail
    return "request failed"


default_llm = LLMWrapper()
