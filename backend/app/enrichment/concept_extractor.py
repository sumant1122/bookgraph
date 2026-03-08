from app.agents.concept_agent import ConceptAgent, ConceptExtractionResult


class ConceptExtractor:
    """Thin enrichment wrapper to keep orchestration logic out of API handlers."""

    def __init__(self, concept_agent: ConceptAgent) -> None:
        self._concept_agent = concept_agent

    def run(self, summary: str, fallback_subjects: list[str]) -> ConceptExtractionResult:
        return self._concept_agent.extract(summary, fallback_subjects=fallback_subjects)

