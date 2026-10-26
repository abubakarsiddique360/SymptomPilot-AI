"""LLM provider abstraction.

Providers are interchangeable and entirely optional — the agent falls back to a
deterministic extractive composer when no provider is reachable.
"""

from __future__ import annotations

from typing import Protocol


class LLMError(RuntimeError):
    """Raised when a provider is reachable but the completion failed."""


class LLMClient(Protocol):
    provider: str
    model: str

    @property
    def name(self) -> str: ...

    def available(self) -> bool: ...

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> str: ...
