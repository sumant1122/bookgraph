from __future__ import annotations

from typing import Any

from app.agents.llm_client import LLMClient, LLMError


class ChatAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def plan_query(self, question: str, graph_stats: dict[str, Any]) -> str | None:
        """
        Generates a Cypher query to answer the user's question based on the graph schema.
        Returns None if it decides a simple keyword search is better or if it fails.
        """
        if not self._llm_client:
            return None

        schema_prompt = (
            "Labels: Book (title, publish_year, description), Paper (title, publish_year, description), "
            "Author (name), Concept (name), Field (name).\n"
            "Relationships: WRITTEN_BY (from Book/Paper to Author), MENTIONS (from Book/Paper to Concept), "
            "BELONGS_TO (from Book/Paper to Field), RELATED_TO, INFLUENCED_BY, CONTRADICTS, EXPANDS (between Book/Paper nodes).\n"
            f"Current Stats: {graph_stats}"
        )

        system_prompt = (
            "You are a Cypher query expert. Convert the user question into a valid READ-ONLY Neo4j Cypher query. "
            "Return strict JSON with one key: 'cypher'. "
            "Do NOT use write keywords like CREATE, MERGE, SET. Use elementId(n) for node IDs. "
            "If the question cannot be answered with a structural query, return an empty string for 'cypher'."
        )

        user_prompt = (
            f"Schema:\n{schema_prompt}\n\n"
            f"User Question: {question}\n\n"
            "Generate a Cypher query that finds the relevant nodes/edges to answer this question. "
            "Focus on structural relationships (e.g., 'at least 2 fields', 'contradicts x')."
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            cypher = str(payload.get("cypher") or "").strip()
            return cypher if cypher else None
        except LLMError:
            return None

    def answer_with_results(
        self,
        question: str,
        query: str,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Takes the raw results of a Cypher query and turns them into a natural language answer.
        """
        if not self._llm_client:
            return self._fallback(question, [], [], provider="none", reason="no_llm_client")

        system_prompt = (
            "You are a knowledge graph assistant. Use the provided Cypher query results to answer the user's question. "
            "Return strict JSON with keys: answer (string), confidence (number 0..1), citations (array of node ids)."
        )

        user_prompt = (
            f"Question: {question}\n\n"
            f"Cypher Query Used: {query}\n\n"
            f"Query Results: {results[:50]}\n\n"
            "Provide a clear, detailed answer based ONLY on these results. If no results were found, explain that."
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return {
                "answer": str(payload.get("answer") or "").strip(),
                "confidence": self._normalize_confidence(payload.get("confidence")),
                "citations": [str(x) for x in payload.get("citations", [])][:12],
                "mode": "cypher_reasoning",
                "provider": getattr(self._llm_client, "provider", "unknown"),
                "fallback_reason": None,
            }
        except LLMError as exc:
            return self._fallback(question, [], [], provider="error", reason=str(exc))

    def answer(
        self,
        *,
        question: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        graph_stats: dict[str, Any],
    ) -> dict[str, Any]:
        provider = getattr(self._llm_client, "provider", "none") if self._llm_client else "none"
        if not self._llm_client:
            return self._fallback(question, nodes, edges, provider=provider, reason="no_llm_client")

        context = {
            "graph_stats": graph_stats,
            "nodes": nodes[:120],
            "edges": edges[:220],
        }
        system_prompt = (
            "You answer user questions about a book knowledge graph. "
            "Use only provided graph context. Return strict JSON with keys: "
            "answer (string), confidence (number 0..1), citations (array of node ids)."
        )
        user_prompt = f"Question: {question}\n\nGraph context:\n{context}"
        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return {
                "answer": str(payload.get("answer") or "").strip(),
                "confidence": self._normalize_confidence(payload.get("confidence")),
                "citations": [str(x) for x in payload.get("citations", [])][:12],
                "mode": "llm",
                "provider": provider,
                "fallback_reason": None,
            }
        except LLMError as exc:
            return self._fallback(
                question,
                nodes,
                edges,
                provider=provider,
                reason=f"llm_error: {str(exc)[:240]}",
            )

    async def stream_answer(
        self,
        question: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        graph_stats: dict[str, Any],
    ) -> Any:
        """
        Streams a natural language answer based on the provided graph context.
        Note: Metadata like citations and confidence aren't easily streamed in the same pass,
        so this focus on the 'answer' text itself.
        """
        if not self._llm_client:
            yield "No LLM client available for streaming."
            return

        context_prompt = (
            f"Graph Context:\nNodes: {nodes[:30]}\nEdges: {edges[:50]}\n"
            f"Graph Stats: {graph_stats}"
        )

        system_prompt = (
            "You are a helpful knowledge graph assistant. Answer the user's question clearly "
            "based ONLY on the provided graph context. Be concise and professional."
        )

        user_prompt = f"{context_prompt}\n\nUser Question: {question}"

        try:
            async for token in self._llm_client.async_stream(system_prompt=system_prompt, user_prompt=user_prompt):
                yield token
        except LLMError as exc:
            yield f"\n[Streaming Error: {str(exc)}]"

    def _fallback(
        self,
        question: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        *,
        provider: str,
        reason: str,
    ) -> dict[str, Any]:
        books = [n for n in nodes if n.get("type") == "book"]
        concepts = [n for n in nodes if n.get("type") == "concept"]
        mentions = [e for e in edges if e.get("type") == "MENTIONS"]
        answer = (
            f"I analyzed {len(nodes)} nodes and {len(edges)} edges for your question: '{question}'. "
            f"The subgraph contains {len(books)} books, {len(concepts)} concepts, and {len(mentions)} mention links."
        )
        citations = [str(n["id"]) for n in books[:3] if n.get("id")]
        return {
            "answer": answer,
            "confidence": 0.45,
            "citations": citations,
            "mode": "fallback",
            "provider": provider,
            "fallback_reason": reason,
        }

    def _normalize_confidence(self, value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, parsed))
