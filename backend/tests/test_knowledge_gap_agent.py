from __future__ import annotations

import unittest

from app.agents.exploration.knowledge_gap_agent import KnowledgeGapAgent


class FakeDiscoveryRepo:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def detect_missing_topics(self, threshold: int = 1):
        return [
            {"field": "Behavioral Economics", "bookCount": 0},
            {"field": "Decision Theory", "bookCount": 1},
        ]

    def detect_sparse_bridges(self, limit: int = 8, max_fields: int = 10):
        return [
            {"field_a": "Behavioral Economics", "field_b": "Startup Strategy", "books_a": 0, "books_b": 5},
            {"field_a": "Decision Theory", "field_b": "Product Management", "books_a": 1, "books_b": 6},
        ]

    def get_books_for_fields(self, fields: list[str], limit: int = 5):
        if "Startup Strategy" in fields:
            return ["The Lean Startup", "Zero to One"]
        return ["The Mom Test"]

    def save_knowledge_gap(
        self,
        gap: str,
        reason: str,
        candidate_books: list[str],
        signature: str,
    ):
        row = {
            "gap": gap,
            "reason": reason,
            "candidate_books": candidate_books,
            "signature": signature,
            "created_at": "2026-03-08T00:00:00+00:00",
        }
        self.saved.append(row)
        return row


class KnowledgeGapAgentTests(unittest.TestCase):
    def test_run_persists_gap_records(self) -> None:
        repo = FakeDiscoveryRepo()
        agent = KnowledgeGapAgent(repo=repo, llm_client=None)

        result = agent.run()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["gap"], "Behavioral Economics")
        self.assertEqual(result[0]["candidate_books"][0], "The Lean Startup")
        self.assertIn("Coverage is low", result[0]["reason"])
