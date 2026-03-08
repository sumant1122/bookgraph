from __future__ import annotations

from hashlib import sha1
from typing import Any

from app.agents.llm_client import LLMClient, LLMError
from app.graph.discovery_repo import DiscoveryGraphRepository


class KnowledgeGapAgent:
    """
    Detects missing adjacent fields and suggests bridge books.
    """

    def __init__(self, repo: DiscoveryGraphRepository, llm_client: LLMClient | None = None) -> None:
        self._repo = repo
        self._llm_client = llm_client

    def run(self) -> list[dict[str, Any]]:
        missing = self._repo.detect_missing_topics(threshold=1)[:8]
        sparse = self._repo.detect_sparse_bridges(limit=15, max_fields=12)
        saved: list[dict[str, Any]] = []

        for row in missing:
            gap_field = str(row.get("field") or "").strip()
            if not gap_field:
                continue
            adjacent = self._adjacent_fields(gap_field, sparse)
            candidate_books = self._repo.get_books_for_fields(adjacent[:2], limit=5) if adjacent else []
            reason = self._reason_for_gap(
                gap_field=gap_field,
                book_count=int(row.get("bookCount") or 0),
                adjacent=adjacent,
                candidates=candidate_books,
            )
            signature = self._signature(gap_field=gap_field, adjacent=adjacent)
            saved.append(
                self._repo.save_knowledge_gap(
                    gap=gap_field,
                    reason=reason,
                    candidate_books=candidate_books,
                    signature=signature,
                )
            )
        return saved

    def _adjacent_fields(self, gap_field: str, sparse: list[dict[str, Any]]) -> list[str]:
        candidates: list[str] = []
        for row in sparse:
            a = str(row.get("field_a") or "")
            b = str(row.get("field_b") or "")
            if a == gap_field and b:
                candidates.append(b)
            elif b == gap_field and a:
                candidates.append(a)
        # Preserve order and uniqueness.
        seen: set[str] = set()
        unique: list[str] = []
        for field in candidates:
            if field not in seen:
                seen.add(field)
                unique.append(field)
        return unique

    def _reason_for_gap(
        self,
        gap_field: str,
        book_count: int,
        adjacent: list[str],
        candidates: list[str],
    ) -> str:
        adjacency_text = ", ".join(adjacent[:3]) if adjacent else "related neighboring fields"
        candidate_text = ", ".join(candidates[:3]) if candidates else "bridge books from adjacent areas"
        fallback = (
            f"Coverage is low for '{gap_field}' ({book_count} books). "
            f"Your graph is also weakly connected to {adjacency_text}. "
            f"Add books such as {candidate_text} to reduce this gap."
        )
        if not self._llm_client:
            return fallback
        system_prompt = (
            "You explain knowledge gaps in a personal reading graph. "
            "Return strict JSON with key: reason."
        )
        user_prompt = (
            f"Gap field: {gap_field}\n"
            f"Current book count: {book_count}\n"
            f"Adjacent fields with sparse bridges: {adjacent}\n"
            f"Candidate books: {candidates}\n"
            "Provide one concise reason and recommendation."
        )
        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            reason = str(payload.get("reason") or "").strip()
            return reason[:500] if reason else fallback
        except LLMError:
            return fallback

    def _signature(self, gap_field: str, adjacent: list[str]) -> str:
        raw = f"{gap_field}|{'|'.join(sorted(adjacent))}"
        return sha1(raw.encode("utf-8")).hexdigest()
