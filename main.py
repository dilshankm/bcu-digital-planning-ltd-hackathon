from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from graph.workflow import graph  # Use LangGraph workflow
from services.conversation_service import conversation_service
from services.neo4j_service import Neo4jService
from services.csv_import_service import CSVImportService


def _remove_embeddings(obj):
    """Recursively remove embedding fields from any nested structure"""
    if isinstance(obj, dict):
        return {k: _remove_embeddings(v) for k, v in obj.items() 
                if k not in ['embedding', '_text_repr']}
    elif isinstance(obj, list):
        return [_remove_embeddings(item) for item in obj]
    else:
        return obj


def _get_node_display_name(node: Dict[str, Any]) -> str:
    """Generate a human-readable display name for a node"""
    label = node.get("label", "Unknown")
    properties = node.get("properties", {})
    
    # Patient: Use firstName + lastName
    if label == "Patient":
        first = properties.get("firstName", "")
        last = properties.get("lastName", "")
        if first or last:
            return f"{first} {last}".strip() or f"Patient {node.get('id', '')}"
        return f"Patient {node.get('id', '')}"
    
    # Condition: Use description
    if label == "Condition":
        desc = properties.get("description", "")
        if desc:
            return desc[:50]  # Truncate long descriptions
        return f"Condition {node.get('id', '')}"
    
    # Encounter: Use description or date
    if label == "Encounter":
        desc = properties.get("description", "")
        if desc:
            return desc[:50]
        start = properties.get("start", "")
        if start:
            return f"Encounter ({start[:10]})"  # Date only
        return f"Encounter {node.get('id', '')}"
    
    # Procedure: Use description
    if label == "Procedure":
        desc = properties.get("description", "")
        if desc:
            return desc[:50]
        return f"Procedure {node.get('id', '')}"
    
    # Observation: Use description or code
    if label == "Observation":
        desc = properties.get("description", "")
        if desc:
            return desc[:50]
        code = properties.get("code", "")
        if code:
            return f"Observation ({code})"
        return f"Observation {node.get('id', '')}"
    
    # Default: Use label + first property value
    if properties:
        first_key = list(properties.keys())[0]
        first_val = str(properties[first_key])[:30]
        return f"{label} ({first_key}={first_val})"
    
    return f"{label} {node.get('id', '')}"
# Import UploadFile conditionally to avoid startup crash if python-multipart missing
try:
    from fastapi import UploadFile, File
    MULTIPART_AVAILABLE = True
except ImportError:
    MULTIPART_AVAILABLE = False
    # Dummy classes for type hints
    class UploadFile:
        pass
    class File:
        pass

