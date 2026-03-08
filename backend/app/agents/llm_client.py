from __future__ import annotations

import json
from typing import Any, Protocol

import httpx


class LLMError(Exception):
    """Raised for failures in the LLM integration layer."""


class LLMClient(Protocol):
    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...


class OpenAICompatibleJSONClient:
    """
    Works with any OpenAI-compatible chat completions endpoint
    (OpenAI, OpenRouter, Ollama's OpenAI API shim).
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str = "openai-compatible",
        default_headers: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._chat_endpoint = self._resolve_chat_endpoint(self._base_url)
        self._api_key = api_key
        self.provider = provider
        self._headers = default_headers or {}
        self._timeout_seconds = timeout_seconds
        self._model = model

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **self._headers}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = httpx.post(
                self._chat_endpoint,
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc

        try:
            content = data["choices"][0]["message"]["content"] or "{}"
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Malformed model response: {data}") from exc
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("LLM response was not a JSON object")
            return parsed
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Failed to parse model JSON output: {content}") from exc

    def _resolve_chat_endpoint(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"
