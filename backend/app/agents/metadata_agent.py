from __future__ import annotations
from typing import Any
from app.agents.llm_client import LLMClient, LLMError
from app.models import BookMetadata, PaperMetadata


class MetadataAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def async_extract_metadata(self, text: str) -> BookMetadata | PaperMetadata:
        if not self._llm_client:
            return PaperMetadata(title="Unknown", author="Unknown", publish_year=None, description="No LLM client")

        system_prompt = (
            "You extract bibliographic metadata from the first few pages of a document. "
            "Determine if it is a 'book' or a 'paper'. "
            "Return strict JSON with keys: type (string 'book' or 'paper'), title (string), author (string), "
            "publish_year (integer or null), description (concise summary, string)."
        )
        user_prompt = f"Extract metadata from this text snippet:\n\n{text[:4000]}"

        try:
            payload = await self._llm_client.async_generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            doc_type = str(payload.get("type", "paper")).lower()
            title = str(payload.get("title", "Unknown"))
            author = str(payload.get("author", "Unknown"))
            publish_year = payload.get("publish_year")
            description = str(payload.get("description", ""))

            if doc_type == "book":
                return BookMetadata(
                    title=title,
                    author=author,
                    publish_year=int(publish_year) if publish_year else None,
                    description=description,
                    subjects=[],
                    content_type="book"
                )
            else:
                return PaperMetadata(
                    title=title,
                    author=author,
                    publish_year=int(publish_year) if publish_year else None,
                    description=description,
                    content_type="paper"
                )
        except (LLMError, ValueError):
            return PaperMetadata(title="Extraction Failed", author="Unknown", publish_year=None, description="")
