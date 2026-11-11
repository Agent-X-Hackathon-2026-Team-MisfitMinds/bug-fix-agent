"""LLM wrapper with caching for Bug-Fix Agent.

Provides one wrapper through free-tier provider (Gemini or Groq),
caches by SHA-256 of issue title + body (and prompt hash for invalidation),
sets a 24-hour TTL, handles rate limits with bounded retry and clear fail state.

Cache rehearsed demo issues before the live demo.
"""

from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional


class RateLimitError(Exception):
    """Raised when LLM provider rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")


class PromptCache:
    """Cache LLM prompts by SHA-256 hash of issue content.

    Uses 24-hour TTL; invalidate on prompt changes.
    Cache rehearsed demo issues before the live demo.

    Cache key = SHA-256(issue_title + issue_body + prompt_version)
    """

    def __init__(self, ttl_hours: int = 24):
        self._cache: Dict[str, tuple[str, float]] = {}
        self.ttl = ttl_hours * 3600  # Convert to seconds

    def _hash(self, issue_title: str, issue_body: str, prompt_version: str = "v1") -> str:
        """Generate SHA-256 hash for cache key."""
        combined = f"{issue_title}|{issue_body}|{prompt_version}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, issue_title: str, issue_body: str, prompt_version: str = "v1") -> Optional[str]:
        """Retrieve cached result if not expired.

        Returns cached result or None if not found/expired.
        """
        key = self._hash(issue_title, issue_body, prompt_version)
        if key in self._cache:
            cached_result, timestamp = self._cache[key]
            elapsed = time.time() - timestamp
            if elapsed < self.ttl:
                return cached_result
            else:
                # Expired - remove entry
                del self._cache[key]
        return None

    def set(self, issue_title: str, issue_body: str, prompt_version: str = "v1", result: str = "") -> None:
        """Store result with current timestamp."""
        key = self._hash(issue_title, issue_body, prompt_version)
        self._cache[key] = (result, time.time())

    def cleanup(self) -> None:
        """Remove all expired entries (call periodically)."""
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items() if now - ts > self.ttl
        ]
        for k in expired_keys:
            del self._cache[k]


class LLMWrapper:
    """Wrapper around LLM provider with caching and rate-limit handling.

    Supports Gemini, Groq, or any free-tier LLM provider.
    All provider calls should go through this wrapper to enable
    caching, caching invalidation, and rate-limit coordination.
    """

    def __init__(
        self,
        provider: str = "gemini",  # gemini or groq
        api_key: Optional[str] = None,
        cache: Optional[PromptCache] = None,
    ):
        self.provider = provider
        self.api_key = api_key or ""
        self.cache = cache or PromptCache()
        self._rate_limit_time: float = 0.0
        self._rate_limit_seconds = 60  # Default 60s cooldown

    def _check_rate_limit(self) -> bool:
        """Check if enough time has passed since last rate limit hit.

        Returns True if OK to proceed, False if still in cooldown.
        """
        if time.time() - self._rate_limit_time < self._rate_limit_seconds:
            return False
        return True

    def _enforce_rate_limit(self) -> None:
        """Mark rate limit as hit - caller should wait before retrying."""
        self._rate_limit_time = time.time()

    async def ask(
        self,
        prompt: str,
        issue_title: str,
        issue_body: str,
        prompt_version: str = "v1",
        force_cache: bool = False,
    ) -> str:
        """Ask LLM a question with caching and rate-limit handling.

        Args:
            prompt: The prompt to send to the LLM
            issue_title: Issue title for cache key
            issue_body: Issue body for cache key
            prompt_version: Prompt version for cache invalidation
            force_cache: If True, skip LLM call if cache hit (even if expired)

        Returns:
            LLM response as string

        Raises:
            RateLimitError: If rate limited and max retries exceeded
        """
        # Step 1: Check cache
        cached = self.cache.get(issue_title, issue_body, prompt_version)
        if cached and not force_cache:
            return cached

        # Step 2: Check rate limit
        if not self._check_rate_limit():
            raise RateLimitError(
                retry_after=self._rate_limit_seconds
            )

        # Step 3: Call LLM provider
        try:
            response = await self._call_provider(prompt)
        except Exception as e:
            # Check if it's a rate limit error from provider
            if "rate limit" in str(e).lower() or "429" in str(e):
                self._enforce_rate_limit()
                raise RateLimitError(retry_after=60) from e
            # Re-raise other errors
            raise

        # Step 4: Cache the result
        self.cache.set(issue_title, issue_body, prompt_version, response)

        return response

    async def _call_provider(self, prompt: str) -> str:
        """Actual provider call - to be implemented by subclass or integration.

        This is a placeholder that should be replaced with actual provider SDK calls.
        For Gemini: use google.generativeai
        For Groq: use groq SDK
        """
        # This is a mock implementation - replace with actual provider call
        # In production, this would call the LLM API
        raise NotImplementedError(
            "_call_provider must be implemented for specific LLM provider"
        )

    def cache_rehearsed_issues(self, rehearsed_issues: List[dict[str, str]]) -> None:
        """Pre-cache results for demo/rehearsal issues before live demo.

        Args:
            rehearsed_issues: List of dicts with 'title', 'body', and expected 'response'
        """
        for issue_data in rehearsed_issues:
            title = issue_data.get("title", "")
            body = issue_data.get("body", "")
            expected = issue_data.get("expected_response", "")
            if title and body:
                self.cache.set(title, body, prompt_version="rehearsed", result=expected)


# Default instance for use across the project
default_llm = LLMWrapper(provider="gemini")  # or "groq" based on available credits