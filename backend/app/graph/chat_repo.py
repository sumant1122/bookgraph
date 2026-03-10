from __future__ import annotations

from typing import Any


class ChatGraphRepository:
    """
    Retrieval and stats queries used by chat-answering flows.
    """

    def __init__(self, root_repo: Any) -> None:
        self._root = root_repo

    def get_chat_subgraph(
        self,
        question: str,
        scope: str = "auto",
        k: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        return self._root.get_chat_subgraph(question=question, scope=scope, k=k)

    def get_graph_stats(self) -> dict[str, Any]:
        return self._root.get_graph_stats()

    def execute_read_query(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._root.execute_read_query(query=query, params=params)
