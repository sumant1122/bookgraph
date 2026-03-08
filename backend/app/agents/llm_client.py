from __future__ import annotations

import json
from typing import Any, Protocol

from openai import OpenAI


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
        default_headers: dict[str, str] | None = None,
    ) -> None:
        client_kwargs: dict[str, Any] = {
            "api_key": api_key or "not-required",
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        self._client = OpenAI(**client_kwargs)
        self._model = model

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc

        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("LLM response was not a JSON object")
            return parsed
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Failed to parse model JSON output: {content}") from exc
