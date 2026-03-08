from __future__ import annotations

from pydantic import BaseModel, Field


class AddBookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class BookResponse(BaseModel):
    title: str
    author: str
    publish_year: int | None = None
    subjects: list[str] = Field(default_factory=list)
    description: str = ""
    concepts: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    relationships_created: int = 0


class GraphResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class InsightResponse(BaseModel):
    central_books: dict
    clusters: dict
    missing_topics: dict
