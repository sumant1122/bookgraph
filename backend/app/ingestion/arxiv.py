from __future__ import annotations
from dataclasses import dataclass
import arxiv
from app.models import PaperMetadata

class ArxivNotFoundError(Exception):
    """Raised when no matching paper can be found."""

class ArxivClient:
    def __init__(self) -> None:
        self._client = arxiv.Client()

    def fetch_paper_metadata(self, title: str) -> PaperMetadata:
        search = arxiv.Search(
            query=title,
            max_results=1,
            sort_by=arxiv.SortCriterion.Relevance
        )
        results = list(self._client.results(search))
        if not results:
            raise ArxivNotFoundError(f"No paper found for title: {title}")

        top = results[0]
        author = ", ".join([author.name for author in top.authors])

        return PaperMetadata(
            content_type="paper",
            title=top.title,
            author=author,
            publish_year=top.published.year,
            description=top.summary,
            arxiv_id=top.entry_id,
            doi=top.doi,
            journal=top.journal_ref,
        )
