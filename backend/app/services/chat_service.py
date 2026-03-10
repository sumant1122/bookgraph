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
    cypher_query: str | None


class ChatService:
    def __init__(self, graph_repo: ChatGraphRepository, chat_agent: ChatAgent) -> None:
        self._graph_repo = graph_repo
        self._chat_agent = chat_agent

    def ask(self, question: str, scope: str, k: int) -> ChatResult:
        graph_stats = self._graph_repo.get_graph_stats()

        # Step 1: Try to plan and execute a structural Cypher query
        cypher_query = self._chat_agent.plan_query(question, graph_stats)
        if cypher_query:
            try:
                query_results = self._graph_repo.execute_read_query(cypher_query)
                output = self._chat_agent.answer_with_results(
                    question=question,
                    query=cypher_query,
                    results=query_results,
                )
                return self._build_result(output, [], [], cypher_query=cypher_query)
            except Exception as exc:
                # Log or handle error, then fallback
                pass

        # Step 2: Fallback to keyword-based subgraph retrieval
        safe_k = max(5, min(100, int(k)))
        subgraph = self._graph_repo.get_chat_subgraph(question=question, scope=scope, k=safe_k)
        nodes = subgraph["nodes"]
        edges = subgraph["edges"]
        output = self._chat_agent.answer(question=question, nodes=nodes, edges=edges, graph_stats=graph_stats)

        return self._build_result(output, nodes, edges)

    async def stream_ask(self, question: str, scope: str, k: int) -> Any:
        """
        Streams a natural language answer based on the graph context.
        Note: For streaming, we currently skip the complex Cypher planning loop 
        to ensure low latency and continuous output.
        """
        safe_k = max(5, min(100, int(k)))
        subgraph = self._graph_repo.get_chat_subgraph(question=question, scope=scope, k=safe_k)
        nodes = subgraph["nodes"]
        edges = subgraph["edges"]
        graph_stats = self._graph_repo.get_graph_stats()

        async for token in self._chat_agent.stream_answer(
            question=question, 
            nodes=nodes, 
            edges=edges, 
            graph_stats=graph_stats
        ):
            yield token

    def _build_result(self, output: dict[str, Any], nodes: list[dict], edges: list[dict], cypher_query: str | None = None) -> ChatResult:
        citation_set = set(output.get("citations", []))
        # If we have nodes in context, find cited ones. Otherwise, use what's in citations if possible.
        cited_nodes = [node for node in nodes if node.get("id") in citation_set] if nodes else []

        return ChatResult(
            answer=output.get("answer", ""),
            confidence=float(output.get("confidence", 0.5)),
            citations=list(citation_set)[:12],
            evidence_nodes=cited_nodes[:20] if cited_nodes else [],
            evidence_edges=edges[:40] if edges else [],
            context_size={"nodes": len(nodes), "edges": len(edges)},
            mode=str(output.get("mode") or "fallback"),
            provider=str(output.get("provider") or "none"),
            fallback_reason=(str(output.get("fallback_reason")) if output.get("fallback_reason") else None),
            cypher_query=cypher_query,
        )
