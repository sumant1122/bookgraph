from __future__ import annotations

import unittest

from app.agents.exploration.reading_path_agent import ReadingPathAgent


class FakeDiscoveryRepo:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def get_concept_reading_paths(self, limit_concepts: int = 8, path_len: int = 4):
        return [
            {
                "concept": "Startup Strategy",
                "books": [
                    {"title": "The Lean Startup", "publish_year": 2011, "relation_score": 5},
                    {"title": "The Innovator's Dilemma", "publish_year": 1997, "relation_score": 3},
                    {"title": "Zero to One", "publish_year": 2014, "relation_score": 4},
                ],
            }
        ]

    def save_reading_path(self, concept: str, books: list[str], explanation: str, signature: str):
        row = {
            "concept": concept,
            "books": books,
            "explanation": explanation,
            "signature": signature,
            "created_at": "2026-03-08T00:00:00+00:00",
        }
        self.saved.append(row)
        return row


class ReadingPathAgentTests(unittest.TestCase):
    def test_run_generates_and_saves_paths(self) -> None:
        repo = FakeDiscoveryRepo()
        agent = ReadingPathAgent(repo=repo, llm_client=None)

        result = agent.run()

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["books"],
            ["The Innovator's Dilemma", "The Lean Startup", "Zero to One"],
        )
        self.assertIn("Startup Strategy", result[0]["explanation"])
