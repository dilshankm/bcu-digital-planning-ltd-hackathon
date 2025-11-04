#!/bin/bash

failed=(
  "Show patients with at least one observation related to blood pressure."
  "Which patients are over 65 and have multiple chronic conditions?"
  "Find patients who had a procedure within 30 days of a diabetes diagnosis."
  "Which patients have not had any encounters in the past year?"
  "Which encounters included a diabetes diagnosis?"
  "Which encounters were for cardiac-related reasons?"
  "Which encounters recorded blood pressure observations?"
  "List encounters with missing stop dates."
  "Which conditions appear in more than 50 patients?"
  "Which conditions are often followed by procedures within 30 days?"
)

echo "Diagnosing 10 failed questions..."
echo ""

for i in "${!failed[@]}"; do
  q="${failed[$i]}"
  num=$((i + 1))
  echo "[$num/10] $q"
  
  response=$(curl -s -X POST http://localhost:8080/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}")
  
  cypher=$(echo "$response" | jq -r '.cypher_query // "NO CYPHER"')
  answer=$(echo "$response" | jq -r '.answer // "NO ANSWER"')
  error=$(echo "$response" | jq -r '.error // ""')
  
  echo "   Cypher: ${cypher:0:120}..."
  
  if [ -n "$error" ]; then
    echo "   ❌ ERROR: $error"
  elif [ -z "$answer" ] || [ "$answer" = "NO ANSWER" ] || [ "$answer" = "" ]; then
    echo "   ❌ EMPTY ANSWER (query may have returned 0 results)"
  else
    echo "   ✅ Has answer: ${answer:0:80}..."
  fi
  echo ""
done

