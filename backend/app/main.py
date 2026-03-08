from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.exploration.graph_explorer import GraphExplorerAgent
from app.agents.exploration.idea_connection_agent import IdeaConnectionAgent
from app.agents.exploration.knowledge_gap_agent import KnowledgeGapAgent
from app.agents.exploration.reading_path_agent import ReadingPathAgent
from app.agents.chat_agent import ChatAgent
from app.agents.concept_agent import ConceptAgent
from app.agents.insight_agent import InsightAgent
from app.agents.llm_client import OpenAICompatibleJSONClient
from app.agents.relationship_agent import RelationshipAgent
from app.agents.scheduler import AgentScheduler
from app.api.routes import router
from app.core.config import get_settings
from app.graph.neo4j_client import GraphRepository
from app.ingestion.openlibrary import OpenLibraryClient
from app.insights.graph_insights import GraphInsightEngine
from app.services.book_service import BookService
from app.services.chat_service import ChatService


def _build_llm_client() -> OpenAICompatibleJSONClient | None:
    settings = get_settings()
    provider = settings.model_provider.strip().lower()

    def build_openai() -> OpenAICompatibleJSONClient | None:
        model = settings.openai_model
        api_key = settings.openai_api_key
        if not api_key:
            return None
        base_url = None
        return OpenAICompatibleJSONClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            provider="openai",
        )

    def build_openrouter() -> OpenAICompatibleJSONClient | None:
        model = settings.openrouter_model
        api_key = settings.openrouter_api_key
        if not api_key:
            return None
        base_url = settings.openrouter_base_url
        return OpenAICompatibleJSONClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            provider="openrouter",
        )

    def build_ollama() -> OpenAICompatibleJSONClient:
        model = settings.ollama_model
        base_url = settings.ollama_base_url
        return OpenAICompatibleJSONClient(
            model=model,
            api_key=settings.ollama_api_key,
            base_url=base_url,
            provider="ollama",
        )

    if provider == "openai":
        return build_openai() or build_openrouter()

    if provider == "openrouter":
        return build_openrouter() or build_openai()

    if provider == "ollama":
        return build_ollama()

    if provider == "auto":
        return build_openrouter() or build_openai()

    return build_openrouter() or build_openai()


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
    chat_agent = ChatAgent(llm_client=llm_client)
    graph_explorer_agent = GraphExplorerAgent(repo=graph_repo, llm_client=llm_client)
    reading_path_agent = ReadingPathAgent(repo=graph_repo, llm_client=llm_client)
    knowledge_gap_agent = KnowledgeGapAgent(repo=graph_repo, llm_client=llm_client)
    idea_connection_agent = IdeaConnectionAgent(repo=graph_repo, llm_client=llm_client)
    scheduler = AgentScheduler()
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
    app.state.chat_service = ChatService(graph_repo, chat_agent=chat_agent)
    app.state.graph_explorer_agent = graph_explorer_agent
    app.state.reading_path_agent = reading_path_agent
    app.state.knowledge_gap_agent = knowledge_gap_agent
    app.state.idea_connection_agent = idea_connection_agent
    app.state.agent_scheduler = scheduler
    scheduler.start(
        [
            ("graph_explorer", 6 * 60 * 60, graph_explorer_agent.run),
            ("reading_path", 24 * 60 * 60, reading_path_agent.run),
            ("knowledge_gap", 24 * 60 * 60, knowledge_gap_agent.run),
            ("idea_connection", 12 * 60 * 60, idea_connection_agent.run),
        ]
    )
    try:
        yield
    finally:
        await scheduler.stop()
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
