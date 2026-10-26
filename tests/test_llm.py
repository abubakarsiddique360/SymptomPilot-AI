from __future__ import annotations

import httpx
import pytest

from symptompilot.config import Settings
from symptompilot.llm import resolve_client
from symptompilot.llm.base import LLMError
from symptompilot.llm.ollama import OllamaClient
from symptompilot.llm.openai_compat import OpenAICompatibleClient


class _Response:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)  # type: ignore[arg-type]


def test_ollama_available_requires_model(monkeypatch) -> None:
    client = OllamaClient("http://localhost:11434", "llama3.2")
    monkeypatch.setattr(
        "symptompilot.llm.ollama.httpx.get",
        lambda *a, **k: _Response(payload={"models": [{"name": "llama3.2:latest"}]}),
    )
    assert client.available() is True

    monkeypatch.setattr(
        "symptompilot.llm.ollama.httpx.get",
        lambda *a, **k: _Response(payload={"models": [{"name": "mistral:latest"}]}),
    )
    assert client.available() is False


def test_ollama_available_handles_connection_errors(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise httpx.ConnectError("no server")

    monkeypatch.setattr("symptompilot.llm.ollama.httpx.get", boom)
    assert OllamaClient("http://localhost:11434", "llama3.2").available() is False


def test_ollama_complete_returns_content(monkeypatch) -> None:
    monkeypatch.setattr(
        "symptompilot.llm.ollama.httpx.post",
        lambda *a, **k: _Response(payload={"message": {"content": "  answer text  "}}),
    )
    result = OllamaClient("http://localhost:11434", "llama3.2").complete("sys", "user")
    assert result == "answer text"


def test_ollama_raises_on_empty_completion(monkeypatch) -> None:
    monkeypatch.setattr(
        "symptompilot.llm.ollama.httpx.post",
        lambda *a, **k: _Response(payload={"message": {"content": ""}}),
    )
    with pytest.raises(LLMError):
        OllamaClient("http://localhost:11434", "llama3.2").complete("sys", "user")


def test_openai_compatible_parses_choice(monkeypatch) -> None:
    monkeypatch.setattr(
        "symptompilot.llm.openai_compat.httpx.post",
        lambda *a, **k: _Response(payload={"choices": [{"message": {"content": "hello"}}]}),
    )
    client = OpenAICompatibleClient("https://example.test/v1", "key", "model")
    assert client.complete("sys", "user") == "hello"
    assert client.available() is True


def test_openai_compatible_raises_without_choices(monkeypatch) -> None:
    monkeypatch.setattr(
        "symptompilot.llm.openai_compat.httpx.post",
        lambda *a, **k: _Response(payload={"choices": []}),
    )
    with pytest.raises(LLMError):
        OpenAICompatibleClient("https://example.test/v1", "key", "model").complete("s", "u")


def test_resolve_client_none_provider() -> None:
    assert resolve_client(Settings(llm_provider="none")) is None


def test_resolve_client_openai_requires_key() -> None:
    assert resolve_client(Settings(llm_provider="openai", openai_api_key="")) is None
    client = resolve_client(Settings(llm_provider="openai", openai_api_key="k"))
    assert client is not None and client.provider == "openai"


def test_resolve_client_auto_without_any_backend(monkeypatch) -> None:
    monkeypatch.setattr("symptompilot.llm._ollama_ready", lambda *a, **k: False)
    assert resolve_client(Settings(llm_provider="auto", openai_api_key="")) is None


def test_resolve_client_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        resolve_client(Settings(llm_provider="magic"))
