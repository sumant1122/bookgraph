from __future__ import annotations

from typing import Any

from app.agents.insight_agent import InsightAgent
from app.graph.neo4j_client import GraphRepository


class GraphInsightEngine:
    def __init__(self, repo: GraphRepository, insight_agent: InsightAgent | None = None) -> None:
        self._repo = repo
        self._insight_agent = insight_agent or InsightAgent()

    def get_central_books(self) -> dict[str, object]:
        ranked = self._repo.get_central_books()
        titles = [row["title"] for row in ranked if row.get("title")]
        return {
            "central_books": ranked,
            "summary": (
                f"Your most influential books are: {', '.join(titles[:3])}"
                if titles
                else "No influential books identified yet."
            ),
        }

    def detect_clusters(self) -> dict[str, object]:
        clusters = self._repo.detect_clusters()
        return {"clusters": clusters, "cluster_count": len(clusters)}

    def detect_missing_topics(self) -> dict[str, object]:
        missing = self._repo.detect_missing_topics()
        return {
            "missing_topics": missing,
            "summary": "Topics with low coverage can guide your next reading additions.",
        }

    def get_graph_stats(self) -> dict[str, Any]:
        stats = self._repo.get_graph_stats()
        return {
            **stats,
            "summary": (
                f"Graph has {stats['books']} books, {stats['authors']} authors, "
                f"{stats['concepts']} concepts, and {stats['book_edges']} cross-book edges."
            ),
        }

    def get_coverage(self) -> dict[str, Any]:
        return {
            "top_fields": self._repo.get_field_coverage(),
            "top_concepts": self._repo.get_top_concepts(),
            "unlinked_books": self._repo.get_unlinked_books(),
        }

    def generate_recommendations(
        self,
        central_books: dict[str, Any],
        missing_topics: dict[str, Any],
        coverage: dict[str, Any],
    ) -> list[str]:
        recommendations: list[str] = []
        unlinked = coverage.get("unlinked_books", [])
        if unlinked:
            unlinked_titles = [row["title"] for row in unlinked[:3] if row.get("title")]
            recommendations.append(
                f"Create relationship links for isolated books: {', '.join(unlinked_titles)}."
            )
        sparse_topics = missing_topics.get("missing_topics", [])
        if sparse_topics:
            sparse_names = [row["field"] for row in sparse_topics[:3] if row.get("field")]
            recommendations.append(
                f"Add books in underrepresented topics: {', '.join(sparse_names)}."
            )
        ranked = central_books.get("central_books", [])
        if ranked:
            top_title = ranked[0].get("title")
            if top_title:
                recommendations.append(
                    f"Use '{top_title}' as a seed and add adjacent books to deepen that cluster."
                )
        if not recommendations:
            recommendations.append("Add at least 5 books across different fields to improve insight quality.")
        return recommendations

    def build_insight_bundle(self) -> dict[str, Any]:
        central = self.get_central_books()
        clusters = self.detect_clusters()
        missing = self.detect_missing_topics()
        stats = self.get_graph_stats()
        coverage = self.get_coverage()
        recommendations = self.generate_recommendations(central, missing, coverage)

        llm_payload = {
            "central_books": central,
            "clusters": clusters,
            "missing_topics": missing,
            "graph_stats": stats,
            "coverage": coverage,
            "recommendations": recommendations,
        }
        narrative = self._insight_agent.synthesize(llm_payload)

        return {
            "central_books": central,
            "clusters": clusters,
            "missing_topics": missing,
            "graph_stats": stats,
            "coverage": coverage,
            "recommendations": recommendations,
            "narrative": narrative,
        }
