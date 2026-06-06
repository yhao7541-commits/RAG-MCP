"""LLM answer synthesis from final retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.settings import resolve_path
from src.core.types import RetrievalResult
from src.libs.llm.base_llm import BaseLLM, Message
from src.libs.llm.llm_factory import LLMFactory
from src.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AnswerSynthesisResult:
    answer: str | None
    used: bool
    fallback_reason: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {"used": self.used}
        if self.fallback_reason:
            metadata["fallback_reason"] = self.fallback_reason
        return metadata


class AnswerSynthesizer:
    """Generate a concise answer from already-ranked retrieval results."""

    def __init__(
        self,
        settings: Any | None = None,
        llm: BaseLLM | None = None,
        prompt_path: str | None = None,
        prompt_template: str | None = None,
        max_context_chars: int = 6000,
    ) -> None:
        self.settings = settings
        self._llm = llm
        self.prompt_path = prompt_path or "./config/prompts/answer_generation.txt"
        self._prompt_template = prompt_template
        self.max_context_chars = max_context_chars

    @property
    def llm(self) -> BaseLLM:
        if self._llm is None:
            if self.settings is None:
                raise RuntimeError("settings are required to initialize the LLM")
            self._llm = LLMFactory.create(self.settings)
        return self._llm

    def synthesize(
        self,
        query: str,
        results: list[RetrievalResult],
        trace: Any | None = None,
    ) -> AnswerSynthesisResult:
        if not results:
            return AnswerSynthesisResult(
                answer=None,
                used=False,
                fallback_reason="No retrieval results to synthesize",
            )

        try:
            prompt = self._build_prompt(query, results)
            response = self.llm.chat([Message(role="user", content=prompt)], trace=trace)
            answer = response.content.strip()
            if not answer:
                return AnswerSynthesisResult(
                    answer=None,
                    used=False,
                    fallback_reason="LLM returned an empty answer",
                )
            return AnswerSynthesisResult(answer=answer, used=True)
        except Exception as exc:
            logger.warning("Answer synthesis failed: %s", exc)
            return AnswerSynthesisResult(
                answer=None,
                used=False,
                fallback_reason=str(exc),
            )

    def _build_prompt(self, query: str, results: list[RetrievalResult]) -> str:
        template = self._load_prompt_template()
        context = self._format_context(results)
        return template.replace("{query}", query).replace("{context}", context)

    def _load_prompt_template(self) -> str:
        if self._prompt_template is not None:
            return self._prompt_template

        prompt_file = Path(self.prompt_path)
        if not prompt_file.is_absolute():
            prompt_file = resolve_path(prompt_file)
        self._prompt_template = prompt_file.read_text(encoding="utf-8")
        return self._prompt_template

    def _format_context(self, results: list[RetrievalResult]) -> str:
        parts: list[str] = []
        used_chars = 0
        for index, result in enumerate(results, start=1):
            source = result.metadata.get("source_path", result.metadata.get("source", "unknown"))
            page = result.metadata.get("page", result.metadata.get("page_num"))
            header = f"[{index}] chunk_id: {result.chunk_id}\nsource: {source}"
            if page is not None:
                header += f"\npage: {page}"
            block = f"{header}\ntext: {' '.join(result.text.split())}\n"
            remaining = self.max_context_chars - used_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[:remaining].rstrip()
            parts.append(block)
            used_chars += len(block)
        return "\n".join(parts)
