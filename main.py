from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.workflow import graph

app = FastAPI(title="Healthcare GraphRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://d1vhufjc9w8vpb.cloudfront.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str


@app.get("/")
async def root():
    return {"message": "Healthcare GraphRAG API", "status": "running"}


@app.post("/ask")
async def ask_question(q: Question):
    """Ask a question about the healthcare data"""

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
        "confidence": 0.0
    }

    # Run the graph
    result = graph.invoke(initial_state)

    return {
        "question": result["question"],
        "cypher_query": result["cypher_query"],
        "answer": result["final_answer"],
        "error": result.get("error", "")
    }
