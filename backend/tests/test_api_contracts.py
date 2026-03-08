from __future__ import annotations

import sys
import types
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

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

from app.api.deps import get_graph_repo
from app.api.routes import router


class FakeGraphRepo:
    def search_graph_nodes(self, query: str, limit: int = 25, node_type: str | None = None):
        return [
            {"id": "book::1", "label": "Clean Code", "type": "book", "properties": {"title": "Clean Code"}},
            {"id": "concept::1", "label": "Refactoring", "type": "concept", "properties": {"name": "Refactoring"}},
        ]

    def get_focus_subgraph(self, node_id: str, depth: int = 1, limit: int = 120):
        return {
            "nodes": [{"id": node_id, "label": "Clean Code", "type": "book", "properties": {}}],
            "edges": [],
        }

    def get_node_details(self, node_id: str):
        return {
            "id": node_id,
            "label": "Clean Code",
            "type": "book",
            "properties": {"title": "Clean Code"},
            "degree": 2,
            "neighbors": [{"id": "book::2", "label": "Design Patterns", "type": "book", "relation": "RELATED_TO"}],
        }

    def list_graph_insights(self, limit: int = 30):
        return [
            {
                "id": "insight-1",
                "type": "cluster",
                "title": "Systems Cluster",
                "description": "A systems-oriented cluster.",
                "node_ids": ["book::1", "book::2"],
                "related_nodes": ["Thinking in Systems", "The Fifth Discipline"],
                "created_at": "2026-03-08T00:00:00+00:00",
            }
        ]

    def get_graph_insight(self, insight_id: str):
        if insight_id != "insight-1":
            return None
        return {
            "id": "insight-1",
            "type": "cluster",
            "title": "Systems Cluster",
            "description": "A systems-oriented cluster.",
            "node_ids": ["book::1", "book::2"],
            "related_nodes": ["Thinking in Systems", "The Fifth Discipline"],
            "created_at": "2026-03-08T00:00:00+00:00",
        }

    def list_reading_paths(self, limit: int = 30):
        return [
            {
                "concept": "Startup Strategy",
                "books": ["The Innovator's Dilemma", "Zero to One", "The Lean Startup"],
                "explanation": "Progresses from disruption theory to execution frameworks.",
                "created_at": "2026-03-08T00:00:00+00:00",
            }
        ]

    def list_knowledge_gaps(self, limit: int = 30):
        return [
            {
                "gap": "Behavioral Economics",
                "reason": "Startup books reference psychology but decision theory coverage is sparse.",
                "candidate_books": ["Thinking, Fast and Slow", "Predictably Irrational"],
                "created_at": "2026-03-08T00:00:00+00:00",
            }
        ]


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_graph_repo] = lambda: FakeGraphRepo()
        self.client = TestClient(app)

    def test_discoveries_response_contains_node_ids(self) -> None:
        response = self.client.get("/discoveries")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["discoveries"][0]["node_ids"], ["book::1", "book::2"])
        self.assertEqual(payload["discoveries"][0]["related_nodes"][0], "Thinking in Systems")

    def test_graph_search_returns_nodes(self) -> None:
        response = self.client.get("/graph/search?q=clean&type=book")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["nodes"][0]["id"], "book::1")

    def test_graph_node_details_returns_payload(self) -> None:
        response = self.client.get("/graph/nodes/book::1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["degree"], 2)
        self.assertEqual(payload["neighbors"][0]["label"], "Design Patterns")

    def test_reading_paths_endpoint_returns_data(self) -> None:
        response = self.client.get("/reading-paths")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["paths"][0]["concept"], "Startup Strategy")
        self.assertEqual(payload["paths"][0]["books"][0], "The Innovator's Dilemma")

    def test_knowledge_gaps_endpoint_returns_data(self) -> None:
        response = self.client.get("/knowledge-gaps")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["gaps"][0]["gap"], "Behavioral Economics")
        self.assertEqual(payload["gaps"][0]["candidate_books"][0], "Thinking, Fast and Slow")
