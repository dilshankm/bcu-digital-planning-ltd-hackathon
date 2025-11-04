from typing import TypedDict, List, Dict, Any, Optional


class GraphState(TypedDict):
    question: str
    cypher_query: str
    neo4j_results: List[Dict[str, Any]]
    final_answer: str
    error: str
    query_embedding: List[float]
    similar_nodes: List[Dict[str, Any]]
    subgraph: Dict[str, Any]
    context: str
    plan: str
    messages: List[Dict[str, Any]]
    step: int
    max_steps: int
    decision: str
    confidence: float
    session_id: Optional[str]  # For multi-turn conversations
    conversation_history: Optional[str]  # Previous conversation context
    refinement_count: int  # Track query refinement attempts