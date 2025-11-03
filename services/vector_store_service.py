from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions

from services.embedding_service import EmbeddingService


class VectorStoreService:
    def __init__(self, persist_directory: str = "./chroma"):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=persist_directory)
        # We will supply our own embeddings via EmbeddingService; use a placeholder here
        self.collection = self.client.get_or_create_collection(
            name="nodes",
            metadata={"hnsw:space": "cosine"},
        )
        self.embedding_service = EmbeddingService()

    def upsert_nodes(self, nodes: List[Dict[str, Any]]):
        # Very small batches to respect embedding token limits
        batch_size = 1
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            ids: List[str] = []
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []
            for node in batch:
                node_id = str(node.get("id"))
                label = node.get("label")
                properties = node.get("properties", {})
                text_repr = self._node_text_representation(label, properties)
                # Aggressively truncate to avoid exceeding token limits
                documents.append(text_repr[:128])
                ids.append(node_id)
                metadatas.append({"label": label})
            embeddings = self.embedding_service.embed_texts(documents)
            self.collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def similarity_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_service.embed_text(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        hits: List[Dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for idx, node_id in enumerate(ids):
            hits.append({
                "id": node_id,
                "document": docs[idx],
                "metadata": metas[idx],
                "score": 1.0 - dists[idx] if dists is not None else None,
            })
        return hits

    @staticmethod
    def _node_text_representation(label: Optional[str], properties: Dict[str, Any]) -> str:
        parts: List[str] = []
        if label:
            parts.append(f"Label: {label}")
        if properties:
            count = 0
            for k, v in properties.items():
                # Truncate property values too
                val_str = str(v)[:50] if v else ""
                parts.append(f"{k}: {val_str}")
                count += 1
                if count >= 5:
                    parts.append("...")
                    break
        text = "\n".join(parts) if parts else "(empty)"
        return text


