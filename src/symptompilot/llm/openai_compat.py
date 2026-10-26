"""Any OpenAI-compatible chat endpoint (OpenAI, Azure-style gateways, vLLM, LM Studio)."""

from __future__ import annotations

import httpx

from symptompilot.llm.base import LLMError


class OpenAICompatibleClient:
    provider = "openai"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"openai-compatible/{self.model}"

    def available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"chat completion failed: {exc}") from exc
        choices = data.get("choices") or []
        content = (choices[0].get("message", {}) or {}).get("content") if choices else ""
        if not content or not str(content).strip():
            raise LLMError("provider returned an empty completion")
        return str(content).strip()
