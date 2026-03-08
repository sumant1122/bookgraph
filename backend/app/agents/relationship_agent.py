from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.llm_client import LLMClient, LLMError

ALLOWED_RELATIONSHIPS = {
    "RELATED_TO",
    "INFLUENCED_BY",
    "CONTRADICTS",
    "EXPANDS",
    "BELONGS_TO",
}

RELATION_ALIASES = {
    "RELATES_TO": "RELATED_TO",
    "RELATED": "RELATED_TO",
    "ASSOCIATED_WITH": "RELATED_TO",
    "DISCUSSES": "RELATED_TO",
    "COVERS": "RELATED_TO",
    "INSPIRED_BY": "INFLUENCED_BY",
    "INSPIRES": "INFLUENCED_BY",
    "DERIVED_FROM": "INFLUENCED_BY",
    "BUILDS_ON": "EXPANDS",
    "ELABORATES_ON": "EXPANDS",
    "EXTENDS": "EXPANDS",
    "BELONGS_TO_FIELD": "BELONGS_TO",
}


@dataclass(slots=True)
class RelationshipResult:
    source: str
    relation: str
    target: str
    confidence: float | None = None
    reason: str | None = None
    method: str = "heuristic"


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
            "Return strict JSON with keys: source, relation, target, confidence, reason. "
            "Allowed canonical relations: RELATED_TO, INFLUENCED_BY, CONTRADICTS, EXPANDS, BELONGS_TO_FIELD. "
            "Natural-language relations like 'discusses' or 'inspired by' are valid inputs, "
            "but you must map them to canonical relations. "
            "If no relationship exists, return relation as NONE."
        )
        user_prompt = (
            f"Book A:\n{source_book}\n\n"
            f"Book B:\n{target_book}\n\n"
            "Return JSON."
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            relation = self._normalize_relation(payload)
            if not relation:
                return None
            confidence = self._parse_confidence(payload.get("confidence"))
            reason = str(payload.get("reason") or "").strip()[:240] or None
            return RelationshipResult(
                source=source,
                relation=relation,
                target=target,
                confidence=confidence,
                reason=reason,
                method="llm",
            )
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
            reason = f"Shared subjects: {', '.join(sorted(overlap)[:3])}"
            return RelationshipResult(
                source=source,
                relation="RELATED_TO",
                target=target,
                confidence=0.55,
                reason=reason,
                method="heuristic",
            )

        source_desc = str(source_book.get("description") or "").lower()
        target_desc = str(target_book.get("description") or "").lower()
        if source_desc and target_desc and source_desc[:80] in target_desc:
            return RelationshipResult(
                source=source,
                relation="INFLUENCED_BY",
                target=target,
                confidence=0.5,
                reason="Description overlap suggests influence.",
                method="heuristic",
            )

        return None

    def _normalize_relation(self, payload: dict[str, Any]) -> str | None:
        raw_relation = str(payload.get("relation") or payload.get("relationship") or "").strip()
        normalized = raw_relation.upper().replace("-", "_").replace(" ", "_")
        if not normalized or normalized == "NONE":
            return None
        if normalized in RELATION_ALIASES:
            normalized = RELATION_ALIASES[normalized]
        if normalized in ALLOWED_RELATIONSHIPS:
            return normalized

        if "INSPIRED" in normalized or "INFLUENC" in normalized:
            return "INFLUENCED_BY"
        if "DISCUSS" in normalized or "RELAT" in normalized or "ASSOCIAT" in normalized:
            return "RELATED_TO"
        if "BUILD" in normalized or "EXTEND" in normalized or "EXPAND" in normalized:
            return "EXPANDS"
        if "CONTRADICT" in normalized or "OPPOS" in normalized:
            return "CONTRADICTS"
        return None

    def _parse_confidence(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return round(max(0.0, min(1.0, float(value))), 3)
        except (TypeError, ValueError):
            return None
