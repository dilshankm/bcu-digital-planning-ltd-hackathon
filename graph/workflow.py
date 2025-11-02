from langgraph.graph import StateGraph, END
from graph.state import GraphState
from graph.nodes import generate_cypher, execute_neo4j_query, interpret_results


def create_workflow():
    """Create the GraphRAG workflow"""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("generate_cypher", generate_cypher)
    workflow.add_node("execute_query", execute_neo4j_query)
    workflow.add_node("interpret", interpret_results)

    # Define edges (flow)
    workflow.set_entry_point("generate_cypher")
    workflow.add_edge("generate_cypher", "execute_query")
    workflow.add_edge("execute_query", "interpret")
    workflow.add_edge("interpret", END)

    return workflow.compile()


# Create the compiled graph
graph = create_workflow()