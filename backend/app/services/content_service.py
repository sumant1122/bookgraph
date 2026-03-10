from __future__ import annotations

import asyncio
from typing import Union, BinaryIO
import io
import PyPDF2
from dataclasses import dataclass

from app.agents.concept_agent import ConceptAgent
from app.agents.relationship_agent import RelationshipAgent
from app.agents.metadata_agent import MetadataAgent
from app.enrichment.concept_extractor import ConceptExtractor
from app.graph.content_repo import ContentGraphRepository
from app.ingestion.arxiv import ArxivClient
from app.ingestion.openlibrary import OpenLibraryClient
from app.ingestion.google_books import GoogleBooksClient
from app.models import BookMetadata, PaperMetadata, ContentItem


@dataclass(slots=True)
class IngestionResult:
    metadata: ContentItem
    concepts: list[str]
    fields: list[str]
    relationships_created: int


class ContentService:
    def __init__(
        self,
        openlibrary_client: OpenLibraryClient,
        arxiv_client: ArxivClient,
        google_books_client: GoogleBooksClient,
        graph_repo: ContentGraphRepository,
        concept_agent: ConceptAgent,
        relationship_agent: RelationshipAgent,
        metadata_agent: MetadataAgent,
        relationship_scan_limit: int = 50,
    ) -> None:
        self._openlibrary_client = openlibrary_client
        self._arxiv_client = arxiv_client
        self._google_books_client = google_books_client
        self._graph_repo = graph_repo
        self._concept_extractor = ConceptExtractor(concept_agent)
        self._concept_agent = concept_agent
        self._relationship_agent = relationship_agent
        self._metadata_agent = metadata_agent
        self._relationship_scan_limit = relationship_scan_limit

    async def ingest_book(self, title: str) -> IngestionResult:
        metadata = await self._openlibrary_client.fetch_book_metadata(title)
        return await self._ingest_item(metadata)

    async def ingest_google_book(self, title: str) -> IngestionResult:
        metadata = await self._google_books_client.fetch_book_metadata(title)
        return await self._ingest_item(metadata)

    async def ingest_paper(self, title: str) -> IngestionResult:
        metadata = self._arxiv_client.fetch_paper_metadata(title)
        return await self._ingest_item(metadata)

    async def ingest_pdf(self, file: BinaryIO) -> IngestionResult:
        text = await asyncio.to_thread(self._extract_pdf_text, file)
        metadata = await self._metadata_agent.async_extract_metadata(text)
        return await self._ingest_item(metadata)

    def _extract_pdf_text(self, file: BinaryIO) -> str:
        try:
            reader = PyPDF2.PdfReader(file)
            text_parts = []
            # Extract first 5 pages for metadata extraction
            for i in range(min(5, len(reader.pages))):
                text_parts.append(reader.pages[i].extract_text())
            return "\n".join(text_parts)
        except Exception as exc:
            return f"Error extracting PDF text: {str(exc)}"

    async def _ingest_item(self, metadata: ContentItem) -> IngestionResult:
        await asyncio.to_thread(self._graph_repo.upsert_item, metadata)

        fallback_subjects = []
        if isinstance(metadata, BookMetadata):
            fallback_subjects = metadata.subjects

        concept_result = await self._concept_agent.async_extract(
            summary=metadata.description,
            fallback_subjects=fallback_subjects,
        )

        await asyncio.to_thread(
            self._graph_repo.add_concepts_and_fields,
            item_title=metadata.title,
            concepts=concept_result.concepts,
            fields=concept_result.fields,
        )

        relationships_created = await self._discover_relationships(metadata)
        return IngestionResult(
            metadata=metadata,
            concepts=concept_result.concepts,
            fields=concept_result.fields,
            relationships_created=relationships_created,
        )

    async def _discover_relationships(self, new_item: ContentItem) -> int:
        preferred_fields = []
        if isinstance(new_item, BookMetadata):
            preferred_fields = new_item.subjects

        # Limit candidates more strictly for real-time ingestion to avoid long hangs
        scan_limit = min(self._relationship_scan_limit, 15)

        candidate_items = await asyncio.to_thread(
            self._graph_repo.get_items_for_relationship_scan,
            exclude_title=new_item.title,
            limit=scan_limit,
            preferred_fields=preferred_fields,
            publish_year=new_item.publish_year,
        )
        source_payload = {
            "title": new_item.title,
            "description": new_item.description,
            "subjects": preferred_fields,
            "publish_year": new_item.publish_year,
        }

        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent LLM calls

        async def check_rel(target: dict) -> dict | None:
            async with semaphore:
                try:
                    return await self._relationship_agent.async_determine_relationship(
                        source_item=source_payload,
                        target_item=target,
                    )
                except Exception:
                    return None

        # Run checks in parallel
        results = await asyncio.gather(*(check_rel(c) for c in candidate_items))
        
        created = 0
        for relationship in results:
            if not relationship:
                continue
            
            await asyncio.to_thread(
                self._graph_repo.add_relationship,
                source=relationship.source,
                relation=relationship.relation,
                target=relationship.target,
                confidence=relationship.confidence,
                reason=relationship.reason,
                method=relationship.method,
            )
            created += 1
        return created
