"""Local Ollama chat provider (default, no API key required)."""

from __future__ import annotations

import httpx

from symptompilot.llm.base import LLMError


class OllamaClient:
    provider = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    def available(self) -> bool:
        """True when the server responds *and* the requested model is pulled."""

        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 2.5))
            if response.status_code != 200:
                return False
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        if not self.model:
            return True
        installed = {str(item.get("name", "")) for item in data.get("models", [])}
        wanted = self.model.split(":")[0]
        return any(name == self.model or name.split(":")[0] == wanted for name in installed)

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"ollama request failed: {exc}") from exc
        message = (data.get("message") or {}).get("content", "")
        if not message.strip():
            raise LLMError("ollama returned an empty completion")
        return message.strip()
