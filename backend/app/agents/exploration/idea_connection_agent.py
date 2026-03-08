from __future__ import annotations

from typing import Any

from app.agents.llm_client import LLMClient
from app.graph.neo4j_client import GraphRepository


class IdeaConnectionAgent:
    """
    Incremental scaffold for idea-connection discovery.
    """

    def __init__(self, repo: GraphRepository, llm_client: LLMClient | None = None) -> None:
        self._repo = repo
        self._llm_client = llm_client

    def run(self) -> list[dict[str, Any]]:
        # Implemented in the next increment.
        return []
