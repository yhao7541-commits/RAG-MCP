"""Tests for LLM answer synthesis over final retrieval results."""

from __future__ import annotations

from typing import Any

from src.core.response.answer_synthesizer import AnswerSynthesizer
from src.core.types import RetrievalResult
from src.libs.llm.base_llm import BaseLLM, ChatResponse, Message


class RecordingLLM(BaseLLM):
    def __init__(self, content: str = "Synthesized answer [1]") -> None:
        self.content = content
        self.messages: list[Message] | None = None

    def chat(
        self,
        messages: list[Message],
        trace: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.validate_messages(messages)
        self.messages = messages
        return ChatResponse(content=self.content, model="test-model")


class FailingLLM(BaseLLM):
    def chat(
        self,
        messages: list[Message],
        trace: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        raise RuntimeError("LLM unavailable")


def _results() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="chunk-1",
            score=0.9,
            text="Create an Azure OpenAI resource before requesting keys.",
            metadata={"source_path": "azure.md"},
        ),
        RetrievalResult(
            chunk_id="chunk-2",
            score=0.8,
            text="Use the endpoint and key in the application settings.",
            metadata={"source_path": "settings.md"},
        ),
    ]


def test_synthesizer_builds_answer_from_numbered_context() -> None:
    llm = RecordingLLM("Use Azure resource credentials in settings. [1][2]")
    synthesizer = AnswerSynthesizer(llm=llm, prompt_template="Q: {query}\n{context}")

    result = synthesizer.synthesize("How do I configure Azure OpenAI?", _results())

    assert result.answer == "Use Azure resource credentials in settings. [1][2]"
    assert result.used is True
    assert result.fallback_reason is None
    assert llm.messages is not None
    prompt = llm.messages[0].content
    assert "How do I configure Azure OpenAI?" in prompt
    assert "[1] chunk_id: chunk-1" in prompt
    assert "[2] chunk_id: chunk-2" in prompt


def test_synthesizer_falls_back_when_llm_fails() -> None:
    synthesizer = AnswerSynthesizer(llm=FailingLLM(), prompt_template="Q: {query}\n{context}")

    result = synthesizer.synthesize("query", _results())

    assert result.answer is None
    assert result.used is False
    assert "LLM unavailable" in result.fallback_reason


def test_synthesizer_falls_back_on_empty_llm_answer() -> None:
    synthesizer = AnswerSynthesizer(llm=RecordingLLM("   "), prompt_template="Q: {query}\n{context}")

    result = synthesizer.synthesize("query", _results())

    assert result.answer is None
    assert result.used is False
    assert result.fallback_reason == "LLM returned an empty answer"
