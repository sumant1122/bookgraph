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
        RETURN b.title AS title, count(r) AS score
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
