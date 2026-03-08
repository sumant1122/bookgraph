from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_book_service, get_graph_repo, get_insight_engine
from app.api.schemas import AddBookRequest, BookResponse, GraphResponse, InsightResponse
from app.graph.neo4j_client import GraphRepository
from app.ingestion.openlibrary import OpenLibraryNotFoundError
from app.insights.graph_insights import GraphInsightEngine
from app.services.book_service import BookService

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


@router.get("/insights", response_model=InsightResponse)
async def insights(engine: GraphInsightEngine = Depends(get_insight_engine)) -> InsightResponse:
    bundle = engine.build_insight_bundle()
    return InsightResponse(**bundle)
