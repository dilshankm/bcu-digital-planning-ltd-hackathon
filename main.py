from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from graph.workflow import graph
from services.conversation_service import conversation_service
from services.neo4j_service import Neo4jService
from services.csv_import_service import CSVImportService
from fastapi import UploadFile, File

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
async def ask_question(q: Question):
    """Ask a question about the healthcare data (supports multi-turn conversations)"""
    import asyncio
    
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
    
    # Initialize state
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
        # Run the graph with timeout (60 seconds)
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
        
        return {
            "question": result["question"],
            "cypher_query": result["cypher_query"],
            "answer": result["final_answer"],
            "error": result.get("error", ""),
            "session_id": session_id
        }
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
async def explore_nodes(node_type: Optional[str] = None, label: Optional[str] = None, limit: int = 20):
    """Explore nodes in the graph - supports both 'node_type' and 'label' parameters for compatibility"""
    neo4j_service = Neo4jService()
    try:
        # Support both 'label' (frontend) and 'node_type' (backend) parameters
        node_label = label or node_type
        if node_label:
            query = f"MATCH (n:{node_label}) RETURN id(n) as id, labels(n) as labels, properties(n) as properties LIMIT {limit}"
        else:
            query = f"MATCH (n) RETURN id(n) as id, labels(n) as labels, properties(n) as properties LIMIT {limit}"
        results = neo4j_service.execute_query(query)
        return {"nodes": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/explore/node/{node_id}")
async def explore_node(node_id: int, depth: int = 1):
    """Explore a specific node and its neighbors"""
    neo4j_service = Neo4jService()
    try:
        subgraph = neo4j_service.expand_subgraph([node_id], depth=depth)
        return {
            "node_id": node_id,
            "subgraph": subgraph,
            "depth": depth
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@app.get("/explore/relationships")
async def explore_relationships(rel_type: Optional[str] = None, limit: int = 50):
    """Explore relationships in the graph"""
    neo4j_service = Neo4jService()
    try:
        if rel_type:
            query = f"MATCH (a)-[r:{rel_type}]->(b) RETURN id(a) as start, type(r) as type, id(b) as end, properties(r) as properties LIMIT {limit}"
        else:
            query = f"MATCH (a)-[r]->(b) RETURN id(a) as start, type(r) as type, id(b) as end, properties(r) as properties LIMIT {limit}"
        results = neo4j_service.execute_query(query)
        return {"relationships": results, "count": len(results)}
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
