from __future__ import annotations

from hashlib import sha1
from typing import Any

from app.agents.llm_client import LLMClient, LLMError
from app.graph.discovery_repo import DiscoveryGraphRepository


class ReadingPathAgent:
    """
    Generates concept-centric reading paths and stores them for the API/UI.
    """

    def __init__(
        self,
        repo: DiscoveryGraphRepository,
        llm_client: LLMClient | None = None,
        limit_concepts: int = 8,
        path_len: int = 4,
    ) -> None:
        self._repo = repo
        self._llm_client = llm_client
        self._limit_concepts = limit_concepts
        self._path_len = path_len

    def run(self) -> list[dict[str, Any]]:
        candidates = self._repo.get_concept_reading_paths(
            limit_concepts=self._limit_concepts,
            path_len=self._path_len,
        )
        saved: list[dict[str, Any]] = []
        for candidate in candidates:
            concept = str(candidate.get("concept") or "").strip()
            if not concept:
                continue
            rows = [row for row in (candidate.get("books") or []) if isinstance(row, dict)]
            ordered_books = self._order_books(rows)
            if len(ordered_books) < 2:
                continue
            explanation = self._explain_path(concept=concept, books=ordered_books)
            signature = self._signature(concept=concept, books=ordered_books)
            saved.append(
                self._repo.save_reading_path(
                    concept=concept,
                    books=ordered_books,
                    explanation=explanation,
                    signature=signature,
                )
            )
        return saved

    def _order_books(self, rows: list[dict[str, Any]]) -> list[str]:
        ordered = sorted(
            rows,
            key=lambda row: (
                int(row.get("publish_year") or 9999),
                -int(row.get("relation_score") or 0),
                str(row.get("title") or ""),
            ),
        )
        return [str(row.get("title")) for row in ordered if str(row.get("title") or "").strip()]

    def _explain_path(self, concept: str, books: list[str]) -> str:
        fallback = (
            f"This path starts with foundational titles and moves toward more connected viewpoints "
            f"for '{concept}': {' -> '.join(books)}."
        )
        if not self._llm_client:
            return fallback
        system_prompt = (
            "You explain reading sequences from a knowledge graph. "
            "Return strict JSON with key: explanation."
        )
        user_prompt = (
            f"Concept: {concept}\n"
            f"Path: {books}\n"
            "Explain why this order is pedagogically useful in under 60 words."
        )
        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            explanation = str(payload.get("explanation") or "").strip()
            return explanation[:500] if explanation else fallback
        except LLMError:
            return fallback

    def _signature(self, concept: str, books: list[str]) -> str:
        raw = f"{concept}|{'|'.join(books)}"
        return sha1(raw.encode("utf-8")).hexdigest()
