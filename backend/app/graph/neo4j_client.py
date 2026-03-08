from __future__ import annotations

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

    def get_books_for_relationship_scan(self, exclude_title: str, limit: int) -> list[dict[str, Any]]:
        query = """
        MATCH (b:Book)
        WHERE b.title <> $exclude_title
        OPTIONAL MATCH (b)-[:BELONGS_TO]->(f:Field)
        RETURN b.title AS title,
               b.description AS description,
               b.publish_year AS publish_year,
               collect(DISTINCT f.name) AS subjects
        LIMIT $limit
        """
        with self._driver.session() as session:
            results = session.run(query, exclude_title=exclude_title, limit=limit)
            return [record.data() for record in results]

    def add_book_relationship(self, source: str, relation: str, target: str) -> None:
        if relation == "BELONGS_TO_FIELD":
            relation = "BELONGS_TO"
        if relation not in {"RELATED_TO", "INFLUENCED_BY", "CONTRADICTS", "EXPANDS", "BELONGS_TO"}:
            return

        query = f"""
        MATCH (source:Book {{title: $source}}), (target:Book {{title: $target}})
        MERGE (source)-[r:{relation}]->(target)
        RETURN type(r) AS relation
        """
        with self._driver.session() as session:
            session.run(query, source=source, target=target).consume()

    def get_graph(self) -> dict[str, list[dict[str, Any]]]:
        nodes_query = """
        MATCH (n)
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        """
        edges_query = """
        MATCH (a)-[r]->(b)
        RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type
        """
        with self._driver.session() as session:
            nodes = [
                {
                    "id": row["id"],
                    "label": row["props"].get("title") or row["props"].get("name") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": row["props"],
                }
                for row in session.run(nodes_query).data()
            ]
            edges = [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "target": row["target"],
                    "type": row["type"],
                }
                for row in session.run(edges_query).data()
            ]
            return {"nodes": nodes, "edges": edges}

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

    def detect_sparse_bridges(self, limit: int = 8) -> list[dict[str, Any]]:
        query = """
        MATCH (f1:Field)<-[:BELONGS_TO]-(b1:Book)
        MATCH (f2:Field)<-[:BELONGS_TO]-(b2:Book)
        WHERE f1.name < f2.name
        WITH f1, f2, count(DISTINCT b1) AS booksA, count(DISTINCT b2) AS booksB
        WHERE booksA > 0 AND booksB > 0
        CALL {
            WITH f1, f2
            MATCH (x:Book)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(y:Book)
            WHERE (x)-[:BELONGS_TO]->(f1) AND (y)-[:BELONGS_TO]->(f2)
            RETURN count(DISTINCT r) AS crossLinks
        }
        WITH f1, f2, booksA, booksB, crossLinks
        WHERE crossLinks = 0
        RETURN f1.name AS field_a, f2.name AS field_b, booksA AS books_a, booksB AS books_b
        ORDER BY (booksA + booksB) DESC, field_a ASC, field_b ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

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
