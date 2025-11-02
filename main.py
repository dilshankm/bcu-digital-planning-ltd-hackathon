from fastapi import FastAPI
from pydantic import BaseModel
from graph.workflow import graph

app = FastAPI(title="Healthcare GraphRAG API")


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
        "error": ""
    }

    # Run the graph
    result = graph.invoke(initial_state)

    return {
        "question": result["question"],
        "cypher_query": result["cypher_query"],
        "answer": result["final_answer"],
        "error": result.get("error", "")
    }
