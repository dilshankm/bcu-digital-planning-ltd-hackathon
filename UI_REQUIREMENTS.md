# UI Requirements for GraphRAG Core Features

## 🎯 Core Requirements - UI Implementation Guide

### 1. Generate Cypher Queries ✅
**Backend**: Already implemented - `/ask` endpoint returns `cypher_query`

**UI Requirements**:
- [ ] **Input Field**: Natural language question input (textarea or input field)
- [ ] **Submit Button**: Trigger API call to `/ask` endpoint
- [ ] **Cypher Query Display**: Show the generated Cypher query in a code block/syntax-highlighted area
  - Format: `cypher_query` from API response
  - Style: Code block with monospace font, Neo4j/Cypher syntax highlighting
  - Make it copyable (copy button)

**Example UI Component**:
```
┌─────────────────────────────────────────┐
│ Ask a question about healthcare data     │
├─────────────────────────────────────────┤
│ [Input: "Which patients have diabetes?"]│
│ [Submit Button]                         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Generated Cypher Query:                 │
├─────────────────────────────────────────┤
│ MATCH (p:Patient)-[:HAS_CONDITION]->    │
│   (c:Condition)                         │
│ WHERE c.description CONTAINS 'Diabetes' │
│ RETURN p                                │
│ [Copy]                                  │
└─────────────────────────────────────────┘
```

---

### 2. Retrieve Relevant Subgraphs ✅
**Backend**: Already implemented - `/ask` returns `traversal_paths`, `nodes_used`, `similar_nodes_found`

**UI Requirements**:
- [ ] **Subgraph Visualization**: Display the graph traversal paths visually
  - Show nodes as circles/boxes
  - Show relationships as arrows/edges
  - Use different colors for different node types (Patient=blue, Condition=red, etc.)
  - Use `traversal_paths` array to render edges
  - Use `nodes_used` array to render nodes

**UI Component Options**:
- **Option A**: Simple list view showing paths
  ```
  Graph Traversal Paths:
  • Patient → HAS_CONDITION → Condition
  • Patient → HAD_ENCOUNTER → Encounter
  • Encounter → DIAGNOSED → Condition
  ```

- **Option B**: Visual graph (using D3.js, Cytoscape.js, or vis.js)
  ```
  [Patient] --HAS_CONDITION--> [Condition]
  [Patient] --HAD_ENCOUNTER--> [Encounter] --DIAGNOSED--> [Condition]
  ```

- **Option C**: Collapsible tree view
  ```
  Patient
  ├─ HAS_CONDITION → Condition (Diabetes)
  └─ HAD_ENCOUNTER → Encounter
     └─ DIAGNOSED → Condition (Hypertension)
  ```

**Recommended**: Start with Option A (simple list) for MVP, upgrade to Option B (visual graph) for stretch goal

---

### 3. Leverage Graph Dependencies ✅
**Backend**: Already implemented - Shows dependency navigation in `traversal_paths`

**UI Requirements**:
- [ ] **Dependency Path Display**: Show how the query navigated through relationships
  - Display: `traversal_paths` array from API response
  - Format: "Patient → Condition → Encounter → Procedure"
  - Highlight which relationships were used
  - Show relationship types clearly

**UI Component**:
```
┌─────────────────────────────────────────┐
│ Graph Dependencies Used:               │
├─────────────────────────────────────────┤
│ Path 1: Patient → HAS_CONDITION →     │
│         Condition → Encounter →         │
│         HAD_PROCEDURE → Procedure       │
│                                         │
│ Path 2: Patient → HAD_ENCOUNTER →      │
│         Encounter → DIAGNOSED →         │
│         Condition                       │
└─────────────────────────────────────────┘
```

---

### 4. Combine Results with LLM Reasoning ✅
**Backend**: Already implemented - `/ask` returns `answer` (natural language)

**UI Requirements**:
- [ ] **Answer Display**: Show the LLM-generated answer prominently
  - Format: `answer` from API response
  - Style: Natural language, readable format
  - Position: Main content area

- [ ] **Explainability Panel**: Show which nodes/relationships contributed
  - Display: `nodes_used` array (which nodes were explored)
  - Display: `plan` (execution plan)
  - Display: `steps_taken` (how many workflow steps)
  - Display: `confidence` (confidence score 0-1)

**UI Component**:
```
┌─────────────────────────────────────────┐
│ Answer:                                 │
├─────────────────────────────────────────┤
│ Found 15 patients with multiple        │
│ chronic conditions. Common patterns    │
│ include diabetes, hypertension, and      │
│ heart disease. These patients had       │
│ average treatment costs of $125,000.    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Explainability:                         │
├─────────────────────────────────────────┤
│ • Nodes Explored: 45                    │
│ • Relationships Used: 12                 │
│ • Execution Steps: 4                    │
│ • Confidence: 0.85                      │
│ • Plan: [Retrieve → Query → Synthesize] │
└─────────────────────────────────────────┘
```

---

## 🎨 Complete UI Layout Recommendation

