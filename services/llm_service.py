from langchain_openai import ChatOpenAI
from config import get_settings


class LLMService:
    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            api_key=settings.openai_api_key,
            temperature=0
        )

    def generate_cypher(self, question: str, schema: str) -> str:
        """Generate Cypher query from natural language"""
        prompt = f"""Convert this question to a Neo4j Cypher query.

Question: {question}

Graph Schema:
{schema}

IMPORTANT Cypher Syntax Rules:
- After WITH with aggregation (e.g., count(), sum()), you CANNOT reference variables from before the WITH clause
- Example CORRECT: MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) WITH p, count(c) as conditionCount WHERE conditionCount > 1 RETURN p
- Example WRONG: MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter) WITH p, count(e) as numEncounters WHERE e.baseCost > 100 (CANNOT use 'e' after WITH)
- For expensive treatments: Aggregate costs in WITH clause, then filter in WHERE
- Example: MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter) WITH p, sum(e.totalCost) as totalCost WHERE totalCost > 10000 RETURN p

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