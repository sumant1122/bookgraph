from __future__ import annotations

import sys
import types
import unittest
from typing import Any

# Lightweight test stub to allow importing modules without installed neo4j package.
if "neo4j" not in sys.modules:
    neo4j_stub = types.ModuleType("neo4j")

    class GraphDatabase:  # noqa: D401
        @staticmethod
        def driver(*args, **kwargs):  # noqa: ANN002, ANN003
            return None

    neo4j_stub.GraphDatabase = GraphDatabase
    neo4j_exceptions_stub = types.ModuleType("neo4j.exceptions")

    class Neo4jError(Exception):
        pass

    class CypherSyntaxError(Exception):
        pass

    neo4j_exceptions_stub.Neo4jError = Neo4jError
    neo4j_exceptions_stub.CypherSyntaxError = CypherSyntaxError
    sys.modules["neo4j"] = neo4j_stub
    sys.modules["neo4j.exceptions"] = neo4j_exceptions_stub

from app.agents.concept_agent import ConceptExtractionResult
from app.agents.relationship_agent import RelationshipResult
from app.ingestion.openlibrary import BookMetadata
from app.services.book_service import BookService


class FakeOpenLibraryClient:
    async def fetch_book_metadata(self, title: str) -> BookMetadata:
        return BookMetadata(
            title=title,
            author="Robert C. Martin",
            publish_year=2008,
            subjects=["Software Engineering"],
            description="A handbook of agile software craftsmanship.",
            openlibrary_key="OL1W",
        )


class FakeGraphRepo:
    def __init__(self) -> None:
        self.relationship_calls: list[dict[str, Any]] = []
        self.added_concepts: list[dict[str, Any]] = []
        self.relationship_scan_calls: list[dict[str, Any]] = []

    def upsert_book(self, metadata: BookMetadata) -> None:
        return None

    def add_concepts_and_fields(self, book_title: str, concepts: list[str], fields: list[str]) -> None:
        self.added_concepts.append({"book_title": book_title, "concepts": concepts, "fields": fields})

    def get_books_for_relationship_scan(
        self,
        exclude_title: str,
        limit: int,
        preferred_fields: list[str] | None = None,
        publish_year: int | None = None,
    ) -> list[dict[str, Any]]:
        self.relationship_scan_calls.append(
            {
                "exclude_title": exclude_title,
                "limit": limit,
                "preferred_fields": preferred_fields or [],
                "publish_year": publish_year,
            }
        )
        return [
            {"title": "Design Patterns", "description": "OO catalog", "subjects": ["Software Engineering"]},
            {"title": "The Lean Startup", "description": "Startup methods", "subjects": ["Entrepreneurship"]},
        ]

    def add_book_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        confidence: float | None = None,
        reason: str | None = None,
        method: str | None = None,
    ) -> None:
        self.relationship_calls.append(
            {
                "source": source,
                "relation": relation,
                "target": target,
                "confidence": confidence,
                "reason": reason,
                "method": method,
            }
        )


class FakeConceptAgent:
    def extract(self, book_summary: str, fallback_subjects: list[str] | None = None) -> ConceptExtractionResult:
        return ConceptExtractionResult(
            concepts=["Clean Code", "Refactoring"],
            fields=["Software Engineering"],
        )


class FakeRelationshipAgent:
    def determine_relationship(
        self,
        source_book: dict[str, str | list[str] | int | None],
        target_book: dict[str, str | list[str] | int | None],
    ) -> RelationshipResult | None:
        target = str(target_book.get("title") or "")
        if target == "Design Patterns":
            return RelationshipResult(
                source=str(source_book.get("title") or ""),
                relation="RELATED_TO",
                target=target,
                confidence=0.77,
                reason="Shared software engineering foundations.",
                method="llm",
            )
        return None


class BookServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_book_creates_relationship_with_metadata(self) -> None:
        graph_repo = FakeGraphRepo()
        service = BookService(
            openlibrary_client=FakeOpenLibraryClient(),
            graph_repo=graph_repo,
            concept_agent=FakeConceptAgent(),  # type: ignore[arg-type]
            relationship_agent=FakeRelationshipAgent(),  # type: ignore[arg-type]
            relationship_scan_limit=20,
        )

        result = await service.ingest_book("Clean Code")

        self.assertEqual(result.relationships_created, 1)
        self.assertEqual(len(graph_repo.relationship_calls), 1)
        relationship = graph_repo.relationship_calls[0]
        self.assertEqual(relationship["relation"], "RELATED_TO")
        self.assertEqual(relationship["confidence"], 0.77)
        self.assertEqual(relationship["method"], "llm")
        self.assertTrue(graph_repo.added_concepts)
        self.assertEqual(graph_repo.relationship_scan_calls[0]["preferred_fields"], ["Software Engineering"])
        self.assertEqual(graph_repo.relationship_scan_calls[0]["publish_year"], 2008)