### Page Structure:
```
┌─────────────────────────────────────────────────────────────┐
│  Healthcare GraphRAG System                                  │
│  [Logo/Header]                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Question Input                                       │   │
│  │ [Textarea: "Ask a question about healthcare data"]  │   │
│  │ [Submit Button]                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Answer (Main Content)                                │   │
│  │ [Large text area showing natural language answer]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────┬──────────────────────────────┐   │
│  │ Generated Cypher      │  Graph Traversal Paths      │   │
│  │ [Code block]          │  [Visual/list of paths]     │   │
│  │ [Copy button]         │                             │   │
│  └──────────────────────┴──────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Explainability Panel                                 │   │
│  │ • Nodes Used: [...list...]                          │   │
│  │ • Steps Taken: 4                                    │   │
│  │ • Confidence: 0.85                                  │   │
│  │ • Execution Plan: [...]                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 UI Implementation Checklist

### MVP (Minimum Viable Product) - Core Requirements:

1. **Question Input**
   - [ ] Text input/textarea for natural language questions
   - [ ] Submit button
   - [ ] Loading state while API call is in progress

2. **Answer Display**
   - [ ] Large, readable text area showing `answer` from API
   - [ ] Markdown support for formatting (if needed)

3. **Cypher Query Display**
   - [ ] Code block showing `cypher_query`
   - [ ] Syntax highlighting (Cypher/Neo4j)
   - [ ] Copy button

4. **Graph Traversal Display** (Simple Version)
   - [ ] List/array showing `traversal_paths`
   - [ ] Format: "Patient → HAS_CONDITION → Condition"
   - [ ] Show `nodes_used` count

5. **Explainability Panel** (Simple Version)
   - [ ] Show `steps_taken`
   - [ ] Show `confidence` score
   - [ ] Show `plan` (if available)

### Enhanced Version (Stretch Goals):

6. **Visual Graph Display**
   - [ ] Interactive graph visualization using D3.js/Cytoscape.js
   - [ ] Node types with different colors
   - [ ] Clickable nodes to see properties
   - [ ] Animated traversal paths

7. **Query History**
   - [ ] Save previous questions/answers
   - [ ] Session support using `session_id`

8. **Advanced Explainability**
   - [ ] Expandable node details
   - [ ] Relationship property display
   - [ ] Step-by-step execution visualization

---

## 🔌 API Endpoints to Use

### Primary Endpoint:
```
POST /ask
Body: { "question": "Which patients have diabetes?" }
Response: {
  "question": "...",
  "cypher_query": "...",
  "answer": "...",
  "traversal_paths": [...],
  "nodes_used": [...],
  "similar_nodes_found": [...],
  "plan": "...",
  "steps_taken": 3,
  "confidence": 0.85,
  "session_id": "..."
}
```

### Additional Endpoints (for exploration):
```
GET /explore/nodes?node_type=Patient&limit=20
GET /explore/node/{node_id}?depth=1
GET /explore/relationships?rel_type=HAS_CONDITION&limit=50
GET /schema
POST /session (create new session)
GET /session/{session_id} (get conversation history)
```

---

## 🎯 Priority Order for UI Development

### Phase 1: Core MVP (Start Here)
1. Question input + Submit button
2. Answer display
3. Cypher query display (with copy button)

### Phase 2: Graph Dependencies
4. Traversal paths display (simple list)
5. Nodes used count

### Phase 3: Explainability
6. Steps taken
7. Confidence score
8. Execution plan

### Phase 4: Enhancement (Stretch Goals)
9. Visual graph display
10. Query history
11. Interactive node exploration

---

## 💡 Example UI Code Structure (React/Vue/Vanilla JS)

```javascript
// Example API call
async function askQuestion(question) {
  const response = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  });
  const data = await response.json();
  
  // Display:
  // - data.answer (main answer)
  // - data.cypher_query (Cypher code)
  // - data.traversal_paths (graph paths)
  // - data.nodes_used (nodes explored)
  // - data.steps_taken (workflow steps)
  // - data.confidence (confidence score)
  // - data.plan (execution plan)
}

// Format traversal paths for display
function formatTraversalPaths(paths) {
  return paths.map(path => {
    return `${path.start} --${path.type}--> ${path.end}`;
  }).join('\n');
}
```

---

## ✅ Summary: What UI Needs to Show

### **MUST HAVE** (Core Requirements):
1. ✅ Question input field
2. ✅ Natural language answer display
3. ✅ Generated Cypher query display
4. ✅ Graph traversal paths (simple list format)

### **SHOULD HAVE** (Better UX):
5. ✅ Explainability panel (steps, confidence, plan)
6. ✅ Loading states
7. ✅ Error handling

### **NICE TO HAVE** (Stretch Goals):
8. ✅ Visual graph visualization
9. ✅ Query history
10. ✅ Interactive node exploration

---

## 🚀 Quick Start for UI Developer

1. **Create a simple form** with question input and submit button
2. **Call `/ask` endpoint** with question text
3. **Display 4 things**:
   - Answer (main text)
   - Cypher query (code block)
   - Traversal paths (list of relationships)
   - Explainability (steps, confidence)

That's it for MVP! Then enhance with visualizations and advanced features.

