from __future__ import annotations

import json
from typing import Any, Protocol

import httpx


class LLMError(Exception):
    """Raised for failures in the LLM integration layer."""


class LLMClient(Protocol):
    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...

    async def async_generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...

    async def async_stream(self, *, system_prompt: str, user_prompt: str) -> Any:
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

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._headers}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        return {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    def _parse_response(self, data: dict[str, object]) -> dict[str, object]:
        try:
            content = data["choices"][0]["message"]["content"] or "{}"  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Malformed model response: {data}") from exc
        try:
            import json as _json
            parsed = _json.loads(content)  # type: ignore[arg-type]
            if not isinstance(parsed, dict):
                raise ValueError("LLM response was not a JSON object")
            return parsed
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Failed to parse model JSON output: {content}") from exc

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """Synchronous call — used by scheduler agents running in asyncio.to_thread."""
        try:
            response = httpx.post(
                self._chat_endpoint,
                headers=self._build_headers(),
                json=self._build_payload(system_prompt, user_prompt),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc
        return self._parse_response(data)

    async def async_generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """Async call using httpx.AsyncClient — used on the hot async path (book ingestion)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    self._chat_endpoint,
                    headers=self._build_headers(),
                    json=self._build_payload(system_prompt, user_prompt),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc
        return self._parse_response(data)

    async def async_stream(self, *, system_prompt: str, user_prompt: str) -> Any:
        """Stream chat completions from the provider."""
        payload = {
            "model": self._model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    self._chat_endpoint,
                    headers=self._build_headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line.removeprefix("data: ").strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            token = chunk["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except (KeyError, IndexError, json.JSONDecodeError):
                            continue
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    def _resolve_chat_endpoint(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"
