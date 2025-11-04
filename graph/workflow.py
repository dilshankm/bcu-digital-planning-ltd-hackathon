from langgraph.graph import StateGraph, END
from graph.state import GraphState
from graph.nodes import (
    generate_cypher,
    execute_neo4j_query,
    interpret_results,
    ensure_vector_index,
    embed_question,
    similarity_search,
    expand_traversal,
    build_subgraph_context,
    planner_agent,
    retriever_agent,
    cypher_agent,
    synthesizer_agent,
    planner_decide,
    router_next_action,
    refine_query,
)


def create_workflow():
    """Create the GraphRAG workflow"""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("ensure_vector_index", ensure_vector_index)
    workflow.add_node("embed_question", embed_question)
    workflow.add_node("similarity_search", similarity_search)
    workflow.add_node("expand_traversal", expand_traversal)
    workflow.add_node("build_context", build_subgraph_context)
    workflow.add_node("generate_cypher", generate_cypher)
    workflow.add_node("execute_query", execute_neo4j_query)
    workflow.add_node("interpret", interpret_results)

    # Define edges (flow)
    # Primary path using autonomous planner and router
    workflow.add_node("planner_decide", planner_decide)
    workflow.add_node("retriever_agent", retriever_agent)
    workflow.add_node("cypher_agent", cypher_agent)
    workflow.add_node("refine_query", refine_query)
    workflow.add_node("synthesizer_agent", synthesizer_agent)

    workflow.set_entry_point("planner_decide")
    workflow.add_conditional_edges(
        "planner_decide",
        router_next_action,
        {
            "retriever_agent": "retriever_agent",
            "cypher_agent": "cypher_agent",
            "refine_query": "refine_query",
            "execute_query": "execute_query",
            "synthesizer_agent": "synthesizer_agent",
            "END": END,
        },
    )

    # Loop back to planner after each action for agentic iteration
    workflow.add_edge("retriever_agent", "planner_decide")
    workflow.add_edge("cypher_agent", "planner_decide")
    workflow.add_edge("refine_query", "planner_decide")
    workflow.add_edge("execute_query", "planner_decide")
    # synthesizer_agent ends the flow via conditional mapping when planner decides "end"
    workflow.add_edge("synthesizer_agent", END)

    # Keep legacy linear path available but not used as entry
    workflow.add_edge("build_context", "generate_cypher")
    workflow.add_edge("generate_cypher", "execute_query")
    workflow.add_edge("interpret", END)
    workflow.add_edge("interpret", END)

    return workflow.compile()


# Create the compiled graph
graph = create_workflow()