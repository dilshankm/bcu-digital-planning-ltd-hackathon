from graph.state import GraphState
from services.neo4j_service import Neo4jService
from services.llm_service import LLMService
from services.neo4j_vector_store_service import Neo4jVectorStoreService  # Neo4j native vector search
from services.embedding_service import EmbeddingService
from services.dspy_service import DSPyService
from services.conversation_service import conversation_service


neo4j_service = Neo4jService()
llm_service = LLMService()
# Use Neo4j native vector store for similarity search
neo4j_vector_service = Neo4jVectorStoreService()
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
        cypher = state.get("cypher_query", "")
        print(cypher)
        if not cypher:
            print("   ⚠️  No Cypher query to execute.")
            return state
        print(f"   🔍 Executing Cypher query...")
        results = neo4j_service.execute_query(cypher)
        state["neo4j_results"] = results
        print(f"   ✅ Query executed. Found {len(results)} results.")
    except Exception as e:
        state["error"] = str(e)
        print(f"   ❌ Query execution failed: {e}")
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
    """Bootstrap the vector index from Neo4j nodes if empty (Neo4j native, no LangChain)."""
    try:
        count = neo4j_vector_service.count()
        if count == 0:
            nodes = neo4j_service.fetch_all_nodes()
            # Bootstrap with small batch to avoid token limits
            neo4j_vector_service.upsert_nodes(nodes[:10])
    except Exception as e:
        print(f"⚠️  Vector index setup failed: {e}")
    return state


def embed_question(state: GraphState) -> GraphState:
    question = state["question"]
    embedding = embedding_service.embed_text(question)
    state["query_embedding"] = embedding
    return state


