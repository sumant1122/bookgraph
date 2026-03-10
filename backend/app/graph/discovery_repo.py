from __future__ import annotations

from typing import Any


class DiscoveryGraphRepository:
    """
    Persistence and scheduling state for autonomous discovery agents.
    """

    def __init__(self, root_repo: Any) -> None:
        self._root = root_repo

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

    def list_graph_insights(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._root.list_graph_insights(limit=limit)

    def get_graph_insight(self, insight_id: str) -> dict[str, Any] | None:
        return self._root.get_graph_insight(insight_id)

    def get_concept_reading_paths(self, limit_concepts: int = 8, path_len: int = 4) -> list[dict[str, Any]]:
        return self._root.get_concept_reading_paths(limit_concepts=limit_concepts, path_len=path_len)

    def save_reading_path(
        self,
        concept: str,
        items: list[str],
        explanation: str,
        signature: str,
    ) -> dict[str, Any]:
        return self._root.save_reading_path(
            concept=concept,
            items=items,
            explanation=explanation,
            signature=signature,
        )

    def list_reading_paths(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._root.list_reading_paths(limit=limit)

    def detect_missing_topics(self, threshold: int = 1) -> list[dict[str, Any]]:
        return self._root.detect_missing_topics(threshold=threshold)

    def detect_sparse_bridges(self, limit: int = 8, max_fields: int = 10) -> list[dict[str, Any]]:
        return self._root.detect_sparse_bridges(limit=limit, max_fields=max_fields)

    def get_items_for_fields(self, fields: list[str], limit: int = 5) -> list[str]:
        return self._root.get_items_for_fields(fields=fields, limit=limit)

    def save_knowledge_gap(
        self,
        gap: str,
        reason: str,
        candidate_items: list[str],
        signature: str,
    ) -> dict[str, Any]:
        return self._root.save_knowledge_gap(
            gap=gap,
            reason=reason,
            candidate_items=candidate_items,
            signature=signature,
        )

    def list_knowledge_gaps(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._root.list_knowledge_gaps(limit=limit)

    def try_acquire_agent_job(self, name: str, owner_id: str, lease_seconds: int) -> bool:
        return self._root.try_acquire_agent_job(name=name, owner_id=owner_id, lease_seconds=lease_seconds)

    def complete_agent_job_run(self, name: str, owner_id: str, status: str, error: str | None = None) -> None:
        self._root.complete_agent_job_run(name=name, owner_id=owner_id, status=status, error=error)
