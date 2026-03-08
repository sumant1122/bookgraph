from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.concept_agent import ConceptAgent
from app.agents.insight_agent import InsightAgent
from app.agents.llm_client import OpenAICompatibleJSONClient
from app.agents.relationship_agent import RelationshipAgent
from app.api.routes import router
from app.core.config import get_settings
from app.graph.neo4j_client import GraphRepository
from app.ingestion.openlibrary import OpenLibraryClient
from app.insights.graph_insights import GraphInsightEngine
from app.services.book_service import BookService


def _build_llm_client() -> OpenAICompatibleJSONClient | None:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider == "openai":
        model = settings.llm_model or settings.openai_model
        api_key = settings.llm_api_key or settings.openai_api_key
        if not api_key:
            return None
        base_url = settings.llm_base_url
        return OpenAICompatibleJSONClient(model=model, api_key=api_key, base_url=base_url)

    if provider == "openrouter":
        model = settings.llm_model or settings.openrouter_model
        api_key = settings.llm_api_key or settings.openrouter_api_key
        if not api_key:
            return None
        base_url = settings.llm_base_url or settings.openrouter_base_url
        return OpenAICompatibleJSONClient(model=model, api_key=api_key, base_url=base_url)

    if provider == "ollama":
        model = settings.llm_model or settings.ollama_model
        base_url = settings.llm_base_url or settings.ollama_base_url
        return OpenAICompatibleJSONClient(model=model, api_key=settings.llm_api_key, base_url=base_url)

    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    graph_repo = GraphRepository(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    graph_repo.ensure_constraints()
    llm_client = _build_llm_client()
    concept_agent = ConceptAgent(llm_client=llm_client)
    relationship_agent = RelationshipAgent(llm_client=llm_client)
    insight_agent = InsightAgent(llm_client=llm_client)
    openlibrary_client = OpenLibraryClient(settings.openlibrary_base_url)
    app.state.graph_repo = graph_repo
    app.state.book_service = BookService(
        openlibrary_client=openlibrary_client,
        graph_repo=graph_repo,
        concept_agent=concept_agent,
        relationship_agent=relationship_agent,
        relationship_scan_limit=settings.relationship_scan_limit,
    )
    app.state.insight_engine = GraphInsightEngine(graph_repo, insight_agent=insight_agent)
    try:
        yield
    finally:
        await openlibrary_client.close()
        graph_repo.close()


app = FastAPI(title="BookGraph API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
