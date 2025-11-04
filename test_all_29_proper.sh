#!/bin/bash

questions=(
  "Which patients have diabetes?"
  "Which patients have more than three chronic conditions?"
  "Show patients who have both hypertension and obesity."
  "Which patients have had encounters costing more than \$10,000?"
  "Find patients with conditions diagnosed in more than 5 encounters."
  "Which patients underwent a heart-related procedure?"
  "Show patients with at least one observation related to blood pressure."
  "Which patients are over 65 and have multiple chronic conditions?"
  "Find patients who had a procedure within 30 days of a diabetes diagnosis."
  "Which patients have not had any encounters in the past year?"
  "Which encounters included a diabetes diagnosis?"
  "What is the average total cost per encounter class?"
  "Which encounters had both a diagnosis and a procedure?"
  "Find encounters where total cost exceeded base cost by more than 50%."
  "Which encounters were for cardiac-related reasons?"
  "Find encounters lasting longer than 7 days."
  "Which encounters recorded blood pressure observations?"
  "List encounters with missing stop dates."
  "Which encounters had multiple diagnoses?"
  "What is the total and average encounter cost across all encounters?"
  "Which conditions are most frequently diagnosed?"
  "Which conditions most often co-occur in patients?"
  "What is the average encounter cost per condition?"
  "Which conditions have the longest average duration in patients?"
  "Which conditions appear in more than 50 patients?"
  "Which conditions are often followed by procedures within 30 days?"
  "Which condition categories have the highest base cost encounters?"
  "How many conditions are recorded per patient on average?"
  "Which conditions are least common in the dataset?"
)

echo "🧪 Testing ALL 29 questions for user-friendly answers..."
echo ""

pass=0
fail=0

for i in "${!questions[@]}"; do
  q="${questions[$i]}"
  num=$((i + 1))
  echo "[$num/29] $q"
  
  response=$(curl -s -X POST http://localhost:8080/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}" 2>&1)
  
  # Check if curl itself failed
  if [ $? -ne 0 ]; then
    echo "   ❌ CURL FAILED"
    ((fail++))
    continue
  fi
  
  # Extract answer field
  answer=$(echo "$response" | jq -r '.answer // empty' 2>/dev/null)
  
  # Check for empty answer
  if [ -z "$answer" ]; then
    echo "   ❌ NO ANSWER"
    ((fail++))
  # Check for technical jargon
  elif echo "$answer" | grep -Eqi "graph|cypher|query.*database|nodes|relationships"; then
    echo "   ❌ TECHNICAL JARGON: ${answer:0:80}..."
    ((fail++))
  else
    echo "   ✅ ${answer:0:100}..."
    ((pass++))
  fi
done

echo ""
echo "=========================================="
echo "RESULTS: $pass passed, $fail failed"
echo "=========================================="

