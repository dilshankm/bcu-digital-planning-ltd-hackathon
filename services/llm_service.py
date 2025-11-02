from langchain_openai import ChatOpenAI
from config import get_settings


class LLMService:
    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            model="gpt-4",
            api_key=settings.openai_api_key,
            temperature=0
        )

    def generate_cypher(self, question: str, schema: str) -> str:
        """Generate Cypher query from natural language"""
        prompt = f"""Convert this question to a Neo4j Cypher query.

Question: {question}

Graph Schema:
{schema}

Return ONLY the Cypher query, nothing else."""

        response = self.llm.invoke(prompt)
        return response.content.strip()

    def interpret_results(self, question: str, results: list) -> str:
        """Interpret Neo4j results into natural language"""
        prompt = f"""Question: {question}

Database Results: {results}

Provide a clear, natural language answer based on these results."""

        response = self.llm.invoke(prompt)
        return response.content