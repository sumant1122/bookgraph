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
    graph_stats: dict = Field(default_factory=dict)
    coverage: dict = Field(default_factory=dict)
    recommendations: list[dict] = Field(default_factory=list)
    narrative: dict = Field(default_factory=dict)
    time_delta: dict = Field(default_factory=dict)
    quality_scores: dict = Field(default_factory=dict)
    reading_paths: list[dict] = Field(default_factory=list)
    overlap_contradiction: dict = Field(default_factory=dict)
    sparse_bridges: list[dict] = Field(default_factory=list)
    field_dashboards: list[dict] = Field(default_factory=list)
    freshness: dict = Field(default_factory=dict)


class DiscoveryItem(BaseModel):
    id: str
    type: str
    title: str
    description: str
    nodes: list[str] = Field(default_factory=list)
    created_at: str


class DiscoveriesResponse(BaseModel):
    discoveries: list[DiscoveryItem] = Field(default_factory=list)


class ReadingPathItem(BaseModel):
    concept: str
    books: list[str] = Field(default_factory=list)
    explanation: str = ""


class ReadingPathsResponse(BaseModel):
    paths: list[ReadingPathItem] = Field(default_factory=list)


class KnowledgeGapItem(BaseModel):
    gap: str
    reason: str = ""


class KnowledgeGapsResponse(BaseModel):
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    scope: str = Field(default="auto", pattern="^(auto|book|author|concept|field)$")
    k: int = Field(default=20, ge=5, le=100)


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    citations: list[str] = Field(default_factory=list)
    evidence_nodes: list[dict] = Field(default_factory=list)
    evidence_edges: list[dict] = Field(default_factory=list)
    context_size: dict = Field(default_factory=dict)
    mode: str = "fallback"
    provider: str = "none"
    fallback_reason: str | None = None
