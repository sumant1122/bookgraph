from __future__ import annotations

from dataclasses import dataclass

from app.agents.concept_agent import ConceptAgent
from app.agents.relationship_agent import RelationshipAgent
from app.enrichment.concept_extractor import ConceptExtractor
from app.graph.book_repo import BookGraphRepository
from app.ingestion.openlibrary import BookMetadata, OpenLibraryClient


@dataclass(slots=True)
class IngestionResult:
    metadata: BookMetadata
    concepts: list[str]
    fields: list[str]
    relationships_created: int


class BookService:
    def __init__(
        self,
        openlibrary_client: OpenLibraryClient,
        graph_repo: BookGraphRepository,
        concept_agent: ConceptAgent,
        relationship_agent: RelationshipAgent,
        relationship_scan_limit: int = 20,
    ) -> None:
        self._openlibrary_client = openlibrary_client
        self._graph_repo = graph_repo
        self._concept_extractor = ConceptExtractor(concept_agent)
        self._relationship_agent = relationship_agent
        self._relationship_scan_limit = relationship_scan_limit

    async def ingest_book(self, title: str) -> IngestionResult:
        metadata = await self._openlibrary_client.fetch_book_metadata(title)
        self._graph_repo.upsert_book(metadata)

        concept_result = self._concept_extractor.run(
            summary=metadata.description,
            fallback_subjects=metadata.subjects,
        )
        self._graph_repo.add_concepts_and_fields(
            book_title=metadata.title,
            concepts=concept_result.concepts,
            fields=concept_result.fields,
        )

        relationships_created = self._discover_relationships(metadata)
        return IngestionResult(
            metadata=metadata,
            concepts=concept_result.concepts,
            fields=concept_result.fields,
            relationships_created=relationships_created,
        )

    def _discover_relationships(self, new_book: BookMetadata) -> int:
        candidate_books = self._graph_repo.get_books_for_relationship_scan(
            exclude_title=new_book.title,
            limit=self._relationship_scan_limit,
            preferred_fields=new_book.subjects,
            publish_year=new_book.publish_year,
        )
        created = 0
        source_payload = {
            "title": new_book.title,
            "description": new_book.description,
            "subjects": new_book.subjects,
            "publish_year": new_book.publish_year,
        }
        for candidate in candidate_books:
            relationship = self._relationship_agent.determine_relationship(
                source_book=source_payload,
                target_book=candidate,
            )
            if not relationship:
                continue
            self._graph_repo.add_book_relationship(
                source=relationship.source,
                relation=relationship.relation,
                target=relationship.target,
                confidence=relationship.confidence,
                reason=relationship.reason,
                method=relationship.method,
            )
            created += 1
        return created
