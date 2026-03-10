from __future__ import annotations
import httpx
from app.models import BookMetadata


class OpenLibraryNotFoundError(Exception):
    """Raised when no matching title can be found."""


class OpenLibraryClient:
    def __init__(self, base_url: str, timeout_seconds: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_book_metadata(self, title: str) -> BookMetadata:
        query = title.strip()
        response = await self._client.get(
            f"{self.base_url}/search.json",
            params={"title": query},
        )
        response.raise_for_status()
        payload = response.json()
        docs = payload.get("docs", [])
        if not docs:
            raise OpenLibraryNotFoundError(f"No book found for title: {title}")

        top = docs[0]
        canonical_title = top.get("title") or query
        author = (top.get("author_name") or ["Unknown"])[0]
        publish_year = top.get("first_publish_year")
        subjects = [str(s) for s in (top.get("subject") or [])[:15]]
        work_key = top.get("key")
        description = await self._fetch_work_description(work_key)
        if not description:
            description = " ".join(subjects[:5]) if subjects else ""

        return BookMetadata(
            content_type="book",
            title=canonical_title,
            author=author,
            publish_year=publish_year,
            subjects=subjects,
            description=description,
            openlibrary_key=work_key,
        )

    async def _fetch_work_description(self, work_key: str | None) -> str:
        if not work_key:
            return ""
        response = await self._client.get(f"{self.base_url}{work_key}.json")
        if response.status_code >= 400:
            return ""
        payload = response.json()
        description = payload.get("description")
        if isinstance(description, dict):
            return str(description.get("value") or "").strip()
        if isinstance(description, str):
            return description.strip()
        return ""

