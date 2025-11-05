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

    CRITICAL PROPERTY RULES:
    - Patient has NO 'age' property! Use birthDate and calculate age: duration.between(date(p.birthDate), date()).years
    - For "over 65": WHERE duration.between(date(p.birthDate), date()).years > 65
    - For "past year": WHERE e.stop > datetime() - duration({{years: 1}})
    - Observation category is 'vital-signs' (not 'blood pressure' or 'Blood Pressure')

    IMPORTANT Cypher Syntax Rules:
    - After WITH with aggregation (e.g., count(), sum()), you CANNOT reference variables from before the WITH clause
    - Example CORRECT: MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) WITH p, count(c) as conditionCount WHERE conditionCount > 1 RETURN p
    - Example WRONG: MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e:Encounter) WITH p, count(e) as numEncounters WHERE e.baseCost > 100 (CANNOT use 'e' after WITH)
    - When collecting variables in WITH, include ALL variables you need in RETURN: WITH p, count(c) as conditionCount, collect(c.description) as conditions
    - For counting patterns: Use COUNT {{}} not size(): MATCH (c:Condition) WITH c, COUNT {{ (c)<-[:HAS_CONDITION]-() }} as patientCount
    - RETURN must be at END of query - cannot have RETURN in middle then continue with more clauses

    MULTIPLE CONDITIONS (AND logic):
    - For "both X and Y": Use MATCH twice with WHERE on each, then return patients who match both
    - Example CORRECT: MATCH (p:Patient)-[:HAS_CONDITION]->(c1:Condition) WHERE toLower(c1.description) CONTAINS 'hypertension' WITH p MATCH (p)-[:HAS_CONDITION]->(c2:Condition) WHERE toLower(c2.description) CONTAINS 'obesity' RETURN p

    DATE/TIME CALCULATIONS:
    - Use duration() for date differences: duration.between(datetime(e.start), datetime(e.stop))
    - For "within 30 days": Use duration.between(...).days <= 30
    - For "past year": datetime() - duration({{years: 1}})

    TEXT MATCHING RULES - ALWAYS USE CONTAINS:
    - NEVER use exact match {{description: "value"}} - ALWAYS use CONTAINS
    - Example CORRECT: WHERE toLower(c.description) CONTAINS 'diabetes'
    - Example WRONG: WHERE c.description = "Diabetes" OR {{description: "Diabetes"}}
    - Use case-insensitive matching: toLower(c.description) CONTAINS 'diabetes'
    - For blood pressure: WHERE toLower(o.description) CONTAINS 'blood pressure'

    ONLY USE RELATIONSHIPS THAT EXIST:
    - Available: HAD_ENCOUNTER, HAS_CONDITION, DIAGNOSED, UNDERWENT, HAD_PROCEDURE, HAS_OBSERVATION, RECORDED_OBSERVATION
    - Do NOT invent relationships like FOLLOWED_BY

Return ONLY the Cypher query, nothing else."""

        response = self.llm.invoke(prompt)
        return response.content.strip()

    def interpret_results(self, question: str, results: list) -> str:
        """Interpret Neo4j results into natural language"""
        import json
        
        # Format results as clean JSON without embeddings
        if not results:
            result_data = "No matching records found."
        else:
            # Extract ONLY firstName and lastName - nothing else
            limited = results[:50] if len(results) > 50 else results
            formatted_results = []
            for item in limited:
                record = item
                # If single-key nested (e.g., {'p': {...}}), extract inner dict
                if isinstance(item, dict) and len(item) == 1:
                    record = list(item.values())[0]
                
                # Extract ONLY name fields
                if isinstance(record, dict):
                    clean_record = {}
                    if 'firstName' in record:
                        clean_record['firstName'] = record['firstName']
                    if 'lastName' in record:
                        clean_record['lastName'] = record['lastName']
                    if clean_record:
                        formatted_results.append(clean_record)
            
            # Format as simple JSON with ONLY names
            result_data = f"Found {len(results)} total patients. Here are their names:\n{json.dumps(formatted_results, indent=2)}"
        
        result_summary = result_data
        
        prompt = f"""You are a helpful healthcare data assistant. Answer the user's question ONLY using the data provided below.

User's Question: {question}

Data provided: {result_summary}

IMPORTANT - How to read the data:
- The data is in JSON format
- Each record has "firstName" and "lastName" fields
- Count the records in the JSON array - that's how many patients match
- Extract firstName and lastName from EACH record to list patient names

CRITICAL RULES - READ CAREFULLY:
- DO NOT hallucinate or invent any information not in the data above
- NEVER EVER mention: "Cypher", "query", "database", "graph", "nodes", "relationships", "context", or ANY technical terms
- DO NOT say "based on the query results" or "the data shows" or "according to the information"
- DO NOT explain how you got the answer - JUST GIVE THE ANSWER
- ONLY use facts, numbers, names explicitly in the data above
- Answer as if you naturally know this information, not as if you're reading it from somewhere

Answer Format - FOLLOW EXACTLY:
- If asked "Which patients...", list ALL patient names from the JSON data (e.g., "John Smith, Jane Doe, Bob Johnson have diabetes")
- If there are many results (more than 10), give a count AND list first 10 names: "72 patients have diabetes: John Smith, Jane Doe, Bob Johnson, ... and 62 others"
- Start with the direct fact: "There are 72 patients" NOT "Based on the data, there are 72 patients"
- Use plain English, as if talking to a friend
- Format names as: firstName lastName (e.g., "Kyong970 Bechtelar572")
- Be brief and clear
- NEVER mention where the data came from

Example GOOD answer: "There are 72 patients with diabetes: Kyong970 Bechtelar572, David908 Adams676, John123 Smith456, ... and 69 others."
Example BAD answer: "There are 0 patients" (when records are provided in JSON)

Provide ONLY the direct, natural answer now:"""

        response = self.llm.invoke(prompt)
        return response.content