from typing import TypedDict, List, Dict, Any


class GraphState(TypedDict):
    question: str
    cypher_query: str
    neo4j_results: List[Dict[str, Any]]
    final_answer: str
    error: str