from __future__ import annotations

from dataclasses import dataclass

from app.agents.llm_client import LLMClient, LLMError


@dataclass(slots=True)
class ConceptExtractionResult:
    concepts: list[str]
    fields: list[str]


class ConceptAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def extract(self, summary: str, fallback_subjects: list[str] | None = None) -> ConceptExtractionResult:
        fallback_subjects = fallback_subjects or []
        summary = (summary or "").strip()
        if not summary and not fallback_subjects:
            return ConceptExtractionResult(concepts=[], fields=[])

        if not self._llm_client:
            return self._heuristic_extract(summary, fallback_subjects)

        system_prompt = (
            "You extract concepts from items. Return strict JSON with keys: "
            "concepts (string array) and fields (string array)."
        )
        user_prompt = (
            "Extract important concepts from the following item.\n\n"
            f"Item summary:\n{summary}\n\n"
            "Return JSON:\n"
            '{"concepts": [], "fields": []}'
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            concepts = [str(x).strip() for x in payload.get("concepts", []) if str(x).strip()]
            fields = [str(x).strip() for x in payload.get("fields", []) if str(x).strip()]
            if concepts or fields:
                return ConceptExtractionResult(concepts=concepts[:12], fields=fields[:6])
        except LLMError:
            pass

        return self._heuristic_extract(summary, fallback_subjects)

    def _heuristic_extract(self, summary: str, subjects: list[str]) -> ConceptExtractionResult:
        tokens = [segment.strip() for segment in subjects if segment.strip()]
        concepts = tokens[:8]
        field_candidates = [t for t in tokens if "engineering" in t.lower() or "science" in t.lower()]
        fields = field_candidates[:4] or (tokens[:2] if tokens else [])
        if not concepts and summary:
            words = [w.strip(".,:;!?()[]{}").lower() for w in summary.split()]
            concepts = [w for w in words if len(w) > 7][:8]
        return ConceptExtractionResult(concepts=concepts, fields=fields)

    async def async_extract(
        self, summary: str, fallback_subjects: list[str] | None = None
    ) -> ConceptExtractionResult:
        """Async version — uses httpx.AsyncClient, no thread required."""
        fallback_subjects = fallback_subjects or []
        summary = (summary or "").strip()
        if not summary and not fallback_subjects:
            return ConceptExtractionResult(concepts=[], fields=[])

        if not self._llm_client or not hasattr(self._llm_client, "async_generate_json"):
            return self._heuristic_extract(summary, fallback_subjects)

        system_prompt = (
            "You extract concepts from items. Return strict JSON with keys: "
            "concepts (string array) and fields (string array)."
        )
        user_prompt = (
            "Extract important concepts from the following item.\n\n"
            f"Item summary:\n{summary}\n\n"
            "Return JSON:\n"
            '{"concepts": [], "fields": []}'
        )
        try:
            payload = await self._llm_client.async_generate_json(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            concepts = [str(x).strip() for x in payload.get("concepts", []) if str(x).strip()]
            fields = [str(x).strip() for x in payload.get("fields", []) if str(x).strip()]
            if concepts or fields:
                return ConceptExtractionResult(concepts=concepts[:12], fields=fields[:6])
        except LLMError:
            pass
        return self._heuristic_extract(summary, fallback_subjects)
