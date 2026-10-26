"""Provider resolution.

``auto`` prefers a local Ollama instance, then an OpenAI-compatible endpoint with
a configured key, then no LLM at all.
"""

from __future__ import annotations

from functools import lru_cache

from symptompilot.config import Settings
from symptompilot.llm.base import LLMClient, LLMError
from symptompilot.llm.ollama import OllamaClient
from symptompilot.llm.openai_compat import OpenAICompatibleClient

__all__ = [
    "LLMClient",
    "LLMError",
    "OllamaClient",
    "OpenAICompatibleClient",
    "resolve_client",
]


@lru_cache(maxsize=8)
def _ollama_ready(base_url: str, model: str, timeout: float) -> bool:
    return OllamaClient(base_url, model=model, timeout=timeout).available()


def resolve_client(settings: Settings) -> LLMClient | None:
    provider = (settings.llm_provider or "auto").lower()
    ollama = OllamaClient(settings.ollama_url, settings.ollama_model, settings.llm_timeout)
    openai = OpenAICompatibleClient(
        settings.openai_base_url,
        settings.openai_api_key,
        settings.openai_model,
        settings.llm_timeout,
    )

    if provider == "none":
        return None
    if provider == "ollama":
        return ollama
    if provider in {"openai", "openai-compatible"}:
        return openai if openai.available() else None
    if provider != "auto":
        raise ValueError(f"unknown llm provider: {settings.llm_provider}")
    if _ollama_ready(settings.ollama_url, settings.ollama_model, settings.llm_timeout):
        return ollama
    return openai if openai.available() else None
