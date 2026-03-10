from __future__ import annotations
import httpx
from app.models import BookMetadata


class GoogleBooksNotFoundError(Exception):
    """Raised when no matching title can be found."""


class GoogleBooksClient:
    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self.base_url = "https://www.googleapis.com/books/v1/volumes"
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_book_metadata(self, title: str) -> BookMetadata:
        query = title.strip()
        response = await self._client.get(
            self.base_url,
            params={"q": f"intitle:{query}", "maxResults": 1},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", [])
        if not items:
            raise GoogleBooksNotFoundError(f"No book found for title: {title}")

        top = items[0]["volumeInfo"]
        canonical_title = top.get("title") or query
        author = (top.get("authors") or ["Unknown"])[0]
        
        # Google Books date format can be YYYY or YYYY-MM-DD
        published_date = top.get("publishedDate", "")
        publish_year = None
        if published_date:
            try:
                publish_year = int(published_date.split("-")[0])
            except (ValueError, IndexError):
                pass
        
        subjects = [str(s) for s in (top.get("categories") or [])[:15]]
        description = top.get("description") or " ".join(subjects[:5]) if subjects else ""
        google_id = items[0].get("id")

        return BookMetadata(
            content_type="book",
            title=canonical_title,
            author=author,
            publish_year=publish_year,
            subjects=subjects,
            description=description,
            google_books_id=google_id,
        )
