from neo4j import GraphDatabase
from typing import Dict

from config import get_settings


class Neo4jService:
    def __init__(self):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )

    def execute_query(self, cypher_query: str, parameters: Dict = None):
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            records = []
            for record in result:
                data = {}
                for key, value in record.items():
                    # Convert Neo4j Node/Relationship objects to dicts
                    if hasattr(value, '__dict__') and hasattr(value, '_properties'):
                        # It's a Neo4j Node or Relationship
                        data[key] = dict(value._properties)
                    elif isinstance(value, list):
                        # Handle lists (might contain Node objects)
                        data[key] = [dict(v._properties) if hasattr(v, '_properties') else v for v in value]
                    else:
                        data[key] = value
                records.append(data)
            return records

    def fetch_all_nodes(self):
        query = (
            "MATCH (n) RETURN id(n) as id, labels(n)[0] as label, properties(n) as properties"
        )
        return self.execute_query(query)

    def expand_subgraph(self, node_ids, depth: int = 1):
        ids_csv = ",".join(str(i) for i in node_ids)
        query = f"""
        MATCH (n) WHERE id(n) IN [{ids_csv}]
        CALL apoc.path.subgraphAll(n, {{maxLevel: {depth}}}) YIELD nodes, relationships
        WITH nodes, relationships
        RETURN [x IN nodes | {{id: id(x), label: labels(x)[0], properties: properties(x)}}] AS nodes,
               [r IN relationships | {{start: id(startNode(r)), end: id(endNode(r)), type: type(r)}}] AS relationships
        LIMIT 1
        """
        # Fallback if APOC not available: simple 1-hop traversal
        try:
            results = self.execute_query(query)
            if results:
                return results[0]
        except Exception:
            pass

        # Simple fallback traversal without APOC
        query_fallback = f"""
        MATCH (n)-[r]-(m)
        WHERE id(n) IN [{ids_csv}]
        RETURN collect(distinct { {id: id(n), label: labels(n)[0], properties: properties(n)} }) as start_nodes,
               collect(distinct { {id: id(m), label: labels(m)[0], properties: properties(m)} }) as neighbor_nodes,
               collect(distinct { {start: id(startNode(r)), end: id(endNode(r)), type: type(r)} }) as relationships
        """
        res = self.execute_query(query_fallback)
        if not res:
            return {"nodes": [], "relationships": []}
        start_nodes = res[0].get("start_nodes", [])
        neighbor_nodes = res[0].get("neighbor_nodes", [])
        relationships = res[0].get("relationships", [])
        # Merge unique nodes by id
        seen = {}
        for n in start_nodes + neighbor_nodes:
            seen[n["id"]] = n
        return {"nodes": list(seen.values()), "relationships": relationships}

    def close(self):
        self.driver.close()
