from __future__ import annotations

from datetime import datetime, timezone
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
        evidence_nodes = self._repo.get_book_nodes_by_titles(titles[:5])
        evidence_edges = self._repo.get_book_relationship_edges(limit=20)
        return {
            "central_books": ranked,
            "summary": (
                f"Your most influential books are: {', '.join(titles[:3])}"
                if titles
                else "No influential books identified yet."
            ),
            "evidence": {
                "nodes": evidence_nodes,
                "edges": evidence_edges,
            },
        }

    def detect_clusters(self) -> dict[str, object]:
        clusters = self._repo.detect_clusters()
        top_books = clusters[0]["books"][:5] if clusters else []
        return {
            "clusters": clusters,
            "cluster_count": len(clusters),
            "evidence": {
                "nodes": self._repo.get_book_nodes_by_titles(top_books),
                "edges": self._repo.get_book_relationship_edges(limit=20),
            },
        }

    def detect_missing_topics(self) -> dict[str, object]:
        missing = self._repo.detect_missing_topics()
        field_names = [row["field"] for row in missing[:6] if row.get("field")]
        return {
            "missing_topics": missing,
            "summary": "Topics with low coverage can guide your next reading additions.",
            "evidence": {
                "nodes": self._repo.get_field_nodes_by_names(field_names),
                "edges": [],
            },
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

    def compute_quality_scores(
        self,
        stats: dict[str, Any],
        clusters: dict[str, Any],
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        books = int(stats.get("books", 0))
        density = float(stats.get("book_relationship_density", 0.0))
        unlinked = len(coverage.get("unlinked_books", []))
        largest_cluster = 0
        if clusters.get("clusters"):
            largest_cluster = len(clusters["clusters"][0].get("books", []))

        relationship_quality = max(0, min(100, int((density * 250) + (books * 2))))
        concept_coverage = max(0, min(100, int((int(stats.get("concepts", 0)) / max(1, books)) * 20)))
        cluster_cohesion = max(0, min(100, int((largest_cluster / max(1, books)) * 100)))
        link_completeness = max(0, min(100, int((1 - (unlinked / max(1, books))) * 100)))
        overall = int((relationship_quality + concept_coverage + cluster_cohesion + link_completeness) / 4)

        return {
            "overall_score": overall,
            "breakdown": {
                "relationship_quality": relationship_quality,
                "concept_coverage": concept_coverage,
                "cluster_cohesion": cluster_cohesion,
                "link_completeness": link_completeness,
            },
        }

    def build_recommendations(
        self,
        central_books: dict[str, Any],
        missing_topics: dict[str, Any],
        coverage: dict[str, Any],
        sparse_bridges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        unlinked = coverage.get("unlinked_books", [])
        if unlinked:
            unlinked_titles = [row["title"] for row in unlinked[:3] if row.get("title")]
            recommendations.append(
                {
                    "action": f"Create relationship links for isolated books: {', '.join(unlinked_titles)}.",
                    "effort": "Quick win",
                    "type": "connectivity",
                }
            )
        sparse_topics = missing_topics.get("missing_topics", [])
        if sparse_topics:
            sparse_names = [row["field"] for row in sparse_topics[:3] if row.get("field")]
            recommendations.append(
                {
                    "action": f"Add books in underrepresented topics: {', '.join(sparse_names)}.",
                    "effort": "Medium",
                    "type": "coverage",
                }
            )
        ranked = central_books.get("central_books", [])
        if ranked:
            top_title = ranked[0].get("title")
            if top_title:
                recommendations.append(
                    {
                        "action": f"Use '{top_title}' as a seed and add adjacent books to deepen that cluster.",
                        "effort": "Deep work",
                        "type": "cluster-growth",
                    }
                )
        if sparse_bridges:
            bridge = sparse_bridges[0]
            recommendations.append(
                {
                    "action": f"Add bridge books that connect '{bridge['field_a']}' and '{bridge['field_b']}'.",
                    "effort": "Medium",
                    "type": "bridge-gap",
                }
            )
        if not recommendations:
            recommendations.append(
                {
                    "action": "Add at least 5 books across different fields to improve insight quality.",
                    "effort": "Medium",
                    "type": "growth",
                }
            )
        return recommendations

    def build_time_delta(self, current_stats: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
        if not previous:
            return {
                "has_previous": False,
                "summary": "No historical snapshot yet. This run establishes the baseline.",
                "delta": {},
                "previous_snapshot_at": None,
            }
        delta = {
            "books": int(current_stats.get("books", 0)) - int(previous.get("books", 0)),
            "authors": int(current_stats.get("authors", 0)) - int(previous.get("authors", 0)),
            "concepts": int(current_stats.get("concepts", 0)) - int(previous.get("concepts", 0)),
            "fields": int(current_stats.get("fields", 0)) - int(previous.get("fields", 0)),
            "book_edges": int(current_stats.get("book_edges", 0)) - int(previous.get("book_edges", 0)),
            "density": round(
                float(current_stats.get("book_relationship_density", 0.0))
                - float(previous.get("book_relationship_density", 0.0)),
                4,
            ),
        }
        return {
            "has_previous": True,
            "summary": (
                f"Since last snapshot: books {delta['books']:+d}, concepts {delta['concepts']:+d}, "
                f"book edges {delta['book_edges']:+d}, density {delta['density']:+.4f}."
            ),
            "delta": delta,
            "previous_snapshot_at": previous.get("created_at"),
        }

    def build_insight_bundle(self) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        central = self.get_central_books()
        clusters = self.detect_clusters()
        missing = self.detect_missing_topics()
        stats = self.get_graph_stats()
        coverage = self.get_coverage()
        sparse_bridges = self._repo.detect_sparse_bridges()
        overlap = self._repo.get_overlap_contradiction_summary()
        reading_paths = self._repo.get_field_reading_paths()
        field_dashboards = self._repo.get_field_dashboards()
        quality = self.compute_quality_scores(stats, clusters, coverage)
        previous_snapshots = self._repo.get_latest_insight_snapshots(limit=1)
        previous = previous_snapshots[0] if previous_snapshots else None
        time_delta = self.build_time_delta(stats, previous)
        recommendations = self.build_recommendations(central, missing, coverage, sparse_bridges)

        llm_payload = {
            "central_books": central,
            "clusters": clusters,
            "missing_topics": missing,
            "graph_stats": stats,
            "coverage": coverage,
            "quality_scores": quality,
            "time_delta": time_delta,
            "sparse_bridges": sparse_bridges,
            "overlap_contradiction": overlap,
            "reading_paths": reading_paths,
            "field_dashboards": field_dashboards,
            "recommendations": recommendations,
        }
        narrative = self._insight_agent.synthesize(llm_payload)
        self._repo.save_insight_snapshot(stats=stats, overall_score=quality["overall_score"])

        return {
            "central_books": central,
            "clusters": clusters,
            "missing_topics": missing,
            "graph_stats": stats,
            "coverage": coverage,
            "recommendations": recommendations,
            "narrative": narrative,
            "time_delta": time_delta,
            "quality_scores": quality,
            "reading_paths": reading_paths,
            "overlap_contradiction": overlap,
            "sparse_bridges": sparse_bridges,
            "field_dashboards": field_dashboards,
            "freshness": {
                "generated_at": generated_at,
                "confidence": {
                    "score": 0.75 if narrative.get("summary") else 0.55,
                    "label": "medium",
                },
                "context_size": {
                    "books": stats.get("books", 0),
                    "concepts": stats.get("concepts", 0),
                    "edges": stats.get("book_edges", 0),
                },
            },
        }
