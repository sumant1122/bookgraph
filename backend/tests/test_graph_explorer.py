from __future__ import annotations

import sys
import types
import unittest
from typing import Any

# Lightweight test stub to allow importing modules without installed neo4j package.
if "neo4j" not in sys.modules:
    neo4j_stub = types.ModuleType("neo4j")

    class GraphDatabase:  # noqa: D401
        @staticmethod
        def driver(*args, **kwargs):  # noqa: ANN002, ANN003
            return None

    neo4j_stub.GraphDatabase = GraphDatabase
    neo4j_exceptions_stub = types.ModuleType("neo4j.exceptions")

    class Neo4jError(Exception):
        pass

    class CypherSyntaxError(Exception):
        pass

    neo4j_exceptions_stub.Neo4jError = Neo4jError
    neo4j_exceptions_stub.CypherSyntaxError = CypherSyntaxError
    sys.modules["neo4j"] = neo4j_stub
    sys.modules["neo4j.exceptions"] = neo4j_exceptions_stub

from app.agents.exploration.graph_explorer import GraphExplorerAgent


class FakeRepo:
    def __init__(self) -> None:
        self.saved_payloads: list[dict[str, Any]] = []

    def detect_clusters(self) -> list[dict[str, Any]]:
        return [{"communityId": "cluster-a", "books": ["Clean Code", "Design Patterns"]}]

    def get_book_nodes_by_titles(self, titles: list[str]) -> list[dict[str, Any]]:
        return [{"id": f"book::{title}", "label": title, "type": "book"} for title in titles]

    def get_central_books(self, limit: int = 5) -> list[dict[str, Any]]:
        return [{"title": "Clean Code", "score": 0.99}]

    def get_cross_field_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        return [
            {
                "concept": "Systems Thinking",
                "fields": ["Software Engineering", "Startup Strategy"],
                "fieldCount": 2,
            }
        ]

    def get_concept_nodes_by_names(self, concepts: list[str]) -> list[dict[str, Any]]:
        return [{"id": f"concept::{name}", "label": name, "type": "concept"} for name in concepts]

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        return [{"id": f"field::{name}", "label": name, "type": "field"} for name in fields]

    def save_graph_insight(
        self,
        insight_type: str,
        title: str,
        description: str,
        node_ids: list[str],
        related_nodes: list[str],
        signature: str,
    ) -> dict[str, Any]:
        payload = {
            "id": f"insight::{len(self.saved_payloads) + 1}",
            "type": insight_type,
            "title": title,
            "description": description,
            "node_ids": node_ids,
            "related_nodes": related_nodes,
            "signature": signature,
            "created_at": "2026-03-08T00:00:00+00:00",
        }
        self.saved_payloads.append(payload)
        return payload


class GraphExplorerTests(unittest.TestCase):
    def test_graph_explorer_persists_discoveries_with_node_ids(self) -> None:
        repo = FakeRepo()
        agent = GraphExplorerAgent(repo=repo, llm_client=None)

        discoveries = agent.run()

        self.assertEqual(len(discoveries), 3)
        self.assertEqual(len(repo.saved_payloads), 3)
        for payload in repo.saved_payloads:
            self.assertTrue(payload["node_ids"])
            self.assertTrue(all("::" in node_id for node_id in payload["node_ids"]))
            self.assertTrue(payload["related_nodes"])
