"""The LLM wrapper must fail loudly and never reuse an answer for another prompt."""
import asyncio
from typing import Any

import pytest

from pipeline import llm
from pipeline.llm import LLMWrapper, PromptCache


class FakeGenAI:
    """Stands in for the google.generativeai module."""

    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def configure(self, **_: Any) -> None:
        return None

    def GenerativeModel(self, model_name: str) -> "FakeGenAI":
        return self

    def generate_content(self, prompt: str) -> Any:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return type("Response", (), {"text": self.reply})()


def ask(wrapper: LLMWrapper, prompt: str) -> str:
    return asyncio.run(wrapper.ask(prompt, "title", "body"))


def test_missing_key_raises_instead_of_answering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "genai", FakeGenAI("unused"))
    with pytest.raises(RuntimeError, match="API key is not configured"):
        ask(LLMWrapper(api_key=""), "diagnose the root cause")


def test_missing_sdk_raises_instead_of_answering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "genai", None)
    with pytest.raises(RuntimeError, match="not installed"):
        ask(LLMWrapper(api_key="k"), "diagnose the root cause")


def test_provider_error_is_raised_not_replaced_by_a_made_up_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "genai", FakeGenAI(ValueError("invalid api key")))
    with pytest.raises(ValueError, match="invalid api key"):
        ask(LLMWrapper(api_key="k"), "write a patch to fix it")


def test_empty_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "genai", FakeGenAI(""))
    with pytest.raises(RuntimeError, match="empty response"):
        ask(LLMWrapper(api_key="k"), "prompt")


def test_two_prompts_for_one_issue_do_not_share_a_cached_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeGenAI("answer")
    monkeypatch.setattr(llm, "genai", fake)
    wrapper = LLMWrapper(api_key="k", cache=PromptCache())

    ask(wrapper, "diagnose")
    ask(wrapper, "fix")
    ask(wrapper, "diagnose")  # served from the cache

    assert fake.prompts == ["diagnose", "fix"]


def test_rehearsed_answer_is_served_for_its_exact_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGenAI("live answer")
    monkeypatch.setattr(llm, "genai", fake)
    wrapper = LLMWrapper(api_key="k", cache=PromptCache())
    wrapper.cache_rehearsed_issues(
        [{"title": "title", "body": "body", "prompt": "diagnose", "expected_response": "rehearsed"}]
    )

    assert ask(wrapper, "diagnose") == "rehearsed"
    assert fake.prompts == []
