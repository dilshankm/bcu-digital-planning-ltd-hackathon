#!/bin/bash

echo "Testing 5 sample questions..."

questions=(
  "How many patients are there?"
  "Which patients have diabetes?"
  "What is the average total cost per encounter class?"
  "Which conditions are most frequently diagnosed?"
  "Which patients have more than three chronic conditions?"
)

for i in "${!questions[@]}"; do
  q="${questions[$i]}"
  num=$((i + 1))
  echo ""
  echo "[$num/5] Q: $q"
  
  answer=$(curl -s -X POST http://localhost:8080/ask \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}" | jq -r '.answer // empty')
  
  if [ -z "$answer" ]; then
    echo "   ❌ NO ANSWER RETURNED"
  elif echo "$answer" | grep -Eqi "graph|cypher|query.*database|nodes|relationships|context"; then
    echo "   ❌ TECHNICAL JARGON DETECTED:"
    echo "   $answer"
  else
    echo "   ✅ CLEAN:"
    echo "   $answer"
  fi
done

echo ""
echo "Done!"

