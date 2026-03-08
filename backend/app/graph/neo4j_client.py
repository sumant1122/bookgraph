from __future__ import annotations

import json
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError, Neo4jError

from app.ingestion.openlibrary import BookMetadata


class GraphRepository:
    def __init__(self, uri: str, username: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self._driver.close()

    def ensure_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT book_title_unique IF NOT EXISTS FOR (b:Book) REQUIRE b.title IS UNIQUE",
            "CREATE CONSTRAINT author_name_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT concept_name_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT field_name_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT graph_insight_id_unique IF NOT EXISTS FOR (g:GraphInsight) REQUIRE g.id IS UNIQUE",
            "CREATE CONSTRAINT insight_bundle_name_unique IF NOT EXISTS FOR (i:InsightBundle) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT agent_job_name_unique IF NOT EXISTS FOR (j:AgentJob) REQUIRE j.name IS UNIQUE",
            "CREATE CONSTRAINT reading_path_signature_unique IF NOT EXISTS FOR (r:ReadingPath) REQUIRE r.signature IS UNIQUE",
            "CREATE CONSTRAINT knowledge_gap_signature_unique IF NOT EXISTS FOR (k:KnowledgeGap) REQUIRE k.signature IS UNIQUE",
        ]
        with self._driver.session() as session:
            for statement in constraints:
                session.run(statement).consume()

    def upsert_book(self, metadata: BookMetadata) -> None:
        query = """
        MERGE (b:Book {title: $title})
        SET b.publish_year = $publish_year,
            b.subjects = $subjects,
            b.description = $description,
            b.openlibrary_key = $openlibrary_key
        MERGE (a:Author {name: $author})
        MERGE (b)-[:WRITTEN_BY]->(a)
        WITH b, $subjects AS subjects
        UNWIND subjects AS subject
        MERGE (f:Field {name: subject})
        MERGE (b)-[:BELONGS_TO]->(f)
        RETURN b.title AS title
        """
        with self._driver.session() as session:
            session.run(
                query,
                title=metadata.title,
                publish_year=metadata.publish_year,
                subjects=metadata.subjects,
                description=metadata.description,
                openlibrary_key=metadata.openlibrary_key,
                author=metadata.author,
            ).consume()

    def add_concepts_and_fields(self, book_title: str, concepts: list[str], fields: list[str]) -> None:
        query = """
        MATCH (b:Book {title: $book_title})
        WITH b, $concepts AS concepts, $fields AS fields
        FOREACH (concept IN concepts |
            MERGE (c:Concept {name: concept})
            MERGE (b)-[:MENTIONS]->(c)
        )
        FOREACH (field IN fields |
            MERGE (f:Field {name: field})
            MERGE (b)-[:BELONGS_TO]->(f)
        )
        """
        with self._driver.session() as session:
            session.run(query, book_title=book_title, concepts=concepts, fields=fields).consume()

    def get_books_for_relationship_scan(
        self,
        exclude_title: str,
        limit: int,
        preferred_fields: list[str] | None = None,
        publish_year: int | None = None,
    ) -> list[dict[str, Any]]:
        preferred_fields = [str(field).lower() for field in (preferred_fields or []) if str(field).strip()]
        safe_publish_year = publish_year if publish_year is not None else 9999
        query = """
        MATCH (b:Book)
        WHERE b.title <> $exclude_title
        OPTIONAL MATCH (b)-[:BELONGS_TO]->(f:Field)
        WITH b, collect(DISTINCT toLower(f.name)) AS field_names, collect(DISTINCT f.name) AS original_fields
        WITH b, original_fields,
             size([field IN field_names WHERE field IN $preferred_fields]) AS overlap_score,
             abs(coalesce(b.publish_year, $safe_publish_year) - $safe_publish_year) AS year_distance
        RETURN b.title AS title,
               b.description AS description,
               b.publish_year AS publish_year,
               original_fields AS subjects
        ORDER BY overlap_score DESC, year_distance ASC, b.title ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            results = session.run(
                query,
                exclude_title=exclude_title,
                preferred_fields=preferred_fields,
                safe_publish_year=safe_publish_year,
                limit=limit,
            )
            return [record.data() for record in results]

    def add_book_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        confidence: float | None = None,
        reason: str | None = None,
        method: str | None = None,
    ) -> None:
        if relation == "BELONGS_TO_FIELD":
            relation = "BELONGS_TO"
        if relation not in {"RELATED_TO", "INFLUENCED_BY", "CONTRADICTS", "EXPANDS", "BELONGS_TO"}:
            return

        query = f"""
        MATCH (source:Book {{title: $source}}), (target:Book {{title: $target}})
        MERGE (source)-[r:{relation}]->(target)
        ON CREATE SET r.created_at = datetime()
        SET r.last_seen_at = datetime(),
            r.confidence = CASE WHEN $confidence IS NULL THEN r.confidence ELSE $confidence END,
            r.reason = CASE WHEN $reason IS NULL OR $reason = '' THEN r.reason ELSE $reason END,
            r.method = CASE WHEN $method IS NULL OR $method = '' THEN r.method ELSE $method END
        RETURN type(r) AS relation
        """
        with self._driver.session() as session:
            session.run(
                query,
                source=source,
                target=target,
                confidence=confidence,
                reason=reason,
                method=method,
            ).consume()

    def get_graph(self) -> dict[str, list[dict[str, Any]]]:
        nodes_query = """
        MATCH (n)
        WHERE NOT n:InsightSnapshot
          AND NOT n:GraphInsight
          AND NOT n:InsightBundle
          AND NOT n:AgentJob
          AND NOT n:ReadingPath
          AND NOT n:KnowledgeGap
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        """
        edges_query = """
        MATCH (a)-[r]->(b)
        WHERE NOT a:InsightSnapshot
          AND NOT b:InsightSnapshot
          AND NOT a:GraphInsight
          AND NOT b:GraphInsight
          AND NOT a:InsightBundle
          AND NOT b:InsightBundle
          AND NOT a:AgentJob
          AND NOT b:AgentJob
          AND NOT a:ReadingPath
          AND NOT b:ReadingPath
          AND NOT a:KnowledgeGap
          AND NOT b:KnowledgeGap
        RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type, properties(r) AS props
        """
        with self._driver.session() as session:
            nodes = [
                {
                    "id": row["id"],
                    "label": row["props"].get("title") or row["props"].get("name") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": self._to_json_safe(row["props"]),
                }
                for row in session.run(nodes_query).data()
            ]
            edges = [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "target": row["target"],
                    "type": row["type"],
                    "properties": self._to_json_safe(row["props"]),
                }
                for row in session.run(edges_query).data()
            ]
            return {"nodes": nodes, "edges": edges}

    def search_graph_nodes(
        self,
        query: str,
        limit: int = 25,
        node_type: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_query = (query or "").strip()
        type_map = {
            "book": "Book",
            "author": "Author",
            "concept": "Concept",
            "field": "Field",
        }
        label = type_map.get((node_type or "").strip().lower())
        cypher = """
        MATCH (n)
        WHERE NOT n:InsightSnapshot
          AND NOT n:GraphInsight
          AND NOT n:InsightBundle
          AND NOT n:AgentJob
          AND NOT n:ReadingPath
          AND NOT n:KnowledgeGap
          AND (
            $query = ''
            OR toLower(coalesce(n.title, n.name, '')) CONTAINS toLower($query)
          )
          AND ($label IS NULL OR $label IN labels(n))
        WITH n, toLower(coalesce(n.title, n.name, '')) AS search_label
        RETURN elementId(n) AS id,
               labels(n) AS labels,
               properties(n) AS props,
               search_label = toLower($query) AS exact_match
        ORDER BY exact_match DESC, coalesce(n.title, n.name, '') ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(
                cypher,
                query=safe_query,
                label=label,
                limit=max(1, min(100, limit)),
            ).data()
            return [
                {
                    "id": row["id"],
                    "label": row["props"].get("title") or row["props"].get("name") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": self._to_json_safe(row["props"]),
                }
                for row in rows
            ]

    def get_focus_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        limit: int = 120,
    ) -> dict[str, list[dict[str, Any]]]:
        safe_depth = max(1, min(2, depth))
        safe_limit = max(10, min(300, limit))
        node_ids_query = f"""
        MATCH (seed)
        WHERE elementId(seed) = $node_id
        MATCH path = (seed)-[:WRITTEN_BY|MENTIONS|BELONGS_TO|RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS*0..{safe_depth}]-(n)
        WITH collect(DISTINCT elementId(n)) AS node_ids
        RETURN node_ids[..$limit] AS node_ids
        """
        nodes_query = """
        UNWIND $node_ids AS node_id
        MATCH (n)
        WHERE elementId(n) = node_id
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        """
        edges_query = """
        UNWIND $node_ids AS node_id
        MATCH (a)
        WHERE elementId(a) = node_id
        MATCH (a)-[r]->(b)
        WHERE elementId(b) IN $node_ids
        RETURN DISTINCT elementId(r) AS id,
                        elementId(a) AS source,
                        elementId(b) AS target,
                        type(r) AS type,
                        properties(r) AS props
        LIMIT $edge_limit
        """
        with self._driver.session() as session:
            row = session.run(node_ids_query, node_id=node_id, limit=safe_limit).single()
            node_ids = [str(item) for item in (row.get("node_ids") or [])] if row else []
            if not node_ids:
                return {"nodes": [], "edges": []}
            nodes = [
                {
                    "id": item["id"],
                    "label": item["props"].get("title") or item["props"].get("name") or "Unknown",
                    "type": (item["labels"][0].lower() if item["labels"] else "unknown"),
                    "properties": self._to_json_safe(item["props"]),
                }
                for item in session.run(nodes_query, node_ids=node_ids).data()
            ]
            edges = [
                {
                    "id": item["id"],
                    "source": item["source"],
                    "target": item["target"],
                    "type": item["type"],
                    "properties": self._to_json_safe(item.get("props") or {}),
                }
                for item in session.run(
                    edges_query,
                    node_ids=node_ids,
                    edge_limit=max(50, safe_limit * 4),
                ).data()
            ]
            return {"nodes": nodes, "edges": edges}

    def get_node_details(self, node_id: str) -> dict[str, Any] | None:
        node_query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        LIMIT 1
        """
        neighbors_query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE NOT m:InsightSnapshot
          AND NOT m:GraphInsight
          AND NOT m:InsightBundle
          AND NOT m:AgentJob
          AND NOT m:ReadingPath
          AND NOT m:KnowledgeGap
        RETURN elementId(m) AS id,
               labels(m) AS labels,
               properties(m) AS props,
               type(r) AS relation
        LIMIT 40
        """
        with self._driver.session() as session:
            node = session.run(node_query, node_id=node_id).single()
            if not node:
                return None
            neighbors = [
                {
                    "id": row["id"],
                    "label": row["props"].get("title") or row["props"].get("name") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "relation": row.get("relation"),
                }
                for row in session.run(neighbors_query, node_id=node_id).data()
                if row.get("id")
            ]
            return {
                "id": node["id"],
                "label": node["props"].get("title") or node["props"].get("name") or "Unknown",
                "type": (node["labels"][0].lower() if node["labels"] else "unknown"),
                "properties": self._to_json_safe(node["props"]),
                "degree": len(neighbors),
                "neighbors": neighbors,
            }

    def _to_json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._to_json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        # Handles Neo4j temporal and other driver-specific types
        return str(value)

    def get_central_books(self, limit: int = 5) -> list[dict[str, Any]]:
        gds_query = """
        CALL gds.graph.project.cypher(
            'bookGraph',
            'MATCH (b:Book) RETURN id(b) AS id',
            'MATCH (a:Book)-[r]->(b:Book) RETURN id(a) AS source, id(b) AS target'
        )
        YIELD graphName
        CALL gds.pageRank.stream(graphName)
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).title AS title, score
        ORDER BY score DESC
        LIMIT $limit
        """
        cleanup_query = "CALL gds.graph.drop('bookGraph', false)"
        fallback_query = """
        MATCH (b:Book)
        OPTIONAL MATCH (b)-[r]-(:Book)
        WITH b, count(r) AS bookLinks
        OPTIONAL MATCH (b)-[:MENTIONS]->(c:Concept)
        WITH b, bookLinks, count(DISTINCT c) AS conceptLinks
        OPTIONAL MATCH (b)-[:BELONGS_TO]->(f:Field)
        WITH b, bookLinks, conceptLinks, count(DISTINCT f) AS fieldLinks
        RETURN b.title AS title, (bookLinks * 2.0 + conceptLinks * 1.0 + fieldLinks * 0.8) AS score
        ORDER BY score DESC
        LIMIT $limit
        """

        with self._driver.session() as session:
            try:
                rows = session.run(gds_query, limit=limit).data()
                session.run(cleanup_query).consume()
                return rows
            except (Neo4jError, CypherSyntaxError):
                return session.run(fallback_query, limit=limit).data()

    def detect_clusters(self) -> list[dict[str, Any]]:
        gds_query = """
        CALL gds.graph.project.cypher(
            'clusterGraph',
            'MATCH (b:Book) RETURN id(b) AS id',
            'MATCH (a:Book)-[r]->(b:Book) RETURN id(a) AS source, id(b) AS target'
        )
        YIELD graphName
        CALL gds.louvain.stream(graphName)
        YIELD nodeId, communityId
        RETURN communityId, collect(gds.util.asNode(nodeId).title) AS books
        ORDER BY size(books) DESC
        """
        cleanup_query = "CALL gds.graph.drop('clusterGraph', false)"
        fallback_query = """
        MATCH (b:Book)-[:BELONGS_TO]->(f:Field)
        RETURN f.name AS communityId, collect(DISTINCT b.title) AS books
        ORDER BY size(books) DESC
        """

        with self._driver.session() as session:
            try:
                rows = session.run(gds_query).data()
                session.run(cleanup_query).consume()
                return rows
            except (Neo4jError, CypherSyntaxError):
                return session.run(fallback_query).data()

    def detect_missing_topics(self, threshold: int = 1) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)
        OPTIONAL MATCH (b:Book)-[:BELONGS_TO]->(f)
        WITH f.name AS field, count(DISTINCT b) AS bookCount
        WHERE bookCount <= $threshold
        RETURN field, bookCount
        ORDER BY bookCount ASC, field ASC
        """
        with self._driver.session() as session:
            return session.run(query, threshold=threshold).data()

    def get_graph_stats(self) -> dict[str, Any]:
        query = """
        OPTIONAL MATCH (b:Book)
        WITH count(DISTINCT b) AS books
        OPTIONAL MATCH (a:Author)
        WITH books, count(DISTINCT a) AS authors
        OPTIONAL MATCH (c:Concept)
        WITH books, authors, count(DISTINCT c) AS concepts
        OPTIONAL MATCH (f:Field)
        WITH books, authors, concepts, count(DISTINCT f) AS fields
        OPTIONAL MATCH (:Book)-[r]->(:Book)
        WITH books, authors, concepts, fields, count(DISTINCT r) AS bookEdges
        RETURN books, authors, concepts, fields, bookEdges
        """
        with self._driver.session() as session:
            row = session.run(query).single()
            if not row:
                return {
                    "books": 0,
                    "authors": 0,
                    "concepts": 0,
                    "fields": 0,
                    "book_edges": 0,
                    "book_relationship_density": 0.0,
                }
            books = int(row["books"] or 0)
            edges = int(row["bookEdges"] or 0)
            max_directed_edges = max(1, books * max(books - 1, 1))
            density = float(edges / max_directed_edges) if books > 1 else 0.0
            return {
                "books": books,
                "authors": int(row["authors"] or 0),
                "concepts": int(row["concepts"] or 0),
                "fields": int(row["fields"] or 0),
                "book_edges": edges,
                "book_relationship_density": round(density, 4),
            }

    def get_field_coverage(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)
        OPTIONAL MATCH (b:Book)-[:BELONGS_TO]->(f)
        RETURN f.name AS field, count(DISTINCT b) AS bookCount
        ORDER BY bookCount DESC, field ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_top_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Concept)<-[:MENTIONS]-(b:Book)
        RETURN c.name AS concept, count(DISTINCT b) AS bookCount
        ORDER BY bookCount DESC, concept ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_unlinked_books(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (b:Book)
        WHERE NOT (b)-[:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Book)
        RETURN b.title AS title, b.publish_year AS publish_year
        ORDER BY coalesce(b.publish_year, 9999) ASC, b.title ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_book_relationship_edges(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
        MATCH (a:Book)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(b:Book)
        RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type
        ORDER BY type(r) ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_book_nodes_by_titles(self, titles: list[str]) -> list[dict[str, Any]]:
        if not titles:
            return []
        query = """
        UNWIND $titles AS title
        MATCH (b:Book {title: title})
        RETURN elementId(b) AS id, b.title AS label, 'book' AS type
        """
        with self._driver.session() as session:
            return session.run(query, titles=titles).data()

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        if not fields:
            return []
        query = """
        UNWIND $fields AS field_name
        MATCH (f:Field {name: field_name})
        RETURN elementId(f) AS id, f.name AS label, 'field' AS type
        """
        with self._driver.session() as session:
            return session.run(query, fields=fields).data()

    def get_concept_nodes_by_names(self, concepts: list[str]) -> list[dict[str, Any]]:
        if not concepts:
            return []
        query = """
        UNWIND $concepts AS concept_name
        MATCH (c:Concept {name: concept_name})
        RETURN elementId(c) AS id, c.name AS label, 'concept' AS type
        """
        with self._driver.session() as session:
            return session.run(query, concepts=concepts).data()

    def get_field_reading_paths(self, limit_fields: int = 4, path_len: int = 4) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)<-[:BELONGS_TO]-(b:Book)
        OPTIONAL MATCH (b)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Book)
        WITH f, b, count(DISTINCT r) AS relScore
        ORDER BY f.name ASC, relScore DESC, coalesce(b.publish_year, 9999) ASC
        WITH f, collect({
            title: b.title,
            publish_year: b.publish_year,
            score: relScore
        })[..$path_len] AS path
        WHERE size(path) >= 2
        RETURN f.name AS field, path
        ORDER BY size(path) DESC, field ASC
        LIMIT $limit_fields
        """
        with self._driver.session() as session:
            return session.run(query, limit_fields=limit_fields, path_len=path_len).data()

    def get_overlap_contradiction_summary(self) -> dict[str, Any]:
        query = """
        MATCH (:Book)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(:Book)
        RETURN
            count(CASE WHEN type(r) IN ['RELATED_TO', 'INFLUENCED_BY', 'EXPANDS'] THEN 1 END) AS overlapCount,
            count(CASE WHEN type(r) = 'CONTRADICTS' THEN 1 END) AS contradictionCount
        """
        sample_query = """
        MATCH (a:Book)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(b:Book)
        RETURN a.title AS source, type(r) AS relation, b.title AS target
        ORDER BY CASE type(r) WHEN 'CONTRADICTS' THEN 0 ELSE 1 END ASC, a.title ASC
        LIMIT 12
        """
        with self._driver.session() as session:
            row = session.run(query).single()
            samples = session.run(sample_query).data()
            return {
                "overlap_count": int(row["overlapCount"] or 0) if row else 0,
                "contradiction_count": int(row["contradictionCount"] or 0) if row else 0,
                "samples": samples,
            }

    def detect_sparse_bridges(self, limit: int = 8, max_fields: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)<-[:BELONGS_TO]-(b:Book)
        WITH f, count(DISTINCT b) AS bookCount
        WHERE bookCount > 0
        ORDER BY bookCount DESC, f.name ASC
        LIMIT $max_fields
        WITH collect({name: f.name, count: bookCount}) AS fieldRows
        UNWIND fieldRows AS fa
        UNWIND fieldRows AS fb
        WITH fa, fb
        WHERE fa.name < fb.name
        CALL {
            WITH fa, fb
            MATCH (x:Book)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(y:Book)
            WHERE (x)-[:BELONGS_TO]->(:Field {name: fa.name})
              AND (y)-[:BELONGS_TO]->(:Field {name: fb.name})
            RETURN count(DISTINCT r) AS crossLinks
        }
        WITH fa, fb, crossLinks
        WHERE crossLinks = 0
        RETURN fa.name AS field_a, fb.name AS field_b, fa.count AS books_a, fb.count AS books_b
        ORDER BY (fa.count + fb.count) DESC, field_a ASC, field_b ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit, max_fields=max_fields).data()

    def get_field_dashboards(self, limit: int = 5) -> list[dict[str, Any]]:
        top_fields = self.get_field_coverage(limit=limit)
        dashboards: list[dict[str, Any]] = []
        with self._driver.session() as session:
            for field in top_fields:
                field_name = field["field"]
                books_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(b:Book)
                OPTIONAL MATCH (b)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Book)
                RETURN b.title AS title, b.publish_year AS publish_year, count(DISTINCT r) AS relationCount
                ORDER BY relationCount DESC, coalesce(b.publish_year, 9999) ASC, title ASC
                LIMIT 5
                """
                concepts_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(b:Book)-[:MENTIONS]->(c:Concept)
                RETURN c.name AS concept, count(DISTINCT b) AS bookCount
                ORDER BY bookCount DESC, concept ASC
                LIMIT 5
                """
                isolated_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(b:Book)
                WHERE NOT (b)-[:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Book)
                RETURN b.title AS title
                ORDER BY title ASC
                LIMIT 5
                """
                top_books = session.run(books_query, field_name=field_name).data()
                top_concepts = session.run(concepts_query, field_name=field_name).data()
                isolated_books = session.run(isolated_query, field_name=field_name).data()
                unanswered_questions = [
                    f"Which book can bridge '{field_name}' to adjacent fields?",
                    f"Are there contradictory viewpoints within '{field_name}'?",
                ]
                dashboards.append(
                    {
                        "field": field_name,
                        "book_count": field["bookCount"],
                        "top_books": top_books,
                        "top_concepts": top_concepts,
                        "isolated_books": isolated_books,
                        "unanswered_questions": unanswered_questions,
                    }
                )
        return dashboards

    def get_latest_insight_snapshots(self, limit: int = 2) -> list[dict[str, Any]]:
        query = """
        MATCH (s:InsightSnapshot)
        RETURN s.created_at AS created_at,
               s.books AS books,
               s.authors AS authors,
               s.concepts AS concepts,
               s.fields AS fields,
               s.book_edges AS book_edges,
               s.book_relationship_density AS book_relationship_density,
               s.overall_score AS overall_score
        ORDER BY s.created_at DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(query, limit=limit).data()
            normalized = []
            for row in rows:
                created_at = row["created_at"]
                normalized.append(
                    {
                        "created_at": str(created_at),
                        "books": int(row.get("books") or 0),
                        "authors": int(row.get("authors") or 0),
                        "concepts": int(row.get("concepts") or 0),
                        "fields": int(row.get("fields") or 0),
                        "book_edges": int(row.get("book_edges") or 0),
                        "book_relationship_density": float(row.get("book_relationship_density") or 0.0),
                        "overall_score": int(row.get("overall_score") or 0),
                    }
                )
            return normalized

    def save_insight_snapshot(self, stats: dict[str, Any], overall_score: int) -> None:
        query = """
        CREATE (s:InsightSnapshot {
            id: randomUUID(),
            created_at: datetime(),
            books: $books,
            authors: $authors,
            concepts: $concepts,
            fields: $fields,
            book_edges: $book_edges,
            book_relationship_density: $book_relationship_density,
            overall_score: $overall_score
        })
        """
        with self._driver.session() as session:
            session.run(
                query,
                books=int(stats.get("books", 0)),
                authors=int(stats.get("authors", 0)),
                concepts=int(stats.get("concepts", 0)),
                fields=int(stats.get("fields", 0)),
                book_edges=int(stats.get("book_edges", 0)),
                book_relationship_density=float(stats.get("book_relationship_density", 0.0)),
                overall_score=int(overall_score),
            ).consume()

    def get_cross_field_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Concept)<-[:MENTIONS]-(b:Book)-[:BELONGS_TO]->(f:Field)
        WITH c, collect(DISTINCT f.name) AS fields, count(DISTINCT f) AS fieldCount
        WHERE fieldCount >= 2
        RETURN c.name AS concept, fields, fieldCount
        ORDER BY fieldCount DESC, concept ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_concept_reading_paths(self, limit_concepts: int = 8, path_len: int = 4) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Concept)<-[:MENTIONS]-(b:Book)
        OPTIONAL MATCH (b)-[r:RELATED_TO|INFLUENCED_BY|EXPANDS]-(:Book)
        WITH c, b, count(DISTINCT r) AS relationScore
        ORDER BY c.name ASC, relationScore DESC, coalesce(b.publish_year, 9999) ASC, b.title ASC
        WITH c, collect({
            title: b.title,
            publish_year: b.publish_year,
            relation_score: relationScore
        })[..$path_len] AS books
        WHERE size(books) >= 2
        RETURN c.name AS concept, books
        ORDER BY size(books) DESC, concept ASC
        LIMIT $limit_concepts
        """
        with self._driver.session() as session:
            return session.run(query, limit_concepts=limit_concepts, path_len=path_len).data()

    def save_reading_path(
        self,
        concept: str,
        books: list[str],
        explanation: str,
        signature: str,
    ) -> dict[str, Any]:
        query = """
        MERGE (r:ReadingPath {signature: $signature})
        ON CREATE SET r.id = randomUUID(), r.created_at = datetime()
        SET r.concept = $concept,
            r.books = $books,
            r.explanation = $explanation,
            r.updated_at = datetime()
        RETURN r.id AS id,
               r.concept AS concept,
               r.books AS books,
               r.explanation AS explanation,
               r.created_at AS created_at
        """
        with self._driver.session() as session:
            row = session.run(
                query,
                concept=concept,
                books=books,
                explanation=explanation,
                signature=signature,
            ).single()
            if not row:
                return {
                    "id": "",
                    "concept": concept,
                    "books": books,
                    "explanation": explanation,
                    "created_at": "",
                }
            return {
                "id": str(row.get("id") or ""),
                "concept": str(row.get("concept") or concept),
                "books": [str(book) for book in (row.get("books") or [])],
                "explanation": str(row.get("explanation") or explanation),
                "created_at": str(row.get("created_at") or ""),
            }

    def list_reading_paths(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
        MATCH (r:ReadingPath)
        RETURN r.concept AS concept,
               r.books AS books,
               r.explanation AS explanation,
               r.created_at AS created_at
        ORDER BY r.created_at DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(query, limit=limit).data()
            return [
                {
                    "concept": str(row.get("concept") or ""),
                    "books": [str(book) for book in (row.get("books") or [])],
                    "explanation": str(row.get("explanation") or ""),
                    "created_at": str(row.get("created_at") or ""),
                }
                for row in rows
            ]

    def get_books_for_fields(self, fields: list[str], limit: int = 5) -> list[str]:
        if not fields:
            return []
        query = """
        UNWIND $fields AS field_name
        MATCH (f:Field {name: field_name})<-[:BELONGS_TO]-(b:Book)
        OPTIONAL MATCH (b)-[r:RELATED_TO|INFLUENCED_BY|EXPANDS]-(:Book)
        WITH b, count(DISTINCT r) AS relationScore
        RETURN b.title AS title
        ORDER BY relationScore DESC, coalesce(b.publish_year, 9999) ASC, title ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(query, fields=fields, limit=limit).data()
            return [str(row["title"]) for row in rows if row.get("title")]

    def save_knowledge_gap(
        self,
        gap: str,
        reason: str,
        candidate_books: list[str],
        signature: str,
    ) -> dict[str, Any]:
        query = """
        MERGE (k:KnowledgeGap {signature: $signature})
        ON CREATE SET k.id = randomUUID(), k.created_at = datetime()
        SET k.gap = $gap,
            k.reason = $reason,
            k.candidate_books = $candidate_books,
            k.updated_at = datetime()
        RETURN k.id AS id,
               k.gap AS gap,
               k.reason AS reason,
               k.candidate_books AS candidate_books,
               k.created_at AS created_at
        """
        with self._driver.session() as session:
            row = session.run(
                query,
                gap=gap,
                reason=reason,
                candidate_books=candidate_books,
                signature=signature,
            ).single()
            if not row:
                return {
                    "id": "",
                    "gap": gap,
                    "reason": reason,
                    "candidate_books": candidate_books,
                    "created_at": "",
                }
            return {
                "id": str(row.get("id") or ""),
                "gap": str(row.get("gap") or gap),
                "reason": str(row.get("reason") or reason),
                "candidate_books": [str(book) for book in (row.get("candidate_books") or [])],
                "created_at": str(row.get("created_at") or ""),
            }

    def list_knowledge_gaps(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
        MATCH (k:KnowledgeGap)
        RETURN k.gap AS gap,
               k.reason AS reason,
               k.candidate_books AS candidate_books,
               k.created_at AS created_at
        ORDER BY k.created_at DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(query, limit=limit).data()
            return [
                {
                    "gap": str(row.get("gap") or ""),
                    "reason": str(row.get("reason") or ""),
                    "candidate_books": [str(book) for book in (row.get("candidate_books") or [])],
                    "created_at": str(row.get("created_at") or ""),
                }
                for row in rows
            ]

    def save_graph_insight(
        self,
        insight_type: str,
        title: str,
        description: str,
        node_ids: list[str],
        related_nodes: list[str],
        signature: str,
    ) -> dict[str, Any]:
        query = """
        MERGE (g:GraphInsight {signature: $signature})
        ON CREATE SET g.id = randomUUID(), g.created_at = datetime()
        SET g.type = $insight_type,
            g.title = $title,
            g.description = $description,
            g.node_ids = $node_ids,
            g.related_nodes = $related_nodes,
            g.nodes = $related_nodes,
            g.updated_at = datetime()
        RETURN g.id AS id,
               g.type AS type,
               g.title AS title,
               g.description AS description,
               g.node_ids AS node_ids,
               coalesce(g.related_nodes, g.nodes, []) AS related_nodes,
               g.created_at AS created_at
        """
        with self._driver.session() as session:
            row = session.run(
                query,
                signature=signature,
                insight_type=insight_type,
                title=title,
                description=description,
                node_ids=node_ids,
                related_nodes=related_nodes,
            ).single()
            if not row:
                return {
                    "id": "",
                    "type": insight_type,
                    "title": title,
                    "description": description,
                    "node_ids": node_ids,
                    "related_nodes": related_nodes,
                    "created_at": "",
                }
            return {
                "id": str(row.get("id") or ""),
                "type": str(row.get("type") or insight_type),
                "title": str(row.get("title") or title),
                "description": str(row.get("description") or description),
                "node_ids": [str(node) for node in (row.get("node_ids") or [])],
                "related_nodes": [str(node) for node in (row.get("related_nodes") or [])],
                "created_at": str(row.get("created_at") or ""),
            }

    def list_graph_insights(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
        MATCH (g:GraphInsight)
        RETURN g.id AS id,
               g.type AS type,
               g.title AS title,
               g.description AS description,
               g.node_ids AS node_ids,
               coalesce(g.related_nodes, g.nodes, []) AS related_nodes,
               g.created_at AS created_at
        ORDER BY g.created_at DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(query, limit=limit).data()
            return [
                {
                    "id": str(row.get("id") or ""),
                    "type": str(row.get("type") or ""),
                    "title": str(row.get("title") or ""),
                    "description": str(row.get("description") or ""),
                    "node_ids": [str(node) for node in (row.get("node_ids") or [])],
                    "related_nodes": [str(node) for node in (row.get("related_nodes") or [])],
                    "created_at": str(row.get("created_at") or ""),
                }
                for row in rows
            ]

    def get_graph_insight(self, insight_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (g:GraphInsight {id: $insight_id})
        RETURN g.id AS id,
               g.type AS type,
               g.title AS title,
               g.description AS description,
               g.node_ids AS node_ids,
               coalesce(g.related_nodes, g.nodes, []) AS related_nodes,
               g.created_at AS created_at
        LIMIT 1
        """
        with self._driver.session() as session:
            row = session.run(query, insight_id=insight_id).single()
            if not row:
                return None
            return {
                "id": str(row.get("id") or ""),
                "type": str(row.get("type") or ""),
                "title": str(row.get("title") or ""),
                "description": str(row.get("description") or ""),
                "node_ids": [str(node) for node in (row.get("node_ids") or [])],
                "related_nodes": [str(node) for node in (row.get("related_nodes") or [])],
                "created_at": str(row.get("created_at") or ""),
            }

    def save_latest_insight_bundle(self, bundle: dict[str, Any]) -> None:
        query = """
        MERGE (i:InsightBundle {name: 'latest'})
        ON CREATE SET i.id = randomUUID(), i.created_at = datetime()
        SET i.payload_json = $payload_json,
            i.generated_at = datetime(),
            i.updated_at = datetime()
        """
        with self._driver.session() as session:
            session.run(query, payload_json=json.dumps(bundle, ensure_ascii=True)).consume()

    def get_latest_insight_bundle(self) -> dict[str, Any] | None:
        query = """
        MATCH (i:InsightBundle {name: 'latest'})
        RETURN i.payload_json AS payload_json
        LIMIT 1
        """
        with self._driver.session() as session:
            row = session.run(query).single()
            if not row:
                return None
            payload_json = row.get("payload_json")
            if not payload_json:
                return None
            try:
                parsed = json.loads(str(payload_json))
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None

    def try_acquire_agent_job(self, name: str, owner_id: str, lease_seconds: int) -> bool:
        query = """
        MERGE (j:AgentJob {name: $name})
        ON CREATE SET j.created_at = datetime(), j.status = 'idle'
        WITH j
        WHERE j.status <> 'running'
           OR j.owner_id = $owner_id
           OR j.lease_expires_at IS NULL
           OR j.lease_expires_at < datetime()
        SET j.owner_id = $owner_id,
            j.status = 'running',
            j.error = NULL,
            j.last_started_at = datetime(),
            j.lease_expires_at = datetime() + duration({seconds: $lease_seconds}),
            j.updated_at = datetime()
        RETURN j.name AS name
        """
        with self._driver.session() as session:
            row = session.run(
                query,
                name=name,
                owner_id=owner_id,
                lease_seconds=max(1, lease_seconds),
            ).single()
            return bool(row)

    def complete_agent_job_run(self, name: str, owner_id: str, status: str, error: str | None = None) -> None:
        normalized_status = "error" if status == "error" else "idle"
        query = """
        MATCH (j:AgentJob {name: $name})
        WHERE j.owner_id = $owner_id
        SET j.status = $status,
            j.error = $error,
            j.last_run_at = datetime(),
            j.owner_id = NULL,
            j.lease_expires_at = NULL,
            j.updated_at = datetime()
        FOREACH (_ IN CASE WHEN $status = 'idle' THEN [1] ELSE [] END |
            SET j.last_success_at = j.last_run_at
        )
        """
        with self._driver.session() as session:
            session.run(
                query,
                name=name,
                owner_id=owner_id,
                status=normalized_status,
                error=(error or None),
            ).consume()

    def get_chat_subgraph(
        self,
        question: str,
        scope: str = "auto",
        k: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        terms = [token.strip().lower() for token in question.split() if len(token.strip()) >= 3][:12]
        scope = scope.strip().lower()
        label_filter = {
            "book": "Book",
            "author": "Author",
            "concept": "Concept",
            "field": "Field",
        }.get(scope)
        with self._driver.session() as session:
            if label_filter:
                seed_query = """
                MATCH (n)
                WHERE $label IN labels(n)
                  AND any(term IN $terms WHERE
                      toLower(coalesce(n.title, n.name, "")) CONTAINS term
                      OR toLower(coalesce(n.description, "")) CONTAINS term
                  )
                RETURN elementId(n) AS id
                LIMIT $k
                """
            else:
                seed_query = """
                MATCH (n)
                WHERE any(term IN $terms WHERE
                    toLower(coalesce(n.title, n.name, "")) CONTAINS term
                    OR toLower(coalesce(n.description, "")) CONTAINS term
                )
                RETURN elementId(n) AS id
                LIMIT $k
                """

            params = {"terms": terms, "k": k, "label": label_filter}
            seed_ids = [row["id"] for row in session.run(seed_query, params).data()] if terms else []
            if not seed_ids:
                fallback_query = """
                MATCH (b:Book)
                RETURN elementId(b) AS id
                ORDER BY coalesce(b.publish_year, 9999) ASC, b.title ASC
                LIMIT $k
                """
                seed_ids = [row["id"] for row in session.run(fallback_query, k=k).data()]

            if not seed_ids:
                return {"nodes": [], "edges": []}

            neighborhood_query = """
            UNWIND $seed_ids AS sid
            MATCH (s)
            WHERE elementId(s) = sid
            OPTIONAL MATCH (s)-[:WRITTEN_BY|MENTIONS|BELONGS_TO|RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(n)
            WITH collect(DISTINCT elementId(s)) + collect(DISTINCT elementId(n)) AS rawNodeIds
            UNWIND rawNodeIds AS nodeId
            WITH DISTINCT nodeId
            WHERE nodeId IS NOT NULL
            RETURN nodeId
            LIMIT $node_limit
            """
            node_ids = [row["nodeId"] for row in session.run(neighborhood_query, seed_ids=seed_ids, node_limit=max(k * 3, 20))]
            if not node_ids:
                node_ids = seed_ids

            nodes_query = """
            UNWIND $node_ids AS node_id
            MATCH (n)
            WHERE elementId(n) = node_id
            RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
            """
            edges_query = """
            UNWIND $node_ids AS node_id
            MATCH (a)
            WHERE elementId(a) = node_id
            MATCH (a)-[r]->(b)
            WHERE elementId(b) IN $node_ids
            RETURN DISTINCT
                elementId(r) AS id,
                elementId(a) AS source,
                elementId(b) AS target,
                type(r) AS type
            LIMIT $edge_limit
            """
            nodes = [
                {
                    "id": row["id"],
                    "label": row["props"].get("title") or row["props"].get("name") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": row["props"],
                }
                for row in session.run(nodes_query, node_ids=node_ids).data()
            ]
            edges = session.run(
                edges_query,
                node_ids=node_ids,
                edge_limit=max(k * 6, 30),
            ).data()
            return {"nodes": nodes, "edges": edges}
