from __future__ import annotations

from fastapi import Request

from app.graph.neo4j_client import Neo4jRepository
from app.services.content_service import ContentService
from app.services.chat_service import ChatService


def get_content_service(request: Request) -> ContentService:
    return request.app.state.content_service


def get_graph_repo(request: Request) -> Neo4jRepository:
    return request.app.state.graph_repo


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service
