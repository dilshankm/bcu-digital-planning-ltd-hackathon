from graph.state import GraphState
from services.neo4j_service import Neo4jService
from services.llm_service import LLMService


neo4j_service = Neo4jService()
llm_service = LLMService()

SCHEMA = """
- Patient nodes with properties: id, birthDate, gender
- Condition nodes with properties: description
- Procedure nodes with properties: description
- Relationships: HAS_CONDITION, UNDERWENT
"""


def generate_cypher(state: GraphState) -> GraphState:
    """Generate Cypher query from natural language question"""
    question = state["question"]
    cypher_query = llm_service.generate_cypher(question, SCHEMA)
    state["cypher_query"] = cypher_query
    return state


def execute_neo4j_query(state: GraphState) -> GraphState:
    """Execute Cypher query against Neo4j"""
    try:
        results = neo4j_service.execute_query(state["cypher_query"])
        state["neo4j_results"] = results
    except Exception as e:
        state["error"] = str(e)
    return state


def interpret_results(state: GraphState) -> GraphState:
    """Use LLM to interpret results and generate answer"""
    question = state["question"]
    results = state["neo4j_results"]
    answer = llm_service.interpret_results(question, results)
    state["final_answer"] = answer
    return state