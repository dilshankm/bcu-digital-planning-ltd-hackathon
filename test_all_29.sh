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

echo "🧪 Testing all 29 questions..."
echo ""

for i in "${!questions[@]}"; do
  q="${questions[$i]}"
  num=$((i + 1))
  echo "[$num/29] Testing: $q"
  
  answer=$(curl -s -X POST http://localhost:8080/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}" | jq -r '.answer // "ERROR"')
  
  # Check for technical jargon
  if echo "$answer" | grep -qi "graph\|cypher\|query\|database\|nodes\|relationships"; then
    echo "   ❌ CONTAINS TECHNICAL JARGON: $answer"
  elif [ "$answer" = "ERROR" ] || [ -z "$answer" ]; then
    echo "   ❌ NO ANSWER"
  else
    echo "   ✅ Clean answer: ${answer:0:100}..."
  fi
  echo ""
done

echo "✅ All 29 questions tested!"

