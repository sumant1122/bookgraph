from __future__ import annotations

from typing import Any

from app.models import BookMetadata, PaperMetadata, ContentItem


class ContentGraphRepository:
    """
    Content and graph-structure operations used by ingestion and graph UI.
    """

    def __init__(self, root_repo: Any) -> None:
        self._root = root_repo

    def upsert_item(self, metadata: ContentItem) -> None:
        if isinstance(metadata, BookMetadata):
            self._root.upsert_book(metadata)
        elif isinstance(metadata, PaperMetadata):
            self._root.upsert_paper(metadata)

    def add_concepts_and_fields(self, item_title: str, concepts: list[str], fields: list[str]) -> None:
        self._root.add_concepts_and_fields(item_title=item_title, concepts=concepts, fields=fields)

    def get_items_for_relationship_scan(
        self,
        exclude_title: str,
        limit: int,
        preferred_fields: list[str] | None = None,
        publish_year: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._root.get_items_for_relationship_scan(
            exclude_title=exclude_title,
            limit=limit,
            preferred_fields=preferred_fields,
            publish_year=publish_year,
        )

    def add_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        confidence: float | None = None,
        reason: str | None = None,
        method: str | None = None,
    ) -> None:
        self._root.add_relationship(
            source=source,
            relation=relation,
            target=target,
            confidence=confidence,
            reason=reason,
            method=method,
        )

    def get_graph(self) -> dict[str, list[dict[str, Any]]]:
        return self._root.get_graph()

    def get_nodes_by_titles(self, titles: list[str]) -> list[dict[str, Any]]:
        return self._root.get_nodes_by_titles(titles)

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        return self._root.get_field_nodes_by_names(fields)

    def get_concept_nodes_by_names(self, concepts: list[str]) -> list[dict[str, Any]]:
        return self._root.get_concept_nodes_by_names(concepts)