app = FastAPI(title="Healthcare GraphRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://d1vhufjc9w8vpb.cloudfront.net",
        "http://graph-rag-alb-890224410.eu-central-1.elb.amazonaws.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str
    session_id: Optional[str] = None  # For multi-turn conversations


class ExploreRequest(BaseModel):
    node_id: Optional[int] = None
    node_type: Optional[str] = None
    limit: int = 20


@app.get("/")
async def root():
    return {"message": "Healthcare GraphRAG API", "status": "running"}


@app.post("/ask")
async def ask_question(q: Question, response: Response):
    """Ask a question about the healthcare data (supports multi-turn conversations)"""
    import asyncio
    
    # Prevent CloudFront caching for API responses
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    # Handle session management - create automatically if not provided
    session_id = q.session_id
    if not session_id:
        try:
            session_id = conversation_service.create_session()
        except Exception as e:
            # If session creation fails, continue without session (single-turn mode)
            session_id = None
    
    # Get conversation history if session exists
    conversation_history = ""
    if session_id:
        try:
            conversation_history = conversation_service.get_conversation_context(session_id, max_messages=5)
            # Add user question to conversation
            conversation_service.add_message(session_id, "user", q.question)
        except Exception:
            # If session fails, continue without conversation history
            session_id = None
    
    # Initialize state for LangGraph workflow
    initial_state = {
        "question": q.question,
        "cypher_query": "",
        "neo4j_results": [],
        "final_answer": "",
        "error": "",
        "query_embedding": [],
        "similar_nodes": [],
        "subgraph": {"nodes": [], "relationships": []},
        "context": "",
        "plan": "",
        "messages": [],
        "step": 0,
        "max_steps": 6,
        "decision": "",
        "confidence": 0.0,
        "session_id": session_id,
        "conversation_history": conversation_history,
        "refinement_count": 0
    }

    try:
        # Use LangGraph workflow (pure LangGraph, no LangChain)
        result = await asyncio.wait_for(
            asyncio.to_thread(graph.invoke, initial_state),
            timeout=60.0
        )
        
        # Add assistant response to conversation if session exists
        if session_id:
            try:
                conversation_service.add_message(
                    session_id, 
                    "assistant", 
                    result["final_answer"],
                    metadata={"cypher_query": result.get("cypher_query", "")}
                )
            except Exception:
                pass  # Continue even if message logging fails
        
        # Enrich traversal paths with readable node information
        nodes_dict = {}
        nodes_used = result.get("subgraph", {}).get("nodes", [])
        
        # Remove embeddings from nodes to avoid huge response size
        clean_nodes_used = []
        for node in nodes_used:
            node_id = str(node.get("id", ""))
            clean_node = {k: v for k, v in node.items() if k not in ['embedding', '_text_repr']}
            # Also clean properties dict if it exists
            if 'properties' in clean_node and isinstance(clean_node['properties'], dict):
                clean_node['properties'] = {k: v for k, v in clean_node['properties'].items() 
                                           if k not in ['embedding', '_text_repr']}
            clean_nodes_used.append(clean_node)
            
            nodes_dict[node_id] = {
                "label": clean_node.get("label", "Unknown"),
                "properties": clean_node.get("properties", {}),
                "display_name": _get_node_display_name(clean_node)
            }
        
        # Enrich relationships with readable information
        enriched_paths = []
        relationships = result.get("subgraph", {}).get("relationships", [])
        for rel in relationships:
            start_id = str(rel.get("start", ""))
            end_id = str(rel.get("end", ""))
            start_node = nodes_dict.get(start_id, {"label": "Unknown", "display_name": f"Node {start_id}"})
            end_node = nodes_dict.get(end_id, {"label": "Unknown", "display_name": f"Node {end_id}"})
            
            enriched_paths.append({
                "start_id": start_id,
                "start_label": start_node["label"],
                "start_name": start_node["display_name"],
                "type": rel.get("type", "UNKNOWN"),
                "end_id": end_id,
                "end_label": end_node["label"],
                "end_name": end_node["display_name"],
                "path_display": f"{start_node['display_name']} ({start_node['label']}) --{rel.get('type', 'UNKNOWN')}--> {end_node['display_name']} ({end_node['label']})"
            })
        
        response = {
            "question": result["question"],
            "cypher_query": result.get("cypher_query", ""),
            "answer": result["final_answer"],
            "error": result.get("error", ""),
            "session_id": session_id,
            # Stretch Goals: Visualization and Explainability
            "traversal_paths": enriched_paths,
            "nodes_used": clean_nodes_used,
            "similar_nodes_found": result.get("similar_nodes", []),
            "plan": result.get("plan", ""),
            "steps_taken": result.get("step", 0),
            "confidence": result.get("confidence", 0.0)
        }
        
        # Recursively remove ALL embeddings from response
        return _remove_embeddings(response)
    except asyncio.TimeoutError:
        error_msg = "Request timed out. The query may be too complex. Please try a simpler question."
        if session_id:
            try:
                conversation_service.add_message(session_id, "system", error_msg)
            except Exception:
                pass
        return {
            "question": q.question,
            "cypher_query": "",
            "answer": error_msg,
            "error": "Timeout: Query exceeded 60 second limit",
            "session_id": session_id
        }
    except Exception as e:
        error_msg = str(e)
        if session_id:
            try:
                conversation_service.add_message(session_id, "system", f"Error: {error_msg}")
            except Exception:
                pass
        return {
            "question": q.question,
            "cypher_query": "",
            "answer": "",
            "error": error_msg,
            "session_id": session_id
        }


@app.post("/session")
async def create_session():
    """Create a new conversation session - returns immediately"""
    try:
        session_id = conversation_service.create_session()
        return {"session_id": session_id, "status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.get("/session/health")
async def session_health():
    """Health check for session service"""
    return {"status": "ready", "service": "conversation"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get conversation history for a session"""
    session = conversation_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/explore/nodes")
async def explore_nodes(
    node_type: Optional[str] = None, 
    label: Optional[str] = None, 
    limit: int = 20,
    skip: int = 0,
    search: Optional[str] = None
):
    """Explore nodes in the graph with pagination and search"""
    neo4j_service = Neo4jService()
    try:
        # Support both 'label' (frontend) and 'node_type' (backend) parameters
        node_label = label or node_type
        
        # Build query with filters
        if node_label:
            base_query = f"MATCH (n:{node_label})"
        else:
            base_query = "MATCH (n)"
        
        # Add search filter if provided
        where_clause = ""
        if search:
            # Search in common properties (firstName, lastName, description, etc.)
            where_clause = """
            WHERE toLower(toString(n.firstName)) CONTAINS toLower($search) 
               OR toLower(toString(n.lastName)) CONTAINS toLower($search)
               OR toLower(toString(n.description)) CONTAINS toLower($search)
               OR toLower(toString(n.id)) CONTAINS toLower($search)
            """
        
        # Get total count for pagination
        count_query = base_query + where_clause.replace("$search", f"'{search}'") if search else base_query
        count_query = count_query.replace("MATCH", "MATCH") + " RETURN count(n) as total"
        total_result = neo4j_service.execute_query(count_query)
        total_count = total_result[0].get("total", 0) if total_result else 0
        
        # Get paginated results
        query = base_query + where_clause + """
        RETURN id(n) as id, labels(n) as labels, properties(n) as properties 
        ORDER BY id(n) 
        SKIP $skip LIMIT $limit
        """
        
        params = {"skip": skip, "limit": limit}
        if search:
            params["search"] = search
        
        results = neo4j_service.execute_query(query, params)
        
        # Format nodes for UI (remove embeddings, add display names)
        formatted_nodes = []
        for node in results:
            clean_node = {k: v for k, v in node.items() if k not in ['embedding', '_text_repr']}
            if 'properties' in clean_node and isinstance(clean_node['properties'], dict):
                clean_node['properties'] = {k: v for k, v in clean_node['properties'].items() 
                                          if k not in ['embedding', '_text_repr']}
            # Add display name
            if isinstance(clean_node.get('properties'), dict):
                props = clean_node['properties']
                if 'firstName' in props and 'lastName' in props:
                    clean_node['display_name'] = f"{props['firstName']} {props['lastName']}"
                elif 'description' in props:
                    clean_node['display_name'] = props['description'][:50]
                else:
                    clean_node['display_name'] = f"{clean_node.get('labels', ['Unknown'])[0]} {clean_node.get('id', '')}"
            formatted_nodes.append(clean_node)
        
        return {
            "nodes": formatted_nodes,
            "count": len(formatted_nodes),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "ui_controls": {
                "zoom": {
                    "shortcuts": {
                        "+": "Zoom in",
                        "-": "Zoom out",
                        "0": "Fit to view",
                        "R": "Reset view",
                        "Space": "Pause animation",
                        "Esc": "Deselect"
                    },
                    "buttons": {
                        "position": "top-right",
                        "show": True
                    }
                },
                "legend": {
                    "show": False
                },
                "filters": {
                    "show": False
                },
                "canvas": {
                    "width": "100%",
                    "height": "100vh",
                    "min_height": "800px"
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/explore/node/{node_id}")
async def explore_node(node_id: int, depth: int = 1):
    """Explore a specific node and its neighbors - returns formatted data for graph visualization"""
    neo4j_service = Neo4jService()
    try:
        # Get the node itself first
        node_query = f"MATCH (n) WHERE id(n) = $node_id RETURN id(n) as id, labels(n) as labels, properties(n) as properties"
        node_result = neo4j_service.execute_query(node_query, {"node_id": node_id})
        
        if not node_result:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        
        # Get subgraph
        subgraph = neo4j_service.expand_subgraph([node_id], depth=depth)
        
        # Format nodes for UI (remove embeddings, add display names)
        formatted_nodes = []
        for node in subgraph.get("nodes", []):
            clean_node = {k: v for k, v in node.items() if k not in ['embedding', '_text_repr']}
            if 'properties' in clean_node and isinstance(clean_node['properties'], dict):
                clean_node['properties'] = {k: v for k, v in clean_node['properties'].items() 
                                          if k not in ['embedding', '_text_repr']}
                # Add display name
                props = clean_node['properties']
                if 'firstName' in props and 'lastName' in props:
                    clean_node['display_name'] = f"{props['firstName']} {props['lastName']}"
                elif 'description' in props:
                    clean_node['display_name'] = props['description'][:50]
                else:
                    clean_node['display_name'] = f"{clean_node.get('label', 'Unknown')} {clean_node.get('id', '')}"
            formatted_nodes.append(clean_node)
        
        # Format relationships
        formatted_rels = []
        for rel in subgraph.get("relationships", []):
            formatted_rels.append({
                "source": rel.get("start"),
                "target": rel.get("end"),
                "type": rel.get("type"),
                "label": rel.get("type", "UNKNOWN")
            })
        
        return {
            "node_id": node_id,
            "node": formatted_nodes[0] if formatted_nodes else None,
            "nodes": formatted_nodes,
            "relationships": formatted_rels,
            "depth": depth,
            "node_count": len(formatted_nodes),
            "relationship_count": len(formatted_rels),
            "ui_controls": {
                "zoom": {
                    "shortcuts": {
                        "+": "Zoom in",
                        "-": "Zoom out",
                        "0": "Fit to view",
                        "R": "Reset view",
                        "Space": "Pause animation",
                        "Esc": "Deselect"
                    },
                    "buttons": {
                        "position": "top-right",
                        "show": True
                    }
                },
                "legend": {
                    "show": False
                },
                "filters": {
                    "show": False
                },
                "canvas": {
                    "width": "100%",
                    "height": "100vh",
                    "min_height": "800px"
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/explore/relationships")
async def explore_relationships(
    rel_type: Optional[str] = None, 
    limit: int = 50,
    skip: int = 0
):
    """Explore relationships in the graph with pagination"""
    neo4j_service = Neo4jService()
    try:
        # Build query
        if rel_type:
            base_query = f"MATCH (a)-[r:{rel_type}]->(b)"
        else:
            base_query = "MATCH (a)-[r]->(b)"
        
        # Get total count
        count_query = base_query + " RETURN count(r) as total"
        total_result = neo4j_service.execute_query(count_query)
        total_count = total_result[0].get("total", 0) if total_result else 0
        
        # Get paginated results
        query = base_query + """
        RETURN id(a) as start, labels(a)[0] as start_label, 
               type(r) as type, properties(r) as properties,
               id(b) as end, labels(b)[0] as end_label
        ORDER BY id(a), id(b)
        SKIP $skip LIMIT $limit
        """
        
        results = neo4j_service.execute_query(query, {"skip": skip, "limit": limit})
        
        # Format for UI
        formatted_rels = []
        for rel in results:
            formatted_rels.append({
                "source": rel.get("start"),
                "target": rel.get("end"),
                "type": rel.get("type"),
                "label": rel.get("type", "UNKNOWN"),
                "source_label": rel.get("start_label"),
                "target_label": rel.get("end_label"),
                "properties": {k: v for k, v in (rel.get("properties") or {}).items() 
                             if k not in ['embedding', '_text_repr']}
            })
        
        return {
            "relationships": formatted_rels,
            "count": len(formatted_rels),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "ui_controls": {
                "zoom": {
                    "shortcuts": {
                        "+": "Zoom in",
                        "-": "Zoom out",
                        "0": "Fit to view",
                        "R": "Reset view",
                        "Space": "Pause animation",
                        "Esc": "Deselect"
                    },
                    "buttons": {
                        "position": "top-right",
                        "show": True
                    }
                },
                "legend": {
                    "show": False
                },
                "filters": {
                    "show": False
                },
                "canvas": {
                    "width": "100%",
                    "height": "100vh",
                    "min_height": "800px"
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/explore/stats")
@app.get("/statistics")  # Alias for frontend compatibility
async def get_stats():
    """Get database statistics for UI dashboard"""
    neo4j_service = Neo4jService()
    try:
        # Get node counts per type
        node_counts_query = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """
        node_counts = neo4j_service.execute_query(node_counts_query)
        
        # Get relationship counts per type
        rel_counts_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """
        rel_counts = neo4j_service.execute_query(rel_counts_query)
        
        # Get total counts
        total_nodes_query = "MATCH (n) RETURN count(n) as total"
        total_rels_query = "MATCH ()-[r]->() RETURN count(r) as total"
        total_nodes_result = neo4j_service.execute_query(total_nodes_query)
        total_rels_result = neo4j_service.execute_query(total_rels_query)
        
        total_nodes = total_nodes_result[0].get("total", 0) if total_nodes_result else 0
        total_rels = total_rels_result[0].get("total", 0) if total_rels_result else 0
        
        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "node_counts": {item["label"]: item["count"] for item in node_counts},
            "relationship_counts": {item["type"]: item["count"] for item in rel_counts}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/schema")
async def get_schema():
    """Get the graph schema information"""
    return {
        "node_types": ["Patient", "Encounter", "Condition", "Procedure", "Observation"],
        "relationship_types": [
            "HAD_ENCOUNTER", "HAS_CONDITION", "UNDERWENT", "HAS_OBSERVATION",
            "DIAGNOSED", "HAD_PROCEDURE", "RECORDED_OBSERVATION"
        ],
        "schema_description": "Healthcare graph with patient encounters, conditions, procedures, and observations"
    }


@app.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    node_type: str = None,
    properties: str = None
):
    """Import CSV data to extend the graph schema"""
    if not node_type:
        raise HTTPException(status_code=400, detail="node_type is required")
    
    if not properties:
        raise HTTPException(status_code=400, detail="properties (comma-separated) is required")
    
    # Read CSV content
    content = await file.read()
    csv_content = content.decode('utf-8')
    
    # Parse properties
    property_list = [p.strip() for p in properties.split(",")]
    
    # Import
    import_service = CSVImportService()
    try:
        result = import_service.import_csv(csv_content, node_type, property_list)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        import_service.close()
