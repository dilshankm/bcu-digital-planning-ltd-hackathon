"""Neo4j-native vector store service using Neo4j vector indexes (like the mentor's notebooks)"""
from typing import List, Dict, Any, Optional
from services.neo4j_service import Neo4jService
from services.embedding_service import EmbeddingService
from config import get_settings


class Neo4jVectorStoreService:
    """Vector store using Neo4j native vector indexes (aligned with mentor's approach)"""
    
    def __init__(self):
        self.neo4j_service = Neo4jService()
        self.embedding_service = EmbeddingService()
        self.settings = get_settings()
        self.index_name = "node_embeddings"
        self.embedding_property = "embedding"
        
    def ensure_vector_index(self):
        """Create vector index if it doesn't exist (like notebook Lesson 3)"""
        try:
            # Check if index already exists
            indexes = self.neo4j_service.execute_query("SHOW VECTOR INDEXES")
            index_names = [idx.get('name', '') for idx in indexes if isinstance(idx, dict)]
            
            if self.index_name not in index_names:
                # Create vector index (same approach as notebooks)
                create_index_query = f"""
                CREATE VECTOR INDEX {self.index_name} IF NOT EXISTS
                FOR (n) ON (n.{self.embedding_property}) 
                OPTIONS {{ indexConfig: {{
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}}}
                """
                self.neo4j_service.execute_query(create_index_query)
                print(f"✅ Created vector index: {self.index_name}")
            else:
                print(f"✅ Vector index already exists: {self.index_name}")
        except Exception as e:
            print(f"⚠️  Could not create vector index (may require Neo4j 5.11+ or GDS): {e}")
            # Fallback: continue without native index, use property-based search
    
    def upsert_nodes(self, nodes: List[Dict[str, Any]]):
        """Store embeddings directly on Neo4j nodes (like notebook)"""
        self.ensure_vector_index()
        
        batch_size = 1  # Small batches to avoid token limits
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            for node in batch:
                node_id = node.get("id")
                label = node.get("label", "Node")
                properties = node.get("properties", {})
                
                # Create text representation for embedding
                text_repr = self._node_text_representation(label, properties)
                
                # Generate embedding
                try:
                    embedding = self.embedding_service.embed_text(text_repr[:500])  # Limit text length
                    
                    # Store embedding as property on node (like notebook's taglineEmbedding)
                    # Use node internal ID to find and update
                    upsert_query = f"""
                    MATCH (n) WHERE id(n) = $node_id
                    SET n.{self.embedding_property} = $embedding,
                        n._text_repr = $text_repr
                    RETURN id(n) as id
                    """
                    self.neo4j_service.execute_query(upsert_query, {
                        "node_id": node_id,
                        "embedding": embedding,
                        "text_repr": text_repr[:500]
                    })
                except Exception as e:
                    print(f"⚠️  Failed to embed node {node_id}: {e}")
                    continue
        
        print(f"✅ Stored embeddings for {len(nodes)} nodes in Neo4j")
    
    def similarity_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using Neo4j vector index (like notebook's db.index.vector.queryNodes)"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.embed_text(query)
            
            # Use Neo4j vector index search (like notebook Lesson 3)
            search_query = f"""
            CALL db.index.vector.queryNodes(
                '{self.index_name}', 
                $top_k, 
                $query_embedding
            ) YIELD node, score
            RETURN id(node) as id, score, labels(node)[0] as label, properties(node) as properties
            ORDER BY score DESC
            LIMIT $top_k
            """
            
            results = self.neo4j_service.execute_query(search_query, {
                "query_embedding": query_embedding,
                "top_k": top_k
            })
            
            hits = []
            for result in results:
                hits.append({
                    "id": result.get("id"),
                    "score": result.get("score", 0.0),
                    "label": result.get("label"),
                    "properties": result.get("properties", {})
                })
            
            return hits
            
        except Exception as e:
            # Fallback: property-based cosine similarity if vector index not available
            print(f"⚠️  Vector index search failed, using fallback: {e}")
            return self._fallback_similarity_search(query, top_k)
    
    def _fallback_similarity_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Fallback similarity search using cosine similarity (pure Python)"""
        query_embedding = self.embedding_service.embed_text(query)
        
        # Get nodes with embeddings
        nodes_query = f"""
        MATCH (n)
        WHERE n.{self.embedding_property} IS NOT NULL
        RETURN id(n) as id, labels(n)[0] as label, properties(n) as properties, n.{self.embedding_property} as embedding
        LIMIT 100
        """
        
        nodes = self.neo4j_service.execute_query(nodes_query)
        
        # Calculate cosine similarity (pure Python, no numpy needed)
        hits = []
        for node in nodes:
            node_embedding = node.get("embedding")
            if node_embedding and isinstance(node_embedding, list):
                # Dot product
                dot_product = sum(a * b for a, b in zip(query_embedding, node_embedding))
                # Magnitudes
                norm_q = sum(x * x for x in query_embedding) ** 0.5
                norm_n = sum(x * x for x in node_embedding) ** 0.5
                # Cosine similarity
                if norm_q > 0 and norm_n > 0:
                    similarity = dot_product / (norm_q * norm_n)
                    hits.append({
                        "id": node.get("id"),
                        "score": float(similarity),
                        "label": node.get("label"),
                        "properties": node.get("properties", {})
                    })
        
        # Sort by score descending
        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits[:top_k]
    
    @staticmethod
    def _node_text_representation(label: Optional[str], properties: Dict[str, Any]) -> str:
        """Create text representation for embedding (like notebook)"""
        parts = []
        if label:
            parts.append(f"Label: {label}")
        if properties:
            for k, v in list(properties.items())[:10]:  # Limit properties
                if v is not None:
                    val_str = str(v)[:100]  # Truncate long values
                    parts.append(f"{k}: {val_str}")
        return "\n".join(parts) if parts else "(empty)"
    
    def count(self) -> int:
        """Count nodes with embeddings"""
        result = self.neo4j_service.execute_query(
            f"MATCH (n) WHERE n.{self.embedding_property} IS NOT NULL RETURN count(n) as count"
        )
        return result[0].get("count", 0) if result else 0

