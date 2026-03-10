from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_content_service, get_chat_service, get_graph_repo
from app.api.schemas import (
    AddItemRequest,
    ItemResponse,
    ChatRequest,
    ChatResponse,
    DiscoveriesResponse,
    DiscoveryItem,
    GraphResponse,
    GraphNodeDetailResponse,
    GraphSearchResponse,
    KnowledgeGapsResponse,
    ReadingPathsResponse,
)
from app.graph.neo4j_client import Neo4jRepository
from app.ingestion.openlibrary import OpenLibraryNotFoundError
from app.ingestion.arxiv import ArxivNotFoundError
from app.ingestion.google_books import GoogleBooksNotFoundError
from app.services.content_service import ContentService
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/books", response_model=list[dict])
async def list_books(
    limit: int = Query(default=50, ge=1, le=200),
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> list[dict]:
    return repo.list_items(limit=limit)


@router.post("/books", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def add_book(payload: AddItemRequest, service: ContentService = Depends(get_content_service)) -> ItemResponse:
    try:
        result = await service.ingest_book(payload.title)
    except OpenLibraryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ItemResponse(
        title=result.metadata.title,
        author=result.metadata.author,
        publish_year=result.metadata.publish_year,
        subjects=result.metadata.subjects if hasattr(result.metadata, 'subjects') else [],
        description=result.metadata.description,
        concepts=result.concepts,
        fields=result.fields,
        relationships_created=result.relationships_created,
    )


@router.post("/google-books", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def add_google_book(payload: AddItemRequest, service: ContentService = Depends(get_content_service)) -> ItemResponse:
    try:
        result = await service.ingest_google_book(payload.title)
    except GoogleBooksNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ItemResponse(
        title=result.metadata.title,
        author=result.metadata.author,
        publish_year=result.metadata.publish_year,
        subjects=result.metadata.subjects if hasattr(result.metadata, 'subjects') else [],
        description=result.metadata.description,
        concepts=result.concepts,
        fields=result.fields,
        relationships_created=result.relationships_created,
    )


@router.post("/papers", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def add_paper(payload: AddItemRequest, service: ContentService = Depends(get_content_service)) -> ItemResponse:
    try:
        result = await service.ingest_paper(payload.title)
    except ArxivNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ItemResponse(
        title=result.metadata.title,
        author=result.metadata.author,
        publish_year=result.metadata.publish_year,
        subjects=[],
        description=result.metadata.description,
        concepts=result.concepts,
        fields=result.fields,
        relationships_created=result.relationships_created,
    )


@router.post("/pdf", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def add_pdf(file: UploadFile = File(...), service: ContentService = Depends(get_content_service)) -> ItemResponse:
    try:
        content = await file.read()
        result = await service.ingest_pdf(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ItemResponse(
        title=result.metadata.title,
        author=result.metadata.author,
        publish_year=result.metadata.publish_year,
        subjects=result.metadata.subjects if hasattr(result.metadata, 'subjects') else [],
        description=result.metadata.description,
        concepts=result.concepts,
        fields=result.fields,
        relationships_created=result.relationships_created,
    )


@router.get("/graph", response_model=GraphResponse)
async def graph_snapshot(repo: Neo4jRepository = Depends(get_graph_repo)) -> GraphResponse:
    data = repo.get_graph()
    return GraphResponse(nodes=data["nodes"], edges=data["edges"])


@router.get("/graph/search", response_model=GraphSearchResponse)
async def graph_search(
    q: str = Query(default="", min_length=0, max_length=120),
    node_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=25, ge=1, le=100),
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> GraphSearchResponse:
    safe_type = node_type.strip().lower() if isinstance(node_type, str) and node_type.strip() else None
    if safe_type and safe_type not in {"book", "paper", "author", "concept", "field"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node type filter.")
    nodes = repo.search_graph_nodes(query=q, limit=limit, node_type=safe_type)
    return GraphSearchResponse(nodes=nodes)


@router.get("/graph/focus", response_model=GraphResponse)
async def graph_focus(
    node_id: str = Query(min_length=1),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=120, ge=10, le=300),
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> GraphResponse:
    data = repo.get_focus_subgraph(node_id=node_id, depth=depth, limit=limit)
    return GraphResponse(nodes=data["nodes"], edges=data["edges"])


@router.get("/graph/nodes/{node_id}", response_model=GraphNodeDetailResponse)
async def graph_node_details(node_id: str, repo: Neo4jRepository = Depends(get_graph_repo)) -> GraphNodeDetailResponse:
    node = repo.get_node_details(node_id=node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found.")
    return GraphNodeDetailResponse(**node)


@router.delete("/graph/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_node(node_id: str, repo: Neo4jRepository = Depends(get_graph_repo)) -> Response:
    deleted = repo.delete_node(node_id=node_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found or deletion not allowed.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/discoveries", response_model=DiscoveriesResponse)
async def discoveries(
    limit: int = Query(default=30, ge=1, le=100),
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> DiscoveriesResponse:
    rows = repo.list_graph_insights(limit=limit)
    return DiscoveriesResponse(discoveries=[DiscoveryItem(**row) for row in rows])


@router.get("/discoveries/{insight_id}", response_model=DiscoveryItem)
async def discovery_by_id(
    insight_id: str,
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> DiscoveryItem:
    row = repo.get_graph_insight(insight_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")
    return DiscoveryItem(**row)


@router.get("/reading-paths", response_model=ReadingPathsResponse)
async def reading_paths(
    limit: int = Query(default=30, ge=1, le=100),
    repo: Neo4jRepository = Depends(get_graph_repo),
) -> ReadingPathsResponse:
    rows = repo.list_reading_paths(limit=limit)
    return ReadingPathsResponse(paths=rows)


@router.get("/knowledge-gaps", response_model=KnowledgeGapsResponse)
async def knowledge_gaps(
    limit: int = Query(default=30, ge=1, le=100),
    repo: Neo4jRepository = Depends(get_graph_repo),
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
        cypher_query=result.cypher_query,
    )


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, service: ChatService = Depends(get_chat_service)) -> StreamingResponse:
    async def _gen():
        try:
            async for token in service.stream_ask(question=payload.question, scope=payload.scope, k=payload.k):
                yield token
        except Exception as exc:
            yield f"\n[Backend Error: {str(exc)}]"

    return StreamingResponse(_gen(), media_type="text/plain")
