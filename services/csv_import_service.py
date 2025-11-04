"""Service for importing additional CSV data into Neo4j"""
import csv
import io
from typing import List, Dict, Any
from services.neo4j_service import Neo4jService


class CSVImportService:
    """Handles CSV import and schema extension"""
    
    def __init__(self):
        self.neo4j_service = Neo4jService()
    
    def import_csv(self, csv_content: str, node_type: str, properties: List[str], 
                   create_relationships: bool = False) -> Dict[str, Any]:
        """
        Import CSV data into Neo4j
        
        Args:
            csv_content: CSV file content as string
            node_type: Type of node to create (e.g., "Medication", "Allergy")
            properties: List of property names from CSV header
            create_relationships: Whether to create relationships with existing nodes
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        nodes_created = 0
        relationships_created = 0
        errors = []
        
        # Create index for the new node type
        try:
            index_query = f"CREATE INDEX IF NOT EXISTS FOR (n:{node_type}) ON (n.id)"
            self.neo4j_service.execute_query(index_query)
        except Exception as e:
            errors.append(f"Index creation warning: {str(e)}")
        
        batch_size = 100
        batch = []
        
        for row in reader:
            try:
                # Clean properties
                node_properties = {k: v for k, v in row.items() if k in properties and v}
                
                # Create node with all properties
                props_str = ", ".join([f"`{k}`: ${k}" for k in node_properties.keys()])
                create_query = f"""
                MERGE (n:{node_type} {{{props_str}}})
                RETURN id(n) as node_id
                """
                
                batch.append({
                    "query": create_query,
                    "params": node_properties
                })
                
                if len(batch) >= batch_size:
                    self._execute_batch(batch)
                    nodes_created += len(batch)
                    batch = []
                    
            except Exception as e:
                errors.append(f"Error processing row: {str(e)}")
        
        # Execute remaining batch
        if batch:
            self._execute_batch(batch)
            nodes_created += len(batch)
        
        return {
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
            "errors": errors,
            "node_type": node_type
        }
    
    def _execute_batch(self, batch: List[Dict]):
        """Execute a batch of queries"""
        with self.neo4j_service.driver.session() as session:
            for item in batch:
                try:
                    session.run(item["query"], item.get("params", {}))
                except Exception:
                    pass  # Continue on individual errors
    
    def create_relationship(self, from_node_type: str, from_property: str, from_value: str,
                           to_node_type: str, to_property: str, to_value: str,
                           relationship_type: str) -> bool:
        """Create a relationship between nodes"""
        query = f"""
        MATCH (a:{from_node_type} {{`{from_property}`: $from_val}})
        MATCH (b:{to_node_type} {{`{to_property}`: $to_val}})
        MERGE (a)-[r:{relationship_type}]->(b)
        RETURN r
        """
        try:
            result = self.neo4j_service.execute_query(query, {
                "from_val": from_value,
                "to_val": to_value
            })
            return len(result) > 0
        except Exception:
            return False
    
    def close(self):
        self.neo4j_service.close()

