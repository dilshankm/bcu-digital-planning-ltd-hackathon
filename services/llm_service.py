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
    - For counting patterns: NEVER use size() - ALWAYS use COUNT {{}}: 
      * WRONG: size((c)<-[:HAS_CONDITION]-())
      * CORRECT: COUNT {{ (c)<-[:HAS_CONDITION]-(:Patient) }} as patientCount
      * Example: MATCH (c:Condition) WITH c, COUNT {{ (c)<-[:HAS_CONDITION]-(:Patient) }} as patientCount WHERE patientCount > 50 RETURN c.description, patientCount
    - RETURN must be at END of query - cannot have RETURN in middle then continue with more clauses
    - When returning Encounter nodes, always include readable fields: RETURN e.id, e.description, e.start, e.stop OR RETURN e (if you need full node)
    - For missing/null values: Use IS NULL or IS NOT NULL: WHERE e.stop IS NULL

    MULTIPLE CONDITIONS (AND logic):
    - For "both X and Y": Use MATCH twice with WHERE on each, then return patients who match both
    - Example CORRECT: MATCH (p:Patient)-[:HAS_CONDITION]->(c1:Condition) WHERE toLower(c1.description) CONTAINS 'hypertension' WITH p MATCH (p)-[:HAS_CONDITION]->(c2:Condition) WHERE toLower(c2.description) CONTAINS 'obesity' RETURN p

    DATE/TIME CALCULATIONS:
    - Use duration() for date differences: duration.between(datetime(e.start), datetime(e.stop))
    - For "within 30 days": Use duration.between(...).days <= 30
    - For "past year": datetime() - duration({{years: 1}})
    - For condition duration: Use HAS_CONDITION relationship properties: (p)-[r:HAS_CONDITION]->(c) WHERE r.start and r.stop exist
    - Example: MATCH (p:Patient)-[r:HAS_CONDITION]->(c:Condition) WHERE r.start IS NOT NULL AND r.stop IS NOT NULL RETURN c.description, AVG(duration.between(datetime(r.start), datetime(r.stop)).days) as avgDuration
    - CRITICAL: When comparing dates between encounters/procedures, use encounter dates NOT patient birthDate
    - Example CORRECT (procedure within 30 days of diagnosis): MATCH (p:Patient)-[:HAD_ENCOUNTER]->(e1:Encounter)-[:DIAGNOSED]->(c:Condition), (p)-[:HAD_ENCOUNTER]->(e2:Encounter)-[:HAD_PROCEDURE]->(pr:Procedure) WHERE toLower(c.description) CONTAINS 'diabetes' AND duration.between(datetime(e1.stop), datetime(e2.start)).days <= 30 AND duration.between(datetime(e1.stop), datetime(e2.start)).days >= 0
    - Example WRONG: duration.between(datetime(e.stop), datetime(p.birthDate)) - NEVER compare encounter dates with birthDate!

    TEXT MATCHING RULES - ALWAYS USE CONTAINS:
    - NEVER use exact match {{description: "value"}} - ALWAYS use CONTAINS
    - Example CORRECT: WHERE toLower(c.description) CONTAINS 'diabetes'
    - Example WRONG: WHERE c.description = "Diabetes" OR {{description: "Diabetes"}}
    - Use case-insensitive matching: toLower(c.description) CONTAINS 'diabetes'
    - For blood pressure: WHERE toLower(o.description) CONTAINS 'blood pressure'
    - For cardiac/heart: Use toLower() with CONTAINS: WHERE toLower(e.reasonDescription) CONTAINS 'cardiac' OR toLower(e.reasonDescription) CONTAINS 'heart'
    - IMPORTANT: When using toLower() on properties that might be NULL, check NULL first: WHERE o.category IS NOT NULL AND toLower(o.category) = 'vital-signs'
    - For Observation category: ALWAYS check NULL first! Use: WHERE (o.category IS NOT NULL AND toLower(o.category) = 'vital-signs') OR toLower(o.description) CONTAINS 'blood pressure'
    - NEVER use toLower() directly on properties that might be NULL without checking first
    - Example CORRECT: WHERE (o.category IS NOT NULL AND toLower(o.category) = 'vital-signs') OR toLower(o.description) CONTAINS 'blood pressure'
    - Example WRONG: WHERE toLower(o.category) = 'vital-signs' AND toLower(o.description) CONTAINS 'blood pressure' (will fail if category is NULL)

    ONLY USE RELATIONSHIPS THAT EXIST:
    - Available: HAD_ENCOUNTER, HAS_CONDITION, DIAGNOSED, UNDERWENT, HAD_PROCEDURE, HAS_OBSERVATION, RECORDED_OBSERVATION
    - Do NOT invent relationships like FOLLOWED_BY
    - For conditions followed by procedures: Use DIAGNOSED on Encounter, then HAD_PROCEDURE on same Encounter
    - Example: MATCH (e:Encounter)-[:DIAGNOSED]->(c:Condition), (e)-[:HAD_PROCEDURE]->(p:Procedure) WHERE duration.between(datetime(e.start), datetime(e.stop)).days <= 30
    
    COMMON QUERY PATTERNS:
    - Average conditions per patient: MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition) WITH p, count(c) as conditionCount RETURN avg(conditionCount) as averageConditionsPerPatient
    - Condition categories: Condition nodes don't have baseCost or totalCost - use Encounter.baseCost/totalCost instead. Example: MATCH (e:Encounter)-[:DIAGNOSED]->(c:Condition) WITH c, MAX(e.baseCost) as maxCost RETURN c.description, maxCost ORDER BY maxCost DESC
    - Average encounter cost per condition: MATCH (e:Encounter)-[:DIAGNOSED]->(c:Condition) WITH c, AVG(e.totalCost) as avgCost RETURN c.description, avgCost ORDER BY avgCost DESC
    - Missing dates: WHERE e.stop IS NULL (returns encounters with null stop dates). Always return readable fields: RETURN e.id, e.description, e.start, e.stop
    - When returning averages/counts, always return the value directly: RETURN avg(conditionCount) as averageConditionsPerPatient (not wrapped in another structure)
    - Conditions followed by procedures: Use Encounter as bridge - Conditions are DIAGNOSED on Encounters, Procedures are HAD_PROCEDURE on same Encounter
    - Example: MATCH (e:Encounter)-[:DIAGNOSED]->(c:Condition), (e)-[:HAD_PROCEDURE]->(p:Procedure) WHERE duration.between(datetime(e.start), datetime(e.stop)).days <= 30 RETURN DISTINCT c.description, p.description

