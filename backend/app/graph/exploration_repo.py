from __future__ import annotations

from typing import Any


class ExplorationGraphRepository:
    """
    Query/persistence operations required by autonomous exploration agents.
    """

    def __init__(self, root_repo: Any) -> None:
        self._root = root_repo

    def detect_clusters(self) -> list[dict[str, Any]]:
        return self._root.detect_clusters()

    def get_central_books(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._root.get_central_books(limit=limit)

    def get_cross_field_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._root.get_cross_field_concepts(limit=limit)

    def get_book_nodes_by_titles(self, titles: list[str]) -> list[dict[str, Any]]:
        return self._root.get_book_nodes_by_titles(titles)

    def get_concept_nodes_by_names(self, concepts: list[str]) -> list[dict[str, Any]]:
        return self._root.get_concept_nodes_by_names(concepts)

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        return self._root.get_field_nodes_by_names(fields)

    def save_graph_insight(
        self,
        insight_type: str,
        title: str,
        description: str,
        node_ids: list[str],
        related_nodes: list[str],
        signature: str,
    ) -> dict[str, Any]:
        return self._root.save_graph_insight(
            insight_type=insight_type,
            title=title,
            description=description,
            node_ids=node_ids,
            related_nodes=related_nodes,
            signature=signature,
        )
