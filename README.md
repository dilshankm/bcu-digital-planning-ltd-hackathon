# Healthcare GraphRAG System

A Graph Retrieval-Augmented Generation (GraphRAG) system built with LangGraph, Neo4j, and OpenAI for querying healthcare data using natural language.

## 🏗️ Architecture

- **FastAPI** - REST API endpoints
- **LangGraph** - Workflow orchestration
- **Neo4j** - Graph database with healthcare data
- **OpenAI GPT-4** - Natural language to Cypher query generation

## 📋 Prerequisites

- Docker installed
- OpenAI API key
- Neo4j Aura account (or local Neo4j instance)

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/dilshankm/bcu-digital-planning-ltd-hackathon.git
cd bcu-digital-planning-ltd-hackathon
```

### 2. Set up environment variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
OPENAI_API_KEY=your-openai-api-key-here
NEO4J_URI=your-neo4j-uri-here
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password-here
```

### 3. Build and run with Docker
```bash
docker build -t hackathon-app .
docker run -p 8080:8080 hackathon-app
```

The API will be available at `http://localhost:8080`

## 📡 API Endpoints

### Health Check
```bash
curl http://localhost:8080/
```

### Ask a Question
```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients are in the database?"}'
```

## 🔧 Development

### Local Setup (without Docker)

1. Create virtual environment:
```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn main:app --reload --port 8080
```

## 📁 Project Structure
```
├── main.py                    # FastAPI application
├── config.py                  # Configuration management
├── graph/
│   ├── state.py              # LangGraph state definition
│   ├── nodes.py              # Graph node functions
│   └── workflow.py           # LangGraph workflow
├── services/
│   ├── neo4j_service.py      # Neo4j database service
│   └── llm_service.py        # OpenAI LLM service
├── Dockerfile                # Docker configuration
└── requirements.txt          # Python dependencies
```

## 🎯 How It Works

1. **User asks a question** in natural language
2. **LLM generates** a Cypher query from the question
3. **Neo4j executes** the query on the healthcare graph
4. **LLM interprets** the results into a natural language answer
5. **API returns** the answer to the user

## 📝 Example Queries

- "How many patients are in the database?"
- "Find patients with diabetes"
- "What procedures are most common?"
- "Show me patients with multiple chronic conditions"

## 🛠️ Technologies Used

- Python 3.10
- FastAPI
- LangGraph
- LangChain
- OpenAI GPT-4
- Neo4j
- Docker

## 📄 License

MIT License