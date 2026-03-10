from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(slots=True)
class ContentItem:
    pass

@dataclass(slots=True)
class BookMetadata(ContentItem):
    title: str
    author: str
    publish_year: int | None
    description: str
    subjects: list[str]
    content_type: Literal["book"] = "book"
    openlibrary_key: str | None = None
    google_books_id: str | None = None

@dataclass(slots=True)
class PaperMetadata(ContentItem):
    title: str
    author: str
    publish_year: int | None
    description: str
    content_type: Literal["paper"] = "paper"
    arxiv_id: str | None = None
    journal: str | None = None
    doi: str | None = None
