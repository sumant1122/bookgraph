from __future__ import annotations

from dataclasses import dataclass

from app.agents.chat_agent import ChatAgent
from app.graph.chat_repo import ChatGraphRepository


@dataclass(slots=True)
class ChatResult:
    answer: str
    confidence: float
    citations: list[str]
    evidence_nodes: list[dict]
    evidence_edges: list[dict]
    context_size: dict[str, int]
    mode: str
    provider: str
    fallback_reason: str | None


class ChatService:
    def __init__(self, graph_repo: ChatGraphRepository, chat_agent: ChatAgent) -> None:
        self._graph_repo = graph_repo
        self._chat_agent = chat_agent

    def ask(self, question: str, scope: str, k: int) -> ChatResult:
        safe_k = max(5, min(100, int(k)))
        subgraph = self._graph_repo.get_chat_subgraph(question=question, scope=scope, k=safe_k)
        nodes = subgraph["nodes"]
        edges = subgraph["edges"]
        graph_stats = self._graph_repo.get_graph_stats()
        output = self._chat_agent.answer(question=question, nodes=nodes, edges=edges, graph_stats=graph_stats)

        citation_set = set(output.get("citations", []))
        cited_nodes = [node for node in nodes if node.get("id") in citation_set] if citation_set else nodes[:8]

        return ChatResult(
            answer=output.get("answer", ""),
            confidence=float(output.get("confidence", 0.5)),
            citations=list(citation_set)[:12],
            evidence_nodes=cited_nodes[:20],
            evidence_edges=edges[:40],
            context_size={"nodes": len(nodes), "edges": len(edges)},
            mode=str(output.get("mode") or "fallback"),
            provider=str(output.get("provider") or "none"),
            fallback_reason=(str(output.get("fallback_reason")) if output.get("fallback_reason") else None),
        )