Return ONLY the Cypher query, nothing else."""

        response = self.llm.invoke(prompt)
        query = response.content.strip()
        
        # Remove duplicate queries if LLM generated multiple (sometimes happens)
        lines = query.split('\n')
        seen_queries = set()
        unique_lines = []
        current_query = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # Check if this is a new query start (MATCH, WITH, RETURN at start)
            if line_stripped.upper().startswith(('MATCH', 'WITH', 'RETURN', 'CALL')):
                query_key = line_stripped[:50]  # Use first 50 chars as key
                if query_key not in seen_queries:
                    seen_queries.add(query_key)
                    if current_query:
                        unique_lines.extend(current_query)
                        unique_lines.append('')
                    current_query = [line]
                else:
                    # Duplicate query detected, skip
                    current_query = []
                    continue
            elif current_query:
                current_query.append(line)
        
        if current_query:
            unique_lines.extend(current_query)
        
        # Join back and take first query if multiple detected
        cleaned_query = '\n'.join(unique_lines).strip()
        if not cleaned_query:
            cleaned_query = query
        
        # If still has duplicates, just take first occurrence
        if cleaned_query.count('RETURN') > 1:
            first_return_idx = cleaned_query.find('RETURN')
            second_match_idx = cleaned_query.find('MATCH', first_return_idx)
            if second_match_idx > 0:
                cleaned_query = cleaned_query[:second_match_idx].strip()
        
        return cleaned_query

    def interpret_results(self, question: str, results: list) -> str:
        """Interpret Neo4j results into natural language"""
        import json
        
        # Format results as clean JSON without embeddings
        if not results:
            result_data = "No matching records found."
        else:
            # Check if results contain aggregated data (like COUNT) or patient records
            first_result = results[0] if results else {}
            
            # If it's aggregated data (e.g., {"numberOfPatients": 100}), pass it directly
            aggregate_keywords = ['count', 'number', 'total', 'sum', 'avg', 'average', 'min', 'max', 'frequency']
            has_aggregate = isinstance(first_result, dict) and any(
                any(keyword in key.lower() for keyword in aggregate_keywords)
                for key in first_result.keys() if isinstance(key, str)
            )
            
            if has_aggregate:
                # Aggregated data - pass as-is
                result_data = json.dumps(results, indent=2)
            else:
                # Patient records - extract ONLY firstName and lastName
                # Don't limit here - pass all results (LLM will handle truncation in answer format)
                limited = results
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
- If asked "Which patients...", list ALL patient names from the JSON data
- COUNT the total number of records in the JSON array - that's the correct count
- If there are 50 or fewer results, list ALL names: "There are 106 patients: John Smith, Jane Doe, Bob Johnson, ..." (all 106 names)
- If there are more than 50 results, give a count AND list first 50 names: "200 patients have diabetes: John Smith, Jane Doe, Bob Johnson, ... and 150 others"
- Start with the direct fact: "There are 106 patients" NOT "Based on the data, there are 106 patients"
- Use plain English, as if talking to a friend
- Format names as: firstName lastName (e.g., "Kyong970 Bechtelar572")
- Be brief and clear
- NEVER mention where the data came from
- CRITICAL: Count the actual number of records in the JSON array. If JSON has 106 records, say "106 patients" not "14 patients"!

Example GOOD answer (106 patients): "There are 106 patients with more than three chronic conditions: [list all 106 names]."
Example GOOD answer (200 patients): "There are 200 patients with diabetes: [first 50 names], ... and 150 others."
Example BAD answer: "There are 14 patients: [only lists 6]" when JSON has 106 records - COUNT THE RECORDS!

Provide ONLY the direct, natural answer now:"""

        response = self.llm.invoke(prompt)
        return response.content