from __future__ import annotations

from app.graph.neo4j_client import GraphRepository


class GraphInsightEngine:
    def __init__(self, repo: GraphRepository) -> None:
        self._repo = repo

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