def similarity_search(state: GraphState) -> GraphState:
    # Use Neo4j native vector search (no LangChain)
    try:
        hits = neo4j_vector_service.similarity_search(state["question"], top_k=3)
        state["similar_nodes"] = hits
    except Exception as e:
        print(f"⚠️  Vector search failed: {e}")
        state["similar_nodes"] = []
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
    """Synthesize final answer using LLM (pure LangGraph, no LangChain)"""
    print("\n🎨 [SYNTHESIZER AGENT] Synthesizing answer...")
    question = state["question"]
    context = state.get("context", "")
    results = state.get("neo4j_results", [])
    cypher_query = state.get("cypher_query", "")
    
    # Build comprehensive context from graph results and subgraph
    # Extract ONLY essential fields to avoid token overflow
    # Even 10 full patient records = 48K tokens! We only need names for listing
    # Limit to reasonable number to avoid token overflow, but pass enough for accurate counts
    # For patient lists, we extract only firstName/lastName so 200 records is ~10K tokens (safe)
    limited_results = results[:200] if len(results) > 200 else results
    clean_results = []
    for r in limited_results:
        # Check if this is aggregated data (COUNT, SUM, etc.) or a patient record
        if isinstance(r, dict):
            # Check if this is aggregated data BEFORE extracting nested values
            # IMPORTANT: Don't flag as aggregate if it has firstName/lastName fields (even with prefix like p.firstName)
            # Aggregate results only have count/sum/avg fields, never patient names
            has_patient_fields = any(
                'firstname' in key.lower() or 'lastname' in key.lower() 
                for key in r.keys() if isinstance(key, str)
            )
            
            aggregate_keywords = ['count', 'number', 'total', 'sum', 'avg', 'average', 'min', 'max', 'frequency']
            has_aggregate = any(any(keyword in key.lower() for keyword in aggregate_keywords)
                              for key in r.keys() if isinstance(key, str))
            
            # Only treat as aggregate if it has aggregate keywords AND no patient fields
            # Records with conditionCount + firstName/lastName are patient records, not aggregates
            if has_aggregate and not has_patient_fields:
                # True aggregate result (like {"numberOfPatients": 100}) - pass through as-is
                clean_results.append(r)
            else:
                # Not aggregated - check if it's a nested node like {'p': {...}}
                if len(r) == 1:
                    # Extract the nested node (e.g., 'p', 'c', 'e')
                    r = list(r.values())[0]
                
                # CRITICAL: Remove embeddings after extraction
                if isinstance(r, dict):
                    r = {k: v for k, v in r.items() if k not in ['embedding', '_text_repr']}
                    
                    # Handle different result formats:
                    # 1. Direct properties: {'firstName': 'John', 'lastName': 'Doe'}
                    # 2. Prefixed properties: {'p.firstName': 'John', 'p.lastName': 'Doe', 'Procedure.description': '...'}
                    # 3. Nested nodes: {'p': {...}, 'Procedure': {...}}
                    clean_r = {}
                    
                    # Check for direct firstName/lastName
                    if 'firstName' in r:
                        clean_r['firstName'] = r['firstName']
                    if 'lastName' in r:
                        clean_r['lastName'] = r['lastName']
                    
                    # Check for prefixed properties (e.g., 'p.firstName', 'Procedure.description', 'e.id')
                    for key, value in r.items():
                        if key.endswith('.firstName') or key.endswith('.lastName'):
                            field_name = key.split('.')[-1]
                            clean_r[field_name] = value
                        elif key.endswith('.description'):
                            clean_r['description'] = value
                        elif key == 'id' or key.endswith('.id'):
                            clean_r['id'] = value
                        elif key.endswith('.start') or key.endswith('.stop'):
                            clean_r[key.split('.')[-1]] = value
                        elif key.endswith('.reasonDescription'):
                            clean_r['reason'] = value
                    
                    # If still no data, check if values are nested dicts (e.g., {'p': {...}, 'Procedure': {...}, 'e': {...}})
                    if not clean_r and len(r) > 0:
                        # Check if single key is a node (e.g., {'e': {...}})
                        if len(r) == 1:
                            node_value = list(r.values())[0]
                            if isinstance(node_value, dict):
                                # Extract common fields from any node type
                                if 'firstName' in node_value:
                                    clean_r['firstName'] = node_value['firstName']
                                if 'lastName' in node_value:
                                    clean_r['lastName'] = node_value['lastName']
                                if 'description' in node_value:
                                    clean_r['description'] = node_value['description']
                                if 'id' in node_value:
                                    clean_r['id'] = node_value['id']
                                if 'start' in node_value:
                                    clean_r['start'] = node_value['start']
                                if 'stop' in node_value:
                                    clean_r['stop'] = node_value['stop']
                                if 'reasonDescription' in node_value:
                                    clean_r['reason'] = node_value['reasonDescription']
                        # Multiple keys - might be {'p': {...}, 'Procedure': {...}, 'e': {...}}
                        elif len(r) > 1:
                            for key, value in r.items():
                                if isinstance(value, dict):
                                    # Extract from nested dict
                                    if 'firstName' in value:
                                        clean_r['firstName'] = value['firstName']
                                    if 'lastName' in value:
                                        clean_r['lastName'] = value['lastName']
                                    if 'description' in value:
                                        clean_r['description'] = value['description']
                                    if 'id' in value:
                                        clean_r['id'] = value['id']
                                    if 'start' in value:
                                        clean_r['start'] = value['start']
                                    if 'stop' in value:
                                        clean_r['stop'] = value['stop']
                                    if 'reasonDescription' in value:
                                        clean_r['reason'] = value['reasonDescription']
                    
                    if clean_r:  # Only add if we extracted something
                        clean_results.append(clean_r)
                    else:
                        # If we still have no clean_r but r has data, include a minimal version
                        # This handles cases where nodes don't have standard fields
                        if isinstance(r, dict) and r:
                            # Include at least the raw dict keys to help LLM understand structure
                            minimal = {k: str(v)[:50] if not isinstance(v, (dict, list)) else type(v).__name__ 
                                      for k, v in list(r.items())[:5]}  # Limit to first 5 fields
                            if minimal:
                                clean_results.append(minimal)
    
    truncated_context = context[:3000] if len(context) > 3000 else context
    
    # If no results, provide a helpful message (user-friendly, no Cypher mention)
    if not results or len(results) == 0:
        answer = (
            f"I couldn't find any information matching your question: '{question}'\n\n"
            f"This might mean:\n"
            f"- No patients or records match the specific criteria you're looking for\n"
            f"- The search terms might need to be adjusted (e.g., try broader terms)\n"
            f"- The data might not be available in the database"
        )
        state["final_answer"] = answer
        print(f"   ⚠️  No results found. Providing helpful message.")
        return state
    
    # Use simple LLM interpretation directly - more reliable than DSPy multi-agent
    # DSPy was too cautious and often returned vague/empty answers even with good data
    print(f"   📊 Passing {len(clean_results)} results to LLM.")
    if clean_results:
        print(f"   🔍 Sample clean result (first): {clean_results[0] if clean_results else 'NONE'}")
        print(f"   🔍 Clean results have names: {any('firstName' in str(r) or 'lastName' in str(r) for r in clean_results[:3])}")
    try:
        answer = llm_service.interpret_results(question, clean_results)
        print(f"   🤖 LLM returned: '{answer[:200] if answer else 'EMPTY/NONE'}'")
    except Exception as e:
        print(f"   ❌ LLM interpretation failed: {e}")
        answer = f"I found {len(results)} matching records but encountered an error interpreting them: {str(e)}"
    
    # Ensure answer is not empty and doesn't contain technical jargon
    if not answer or len(answer.strip()) < 10:
        answer = f"I found {len(results)} matching records, but I'm having trouble summarizing them. Please try rephrasing your question or asking for more specific information."
    
    # AGGRESSIVE filter for technical terms and vague language that users shouldn't see
    banned_phrases = [
        "graph context", "graph", "cypher query", "cypher", "database query", 
        "query results", "the query", "nodes", "relationships", "neo4j",
        "based on the", "according to the", "the data shows", "the information shows",
        "in the context", "from the context", "to identify", "we need to analyze",
        "available information"
    ]
    answer_lower = answer.lower()
    for phrase in banned_phrases:
        if phrase in answer_lower:
            # Try to clean up the answer
            if phrase == "graph context":
                answer = answer.replace("graph context", "system")
                answer = answer.replace("Graph context", "system")
            elif phrase in ["cypher query", "cypher"]:
                answer = answer.replace("cypher query", "system").replace("Cypher query", "system")
                answer = answer.replace("cypher", "").replace("Cypher", "")
            elif phrase in ["the query", "query results", "database query"]:
                answer = answer.replace("query results", "results").replace("Query results", "Results")
                answer = answer.replace("the query", "the search").replace("The query", "The search")
            # If too many technical terms, fall back to simple LLM interpretation
            if sum(1 for p in banned_phrases[:7] if p in answer_lower) >= 2:
                print(f"   ⚠️  Answer contains too many technical terms. Re-generating with strict prompt.")
                answer = llm_service.interpret_results(question, limited_results)
                break
    
    state["final_answer"] = answer
    print(f"   ✅ Answer synthesized!")
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
    error = state.get("error", "")
    context = state.get("context", "")
    
    if not cypher:
        print("   ⏭️  No query to refine. Skipping.")
        return state
    
    # Check if there was a syntax error or if results are empty
    if error or len(results) == 0:
        error_context = f"Error: {error}\n\n" if error else ""
        refinement_prompt = (
            f"{error_context}"
            f"The Cypher query failed or returned no results:\n{cypher}\n\n"
            f"Original question: {question}\n\n"
            f"Analyze why this query might have failed and suggest an improved query "
            f"that is more likely to return results. Consider:\n"
            f"- Syntax errors: After WITH/aggregation, you cannot reference variables from before the WITH clause\n"
            f"- CRITICAL: When using multiple WITH clauses, you must include ALL variables you need in each WITH\n"
            f"- If you use collect() or count() on a variable, include it in WITH: WITH p, count(c) as conditionCount, collect(c.description) as conditions\n"
            f"- Example CORRECT: MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) WITH p, count(c) as conditionCount, collect(c.description) as conditions WHERE conditionCount > 1 RETURN p.firstName, p.lastName, conditions\n"
            f"- Example WRONG: WITH p, count(c) as conditionCount WHERE conditionCount > 1 RETURN collect(c.description) (c is not available after WITH)\n"
            f"- CRITICAL FIX FOR 'Variable c not defined': Move collect(c.description) INTO the WITH clause, not the RETURN clause\n"
            f"- If error mentions 'Variable `c` not defined', change: WITH p, count(c) as count ... RETURN collect(c.description) TO: WITH p, count(c) as count, collect(c.description) as descriptions ... RETURN descriptions\n"
            f"- For multiple conditions: MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) WITH p, count(c) as conditionCount WHERE conditionCount > 1 RETURN p\n"
            f"- For expensive treatments: Check Encounter.totalCost or Procedure baseCost\n"
            f"- TEXT MATCHING: Use CONTAINS for partial text matching, not exact match {{description: \"value\"}}\n"
            f"- Example: WHERE c.description CONTAINS 'Diabetes' (not {{description: \"Diabetes\"}})\n"
            f"- Use case-insensitive matching: toLower(c.description) CONTAINS toLower('diabetes')\n"
            f"- Relaxing WHERE constraints if needed\n"
            f"- Expanding relationship patterns\n"
        )
        refined_cypher = llm_service.generate_cypher(refinement_prompt, SCHEMA)
        state["cypher_query"] = refined_cypher
        state["neo4j_results"] = []  # Reset to re-execute
        state["error"] = ""  # Clear error
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

    # Get state variables before checking step limit
    question = state.get("question", "")
    context = state.get("context", "")
    cypher = state.get("cypher_query", "")
    results = state.get("neo4j_results", [])
    
    if step > max_steps:
        state["decision"] = "end"
        state["confidence"] = 0.5
        print(f"   ⚠️  Step budget exceeded. Ending workflow.")
        _append_message(state, "planner", f"Step budget exceeded ({step}>{max_steps}). Ending.")
        
        # If we have results but no answer yet, try to synthesize one
        if not state.get("final_answer") and results is not None:
            if len(results) == 0:
                state["final_answer"] = f"I couldn't find any information matching your question: '{question}'. No records match the specific criteria."
            else:
                # Try to synthesize answer from existing results
                try:
                    limited_results = results[:50] if len(results) > 50 else results
                    clean_results = []
                    for r in limited_results:
                        if isinstance(r, dict):
                            r_clean = {k: v for k, v in r.items() if k not in ['embedding', '_text_repr']}
                            clean_results.append(r_clean)
                    answer = llm_service.interpret_results(question, clean_results)
                    state["final_answer"] = answer if answer else f"I found {len(results)} matching records."
                except:
                    state["final_answer"] = f"I found {len(results)} matching records but couldn't synthesize a complete answer."
        
        return state
    refinement_count = state.get("refinement_count", 0)
    error = state.get("error", "")

    # Heuristic policy for autonomous routing
    if not context:
        decision = "retrieve"
        rationale = "No graph context yet; retrieve similar nodes and expand subgraph."
    elif not cypher:
        decision = "query"
        rationale = "Have context but no Cypher; generate Cypher next."
    elif cypher and (results is None or len(results) == 0):
        # Check if we should refine or execute
        if refinement_count < 1 and error:
            # Only refine if there was an error and we haven't refined yet
            decision = "refine"
            rationale = "Have Cypher but error occurred; try refining the query."
            state["refinement_count"] = refinement_count + 1
        else:
            # Execute query first before trying refinement
            decision = "execute"
            rationale = "Have Cypher but no results; execute query first."
    elif len(results) > 100:
        # Too many results - refine (only once)
        if refinement_count == 0:
            decision = "refine"
            rationale = "Too many results; refine query to be more specific."
            state["refinement_count"] = refinement_count + 1
        else:
            # Already refined once, just use what we have
            decision = "answer"
            rationale = "Have results (already refined once); synthesize answer."
    elif cypher and len(results) > 0:
        # Have results - synthesize answer
        decision = "answer"
        rationale = "Have context and results; synthesize final answer."
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