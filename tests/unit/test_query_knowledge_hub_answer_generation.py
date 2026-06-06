"""Tests for answer generation in query_knowledge_hub."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.response.answer_synthesizer import AnswerSynthesisResult
from src.core.types import RetrievalResult
from src.mcp_server.tools.query_knowledge_hub import QueryKnowledgeHubTool


class FakeSynthesizer:
    def __init__(self) -> None:
        self.call_count = 0
        self.last_query = None
        self.last_results = None

    def synthesize(self, query, results, trace=None):
        self.call_count += 1
        self.last_query = query
        self.last_results = results
        return AnswerSynthesisResult(answer="Generated answer [1]", used=True)


class QueryToolHarness(QueryKnowledgeHubTool):
    def _ensure_initialized(self, collection: str) -> None:
        self._initialized = True
        self._current_collection = collection

    def _perform_search(self, query: str, top_k: int, trace=None):
        return [
            RetrievalResult(
                chunk_id="chunk-1",
                score=0.9,
                text="Retrieved context",
                metadata={"source_path": "doc.md"},
            )
        ]


def _settings(enabled: bool = True):
    return SimpleNamespace(
        answer_generation=SimpleNamespace(
            enabled=enabled,
            prompt_path="./config/prompts/answer_generation.txt",
            max_context_chars=6000,
        )
    )


@pytest.mark.asyncio
async def test_query_tool_includes_generated_answer_when_enabled() -> None:
    synthesizer = FakeSynthesizer()
    tool = QueryToolHarness(
        settings=_settings(enabled=True),
        answer_synthesizer=synthesizer,
    )

    with patch("src.mcp_server.tools.query_knowledge_hub.TraceCollector.collect"):
        response = await tool.execute(query="How to configure Azure?", top_k=1)

    assert synthesizer.call_count == 1
    assert synthesizer.last_query == "How to configure Azure?"
    assert synthesizer.last_results[0].chunk_id == "chunk-1"
    assert "## 大模型整理结果" in response.content
    assert "Generated answer [1]" in response.content
    assert "## 召回结果" in response.content
    assert response.metadata["answer_generation"]["used"] is True


@pytest.mark.asyncio
async def test_query_tool_skips_generated_answer_when_disabled() -> None:
    synthesizer = FakeSynthesizer()
    tool = QueryToolHarness(
        settings=_settings(enabled=False),
        answer_synthesizer=synthesizer,
    )

    with patch("src.mcp_server.tools.query_knowledge_hub.TraceCollector.collect"):
        response = await tool.execute(query="How to configure Azure?", top_k=1)

    assert synthesizer.call_count == 0
    assert "## 大模型整理结果" not in response.content
    assert "answer_generation" not in response.metadata
