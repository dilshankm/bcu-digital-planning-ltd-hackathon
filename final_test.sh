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

pass=0
fail_empty=0
fail_technical=0

for i in "${!questions[@]}"; do
  q="${questions[$i]}"
  
  answer=$(curl -s -X POST http://localhost:8080/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}" | jq -r '.answer // ""' 2>/dev/null)
  
  if [ -z "$answer" ]; then
    ((fail_empty++))
  elif echo "$answer" | grep -Eqi "graph|cypher|query.*database|nodes|relationships"; then
    ((fail_technical++))
  else
    ((pass++))
  fi
done

echo "=========================================="
echo "FINAL RESULTS FOR ALL 29 QUESTIONS:"
echo "=========================================="
echo "✅ PASSED (human-readable): $pass"
echo "❌ FAILED (empty answer): $fail_empty"
echo "❌ FAILED (technical jargon): $fail_technical"
echo "=========================================="
echo "Total: 29 questions"

