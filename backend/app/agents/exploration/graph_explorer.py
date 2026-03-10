from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any

from app.agents.llm_client import LLMClient, LLMError
from app.graph.exploration_repo import ExplorationGraphRepository


@dataclass(slots=True)
class GraphDiscovery:
    insight_type: str
    title: str
    description: str
    node_ids: list[str]
    related_nodes: list[str]
    signature: str


class GraphExplorerAgent:
    """
    Periodically scans the graph for high-value structures and stores discoveries.
    """

    def __init__(self, repo: ExplorationGraphRepository, llm_client: LLMClient | None = None) -> None:
        self._repo = repo
        self._llm_client = llm_client

    def run(self) -> list[dict[str, Any]]:
        discoveries: list[GraphDiscovery] = []
        discoveries.extend(self._build_cluster_discoveries())
        discoveries.extend(self._build_centrality_discoveries())
        discoveries.extend(self._build_cross_field_concept_discoveries())

        saved: list[dict[str, Any]] = []
        for discovery in discoveries:
            record = self._repo.save_graph_insight(
                insight_type=discovery.insight_type,
                title=discovery.title,
                description=discovery.description,
                node_ids=discovery.node_ids,
                related_nodes=discovery.related_nodes,
                signature=discovery.signature,
            )
            saved.append(record)
        return saved

    def _build_cluster_discoveries(self) -> list[GraphDiscovery]:
        clusters = self._repo.detect_clusters()[:4]
        output: list[GraphDiscovery] = []
        for cluster in clusters:
            items = [str(title) for title in cluster.get("items", []) if title][:6]
            if len(items) < 2:
                continue
            item_nodes = self._repo.get_nodes_by_titles(items)
            node_ids = [str(node.get("id")) for node in item_nodes if node.get("id")]
            related_nodes = [str(node.get("label")) for node in item_nodes if node.get("label")]
            if len(node_ids) < 2:
                continue
            community = str(cluster.get("communityId") or "cluster")
            title, description = self._describe_cluster(community, related_nodes)
            signature = self._signature("cluster", community, node_ids)
            output.append(
                GraphDiscovery(
                    insight_type="cluster",
                    title=title,
                    description=description,
                    node_ids=node_ids,
                    related_nodes=related_nodes,
                    signature=signature,
                )
            )
        return output

    def _build_centrality_discoveries(self) -> list[GraphDiscovery]:
        ranked = self._repo.get_central_items(limit=5)
        items = [str(row.get("title")) for row in ranked if row.get("title")][:5]
        if not items:
            return []
        item_nodes = self._repo.get_nodes_by_titles(items)
        node_ids = [str(node.get("id")) for node in item_nodes if node.get("id")]
        related_nodes = [str(node.get("label")) for node in item_nodes if node.get("label")]
        if not node_ids:
            return []
        title = "Central Items Driving The Graph"
        description = (
            f"These items are highly connected and likely shape many other topics: {', '.join(related_nodes[:3])}."
        )
        signature = self._signature("central", "items", node_ids)
        return [
            GraphDiscovery(
                insight_type="centrality",
                title=title,
                description=description,
                node_ids=node_ids,
                related_nodes=related_nodes,
                signature=signature,
            )
        ]

    def _build_cross_field_concept_discoveries(self) -> list[GraphDiscovery]:
        cross_field = self._repo.get_cross_field_concepts(limit=6)
        output: list[GraphDiscovery] = []
        for row in cross_field:
            concept = str(row.get("concept") or "").strip()
            if not concept:
                continue
            field_count = int(row.get("fieldCount") or 0)
            if field_count < 2:
                continue
            fields = [str(name) for name in row.get("fields", []) if name][:5]
            concept_nodes = self._repo.get_concept_nodes_by_names([concept])
            field_nodes = self._repo.get_field_nodes_by_names(fields)
            nodes = concept_nodes + field_nodes
            node_ids = [str(node.get("id")) for node in nodes if node.get("id")]
            related_nodes = [str(node.get("label")) for node in nodes if node.get("label")]
            if len(node_ids) < 2:
                continue
            title = f"Cross-Field Concept: {concept}"
            description = (
                f"'{concept}' appears across {field_count} fields ({', '.join(fields)}), "
                "making it a bridge concept for interdisciplinary reading."
            )
            signature = self._signature("cross_field_concept", concept, node_ids)
            output.append(
                GraphDiscovery(
                    insight_type="cross_field_concept",
                    title=title,
                    description=description,
                    node_ids=node_ids,
                    related_nodes=related_nodes,
                    signature=signature,
                )
            )
        return output

    def _describe_cluster(self, community: str, items: list[str]) -> tuple[str, str]:
        fallback_title = f"Cluster Discovery: {items[0]}"
        fallback_description = (
            f"This cluster groups related items such as {', '.join(items[:3])}, "
            "suggesting a shared intellectual theme."
        )
        if not self._llm_client:
            return fallback_title, fallback_description

        system_prompt = (
            "You analyze clusters in a knowledge graph. "
            "Return strict JSON with keys: title, description. "
            "Description should be concise and explain the intellectual theme."
        )
        user_prompt = (
            "You are analyzing a knowledge graph of items and concepts. "
            "Explain the significance of this cluster of nodes and what intellectual theme it represents.\n\n"
            f"Community: {community}\n"
            f"Items: {items}\n"
        )
        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            title = str(payload.get("title") or "").strip()[:120] or fallback_title
            description = str(payload.get("description") or "").strip()[:600] or fallback_description
            return title, description
        except LLMError:
            return fallback_title, fallback_description

    def _signature(self, kind: str, anchor: str, nodes: list[str]) -> str:
        raw = f"{kind}|{anchor}|{'|'.join(sorted(nodes))}"
        return sha1(raw.encode("utf-8")).hexdigest()
