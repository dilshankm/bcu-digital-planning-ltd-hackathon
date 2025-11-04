from graph.state import GraphState
from services.neo4j_service import Neo4jService
from services.llm_service import LLMService
from services.vector_store_service import VectorStoreService  # Keep as fallback
from services.neo4j_vector_store_service import Neo4jVectorStoreService  # Neo4j native (mentor's approach)
from services.embedding_service import EmbeddingService
from services.dspy_service import DSPyService
from services.conversation_service import conversation_service


neo4j_service = Neo4jService()
llm_service = LLMService()
# Use Neo4j native vector store (like mentor's notebooks) as primary
neo4j_vector_service = Neo4jVectorStoreService()
vector_service = VectorStoreService()  # Fallback if Neo4j vector index not available
embedding_service = EmbeddingService()
dspy_service = DSPyService()

SCHEMA = """
Neo4j Healthcare Graph Schema Summary

Node Types
- Patient(id, firstName, lastName, birthDate, deathDate, gender, race, ethnicity, marital, city, state, county, zip, income)
- Encounter(id, start, stop, encounterClass, code, description, baseCost, totalCost, reasonCode, reasonDescription)
- Condition(code, description, system)
- Procedure(code, description, system)
- Observation(code, description, category)

Relationship Types
- (Patient)-[:HAD_ENCOUNTER]->(Encounter)
- (Patient)-[:HAS_CONDITION {start, stop}]->(Condition)
- (Encounter)-[:DIAGNOSED]->(Condition)
- (Patient)-[:UNDERWENT]->(Procedure)
- (Encounter)-[:HAD_PROCEDURE {start, stop, baseCost, reasonCode, reasonDescription}]->(Procedure)
- (Patient)-[:HAS_OBSERVATION]->(Observation)
- (Encounter)-[:RECORDED_OBSERVATION {date, value, units, type}]->(Observation)

Common Query Patterns Examples
- Patient journey timeline via HAD_ENCOUNTER, DIAGNOSED, HAD_PROCEDURE, RECORDED_OBSERVATION
- Co-occurring patient conditions
- Condition to procedure co-occurrence
- High-risk patients (>=3 conditions)
- Utilization analysis (encounter counts, totalCost, avg cost)
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
    """Use DSPy agent with subgraph context to generate answer"""
    question = state["question"]
    context = state.get("context", "")
    # Fallback to LLMService if DSPy not available or context empty
    if not context:
        results = state["neo4j_results"]
        answer = llm_service.interpret_results(question, results)
    else:
        answer = dspy_service.answer(question, context)
    state["final_answer"] = answer
    return state


def ensure_vector_index(state: GraphState) -> GraphState:
    """Bootstrap the vector index from Neo4j nodes if empty (using Neo4j native vector index like mentor)."""
    # Use Neo4j native vector store (like mentor's notebooks)
    try:
        count = neo4j_vector_service.count()
        if count == 0:
            nodes = neo4j_service.fetch_all_nodes()
            # Bootstrap with small batch to avoid token limits
            neo4j_vector_service.upsert_nodes(nodes[:10])
    except Exception as e:
        # Fallback to Chroma if Neo4j vector index not available
        print(f"⚠️  Neo4j vector index not available, using Chroma fallback: {e}")
        if vector_service.collection.count() == 0:
            nodes = neo4j_service.fetch_all_nodes()
            vector_service.upsert_nodes(nodes[:10])
    return state


def embed_question(state: GraphState) -> GraphState:
    question = state["question"]
    embedding = embedding_service.embed_text(question)
    state["query_embedding"] = embedding
    return state


def similarity_search(state: GraphState) -> GraphState:
    # Use Neo4j native vector search (like mentor's notebooks)
    try:
        hits = neo4j_vector_service.similarity_search(state["question"], top_k=3)
    except Exception as e:
        # Fallback to Chroma if Neo4j vector index not available
        print(f"⚠️  Neo4j vector search failed, using Chroma fallback: {e}")
        hits = vector_service.similarity_search(state["question"], top_k=3)
    state["similar_nodes"] = hits
    return state


def expand_traversal(state: GraphState) -> GraphState:
    node_ids = [hit["id"] for hit in state.get("similar_nodes", [])]
    if not node_ids:
        state["subgraph"] = {"nodes": [], "relationships": []}
        return state
    # Reduce depth to 1 and limit expansion
    subgraph = neo4j_service.expand_subgraph(node_ids, depth=1)
    # Limit subgraph size
    if "nodes" in subgraph:
        subgraph["nodes"] = subgraph["nodes"][:20]
    if "relationships" in subgraph:
        subgraph["relationships"] = subgraph["relationships"][:30]
    state["subgraph"] = subgraph
    return state


def build_subgraph_context(state: GraphState) -> GraphState:
    subgraph = state.get("subgraph", {"nodes": [], "relationships": []})
    parts = []
    parts.append("NODES:")
    # Limit to 20 nodes max to prevent context overflow
    nodes = subgraph.get("nodes", [])[:20]
    for n in nodes:
        label = n.get("label")
        properties = n.get("properties", {})
        # Limit properties to first 3 key-value pairs
        kv_items = list(properties.items())[:3]
        kv = ", ".join(f"{k}={str(v)[:30]}" for k, v in kv_items)  # Truncate values
        parts.append(f"- ({n.get('id')}:{label} {{ {kv} }})")
    parts.append("RELATIONSHIPS:")
    # Limit to 30 relationships max
    relationships = subgraph.get("relationships", [])[:30]
    for r in relationships:
        parts.append(f"- ({r.get('start')})-[:{r.get('type')}]->({r.get('end')})")
    context = "\n".join(parts)
    # Truncate total context to 4000 chars (roughly 1000 tokens)
    if len(context) > 4000:
        context = context[:4000] + "... (truncated)"
    state["context"] = context
    return state


# Agent-style nodes

def planner_agent(state: GraphState) -> GraphState:
    question = state["question"]
    context = state.get("context", "")
    prompt = (
        "You are a planner agent. Given a question and optional graph context, "
        "produce a short step-by-step plan using available actions: "
        "[SIMILARITY_SEARCH, TRAVERSE_SUBGRAPH, GENERATE_CYPHER, EXECUTE_QUERY, SYNTHESIZE]. "
        "Be concise."
    )
    plan = llm_service.interpret_results(
        question=f"{prompt}\n\nQuestion: {question}",
        results=[{"context": context}]
    )
    state["plan"] = plan
    return state


def retriever_agent(state: GraphState) -> GraphState:
    # Ensure index, embed, search, expand, build context
    print("\n🔍 [RETRIEVER AGENT] Executing retrieval pipeline...")
    ensure_vector_index(state)
    embed_question(state)
    similarity_search(state)
    expand_traversal(state)
    build_subgraph_context(state)
    print(f"   ✅ Retrieved context ({len(state.get('context', ''))} chars)")
    return state


def cypher_agent(state: GraphState) -> GraphState:
    # Use both schema and built context to generate higher-precision Cypher
    print("\n💾 [CYPHER AGENT] Generating Cypher query...")
    question = state["question"]
    context = state.get("context", "")
    conversation_history = state.get("conversation_history", "")
    
    # Include conversation history if available
    if conversation_history:
        question_with_history = f"Previous conversation:\n{conversation_history}\n\nCurrent question: {question}"
    else:
        question_with_history = question
    
    augmented_schema = f"{SCHEMA}\n\nContext:\n{context}"
    cypher_query = llm_service.generate_cypher(question_with_history, augmented_schema)
    state["cypher_query"] = cypher_query
    print(f"   ✅ Generated: {cypher_query[:100]}...")
    return state


def synthesizer_agent(state: GraphState) -> GraphState:
    # Leverage DSPy multi-agent result synthesis over context + db results
    print("\n🎨 [SYNTHESIZER AGENT] Synthesizing final answer with DSPy multi-agent pipeline...")
    question = state["question"]
    context = state.get("context", "")
    results = state.get("neo4j_results", [])
    
    # Limit results to first 10 items and truncate each
    limited_results = []
    for r in results[:10]:
        if isinstance(r, dict):
            # Truncate each value in result dict
            limited_r = {k: str(v)[:100] if len(str(v)) > 100 else v for k, v in r.items()}
            limited_results.append(limited_r)
        else:
            limited_results.append(str(r)[:200])
    
    # Truncate context to 3000 chars (safe for gpt-3.5-turbo)
    truncated_context = context[:3000] if len(context) > 3000 else context
    
    if truncated_context or limited_results:
        results_str = str(limited_results)[:2000]  # Limit results string
        composite_context = f"Context:\n{truncated_context}\n\nResults:\n{results_str}"
        answer = dspy_service.answer(question, composite_context)
    else:
        answer = llm_service.interpret_results(question, limited_results)
    state["final_answer"] = answer
    print(f"   ✅ Final answer generated!")
    return state


def _append_message(state: GraphState, role: str, content: str) -> None:
    msgs = state.get("messages", [])
    msgs.append({"role": role, "content": content})
    state["messages"] = msgs


def refine_query(state: GraphState) -> GraphState:
    """Query refinement agent: analyzes results and improves query if needed"""
    print("\n🔄 [REFINEMENT AGENT] Analyzing results to refine query...")
    question = state.get("question", "")
    cypher = state.get("cypher_query", "")
    results = state.get("neo4j_results", [])
    context = state.get("context", "")
    
    if not cypher:
        print("   ⏭️  No query to refine. Skipping.")
        return state
    
    # Check if results are empty or too few
    if len(results) == 0:
        refinement_prompt = (
            f"The Cypher query returned no results:\n{cypher}\n\n"
            f"Original question: {question}\n\n"
            f"Analyze why this query might have failed and suggest an improved query "
            f"that is more likely to return results. Consider:\n"
            f"- Relaxing WHERE constraints\n"
            f"- Checking for typos or incorrect property names\n"
            f"- Using CONTAINS instead of exact matches\n"
            f"- Expanding relationship patterns\n"
        )
        refined_cypher = llm_service.generate_cypher(refinement_prompt, SCHEMA)
        state["cypher_query"] = refined_cypher
        state["neo4j_results"] = []  # Reset to re-execute
        print(f"   ✅ Refined query: {refined_cypher[:100]}...")
        _append_message(state, "refiner", f"Refined query: {refined_cypher}")
    elif len(results) > 100:
        # Too many results - refine to be more specific
        refinement_prompt = (
            f"The query returned {len(results)} results, which is too many.\n"
            f"Original query: {cypher}\n"
            f"Question: {question}\n\n"
            f"Suggest a more specific query with additional filters or constraints."
        )
        refined_cypher = llm_service.generate_cypher(refinement_prompt, SCHEMA)
        state["cypher_query"] = refined_cypher
        state["neo4j_results"] = []  # Reset to re-execute
        print(f"   ✅ Refined query to be more specific: {refined_cypher[:100]}...")
        _append_message(state, "refiner", f"Refined query for specificity: {refined_cypher}")
    else:
        print(f"   ✅ Results look good ({len(results)} items). No refinement needed.")
    
    return state


def planner_decide(state: GraphState) -> GraphState:
    """Autonomous planner that decides next action and updates loop counters."""
    # Increment step and enforce budget
    step = state.get("step", 0) + 1
    state["step"] = step
    max_steps = state.get("max_steps", 6)

    print(f"\n🎯 [PLANNER] Step {step}/{max_steps}")

    if step > max_steps:
        state["decision"] = "end"
        state["confidence"] = 0.5
        print(f"   ⚠️  Step budget exceeded. Ending workflow.")
        _append_message(state, "planner", f"Step budget exceeded ({step}>{max_steps}). Ending.")
        return state

    question = state.get("question", "")
    context = state.get("context", "")
    cypher = state.get("cypher_query", "")
    results = state.get("neo4j_results", [])
    refinement_count = state.get("refinement_count", 0)

    # Heuristic policy for autonomous routing
    if not context:
        decision = "retrieve"
        rationale = "No graph context yet; retrieve similar nodes and expand subgraph."
    elif not cypher:
        decision = "query"
        rationale = "Have context but no Cypher; generate Cypher next."
    elif cypher and (results is None or len(results) == 0) and refinement_count < 2:
        # Try refinement if we have a query but no results
        decision = "refine"
        rationale = "Have Cypher but no results; try refining the query."
        state["refinement_count"] = refinement_count + 1
    elif cypher and (results is None or len(results) == 0):
        decision = "execute"
        rationale = "Have Cypher but no results; execute query (refinement already attempted)."
    elif len(results) > 0 and refinement_count == 0 and len(results) > 100:
        # Too many results - refine
        decision = "refine"
        rationale = "Too many results; refine query to be more specific."
        state["refinement_count"] = refinement_count + 1
    elif cypher and (results is None or len(results) == 0):
        decision = "execute"
        rationale = "Have Cypher but no results; execute query."
    else:
        decision = "answer"
        rationale = "Have context and results; synthesize final answer."

    state["decision"] = decision
    state["confidence"] = 0.7
    print(f"   📋 Decision: {decision.upper()}")
    print(f"   💡 Rationale: {rationale}")
    _append_message(state, "planner", f"Decision: {decision}. Rationale: {rationale}")
    _append_message(state, "user", question)
    if context:
        _append_message(state, "context", context[:1000])
    return state


def router_next_action(state: GraphState) -> str:
    """Return the key for the next node based on planner decision."""
    decision = state.get("decision", "answer")
    mapping = {
        "retrieve": "retriever_agent",
        "query": "cypher_agent",
        "refine": "refine_query",
        "execute": "execute_query",
        "answer": "synthesizer_agent",
        "end": "END",
    }
    return mapping.get(decision, "synthesizer_agent")