from __future__ import annotations

from typing import Any


class AnalyticsGraphRepository:
    """
    Analytics and insight materialization queries for graph intelligence features.
    """

    def __init__(self, root_repo: Any) -> None:
        self._root = root_repo

    def get_central_books(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._root.get_central_books(limit=limit)

    def detect_clusters(self) -> list[dict[str, Any]]:
        return self._root.detect_clusters()

    def detect_missing_topics(self, threshold: int = 1) -> list[dict[str, Any]]:
        return self._root.detect_missing_topics(threshold=threshold)

    def get_graph_stats(self) -> dict[str, Any]:
        return self._root.get_graph_stats()

    def get_field_coverage(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._root.get_field_coverage(limit=limit)

    def get_top_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._root.get_top_concepts(limit=limit)

    def get_unlinked_books(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._root.get_unlinked_books(limit=limit)

    def get_book_relationship_edges(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._root.get_book_relationship_edges(limit=limit)

    def get_book_nodes_by_titles(self, titles: list[str]) -> list[dict[str, Any]]:
        return self._root.get_book_nodes_by_titles(titles)

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        return self._root.get_field_nodes_by_names(fields)

    def get_field_reading_paths(self, limit_fields: int = 4, path_len: int = 4) -> list[dict[str, Any]]:
        return self._root.get_field_reading_paths(limit_fields=limit_fields, path_len=path_len)

    def get_overlap_contradiction_summary(self) -> dict[str, Any]:
        return self._root.get_overlap_contradiction_summary()

    def detect_sparse_bridges(self, limit: int = 8, max_fields: int = 10) -> list[dict[str, Any]]:
        return self._root.detect_sparse_bridges(limit=limit, max_fields=max_fields)

    def get_field_dashboards(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._root.get_field_dashboards(limit=limit)

    def get_latest_insight_snapshots(self, limit: int = 2) -> list[dict[str, Any]]:
        return self._root.get_latest_insight_snapshots(limit=limit)

    def save_insight_snapshot(self, stats: dict[str, Any], overall_score: int) -> None:
        self._root.save_insight_snapshot(stats=stats, overall_score=overall_score)

    def save_latest_insight_bundle(self, bundle: dict[str, Any]) -> None:
        self._root.save_latest_insight_bundle(bundle=bundle)

    def get_latest_insight_bundle(self) -> dict[str, Any] | None:
        return self._root.get_latest_insight_bundle()
