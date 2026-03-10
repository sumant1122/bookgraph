from __future__ import annotations

from pydantic import BaseModel, Field


class AddItemRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class ItemResponse(BaseModel):
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


class GraphSearchResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)


class GraphNodeDetailResponse(BaseModel):
    id: str
    label: str
    type: str
    properties: dict = Field(default_factory=dict)
    degree: int = 0
    neighbors: list[dict] = Field(default_factory=list)


class DiscoveryItem(BaseModel):
    id: str
    type: str
    title: str
    description: str
    node_ids: list[str] = Field(default_factory=list)
    related_nodes: list[str] = Field(default_factory=list)
    created_at: str


class DiscoveriesResponse(BaseModel):
    discoveries: list[DiscoveryItem] = Field(default_factory=list)


class ReadingPathItem(BaseModel):
    concept: str
    items: list[str] = Field(default_factory=list)
    explanation: str = ""
    created_at: str | None = None


class ReadingPathsResponse(BaseModel):
    paths: list[ReadingPathItem] = Field(default_factory=list)


class KnowledgeGapItem(BaseModel):
    gap: str
    reason: str = ""
    candidate_items: list[str] = Field(default_factory=list)
    created_at: str | None = None


class KnowledgeGapsResponse(BaseModel):
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    scope: str = Field(default="auto", pattern="^(auto|book|paper|author|concept|field)$")
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
    cypher_query: str | None = None
