from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_book_service, get_chat_service, get_graph_repo, get_insight_engine
from app.api.schemas import (
    AddBookRequest,
    BookResponse,
    ChatRequest,
    ChatResponse,
    DiscoveriesResponse,
    DiscoveryItem,
    GraphResponse,
    GraphNodeDetailResponse,
    GraphSearchResponse,
    InsightResponse,
    KnowledgeGapsResponse,
    ReadingPathsResponse,
)
from app.graph.neo4j_client import GraphRepository
from app.ingestion.openlibrary import OpenLibraryNotFoundError
from app.insights.graph_insights import GraphInsightEngine
from app.services.book_service import BookService
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/books", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def add_book(payload: AddBookRequest, service: BookService = Depends(get_book_service)) -> BookResponse:
    try:
        result = await service.ingest_book(payload.title)
    except OpenLibraryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return BookResponse(
        title=result.metadata.title,
        author=result.metadata.author,
        publish_year=result.metadata.publish_year,
        subjects=result.metadata.subjects,
        description=result.metadata.description,
        concepts=result.concepts,
        fields=result.fields,
        relationships_created=result.relationships_created,
    )


@router.get("/graph", response_model=GraphResponse)
async def graph_snapshot(repo: GraphRepository = Depends(get_graph_repo)) -> GraphResponse:
    data = repo.get_graph()
    return GraphResponse(nodes=data["nodes"], edges=data["edges"])


@router.get("/graph/search", response_model=GraphSearchResponse)
async def graph_search(
    q: str = Query(default="", min_length=0, max_length=120),
    node_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=25, ge=1, le=100),
    repo: GraphRepository = Depends(get_graph_repo),
) -> GraphSearchResponse:
    safe_type = node_type.strip().lower() if isinstance(node_type, str) and node_type.strip() else None
    if safe_type and safe_type not in {"book", "author", "concept", "field"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node type filter.")
    nodes = repo.search_graph_nodes(query=q, limit=limit, node_type=safe_type)
    return GraphSearchResponse(nodes=nodes)


@router.get("/graph/focus", response_model=GraphResponse)
async def graph_focus(
    node_id: str = Query(min_length=1),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=120, ge=10, le=300),
    repo: GraphRepository = Depends(get_graph_repo),
) -> GraphResponse:
    data = repo.get_focus_subgraph(node_id=node_id, depth=depth, limit=limit)
    return GraphResponse(nodes=data["nodes"], edges=data["edges"])


@router.get("/graph/nodes/{node_id}", response_model=GraphNodeDetailResponse)
async def graph_node_details(node_id: str, repo: GraphRepository = Depends(get_graph_repo)) -> GraphNodeDetailResponse:
    node = repo.get_node_details(node_id=node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found.")
    return GraphNodeDetailResponse(**node)


@router.get("/insights", response_model=InsightResponse)
async def insights(engine: GraphInsightEngine = Depends(get_insight_engine)) -> InsightResponse:
    bundle = engine.get_latest_bundle()
    return InsightResponse(**bundle)


@router.get("/discoveries", response_model=DiscoveriesResponse)
async def discoveries(
    limit: int = Query(default=30, ge=1, le=100),
    repo: GraphRepository = Depends(get_graph_repo),
) -> DiscoveriesResponse:
    rows = repo.list_graph_insights(limit=limit)
    return DiscoveriesResponse(discoveries=[DiscoveryItem(**row) for row in rows])


@router.get("/discoveries/{insight_id}", response_model=DiscoveryItem)
async def discovery_by_id(
    insight_id: str,
    repo: GraphRepository = Depends(get_graph_repo),
) -> DiscoveryItem:
    row = repo.get_graph_insight(insight_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")
    return DiscoveryItem(**row)


@router.get("/reading-paths", response_model=ReadingPathsResponse)
async def reading_paths(
    limit: int = Query(default=30, ge=1, le=100),
    repo: GraphRepository = Depends(get_graph_repo),
) -> ReadingPathsResponse:
    rows = repo.list_reading_paths(limit=limit)
    return ReadingPathsResponse(paths=rows)


@router.get("/knowledge-gaps", response_model=KnowledgeGapsResponse)
async def knowledge_gaps(
    limit: int = Query(default=30, ge=1, le=100),
    repo: GraphRepository = Depends(get_graph_repo),
) -> KnowledgeGapsResponse:
    rows = repo.list_knowledge_gaps(limit=limit)
    return KnowledgeGapsResponse(gaps=rows)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    try:
        result = service.ask(question=payload.question, scope=payload.scope, k=payload.k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ChatResponse(
        answer=result.answer,
        confidence=result.confidence,
        citations=result.citations,
        evidence_nodes=result.evidence_nodes,
        evidence_edges=result.evidence_edges,
        context_size=result.context_size,
        mode=result.mode,
        provider=result.provider,
        fallback_reason=result.fallback_reason,
    )
