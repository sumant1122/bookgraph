from __future__ import annotations

from dataclasses import dataclass

from app.agents.llm_client import LLMClient, LLMError

ALLOWED_RELATIONSHIPS = {
    "RELATED_TO",
    "INFLUENCED_BY",
    "CONTRADICTS",
    "EXPANDS",
    "BELONGS_TO_FIELD",
}


@dataclass(slots=True)
class RelationshipResult:
    source: str
    relation: str
    target: str


class RelationshipAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def determine_relationship(
        self,
        source_book: dict[str, str | list[str] | int | None],
        target_book: dict[str, str | list[str] | int | None],
    ) -> RelationshipResult | None:
        source = str(source_book.get("title") or "").strip()
        target = str(target_book.get("title") or "").strip()
        if not source or not target or source == target:
            return None

        if not self._llm_client:
            return self._heuristic_relationship(source_book, target_book)

        system_prompt = (
            "Determine if there is a meaningful intellectual relationship between two books. "
            "Return strict JSON with keys: source, relation, target. "
            "Allowed relations: RELATED_TO, INFLUENCED_BY, CONTRADICTS, EXPANDS, BELONGS_TO_FIELD. "
            "If no relationship exists, return relation as NONE."
        )
        user_prompt = (
            f"Book A:\n{source_book}\n\n"
            f"Book B:\n{target_book}\n\n"
            "Return JSON."
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            relation = str(payload.get("relation", "")).strip().upper()
            if relation not in ALLOWED_RELATIONSHIPS:
                return None
            mapped_relation = "BELONGS_TO" if relation == "BELONGS_TO_FIELD" else relation
            return RelationshipResult(source=source, relation=mapped_relation, target=target)
        except LLMError:
            return self._heuristic_relationship(source_book, target_book)

    def _heuristic_relationship(
        self,
        source_book: dict[str, str | list[str] | int | None],
        target_book: dict[str, str | list[str] | int | None],
    ) -> RelationshipResult | None:
        source = str(source_book.get("title") or "").strip()
        target = str(target_book.get("title") or "").strip()
        source_subjects = {str(s).lower() for s in (source_book.get("subjects") or [])}
        target_subjects = {str(s).lower() for s in (target_book.get("subjects") or [])}
        overlap = source_subjects.intersection(target_subjects)
        if overlap:
            return RelationshipResult(source=source, relation="RELATED_TO", target=target)

        source_desc = str(source_book.get("description") or "").lower()
        target_desc = str(target_book.get("description") or "").lower()
        if source_desc and target_desc and source_desc[:80] in target_desc:
            return RelationshipResult(source=source, relation="INFLUENCED_BY", target=target)

        return None

