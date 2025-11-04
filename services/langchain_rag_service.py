"""LangChain Neo4j RAG service (exactly like mentor's notebooks)"""
from typing import List, Dict, Any, Optional
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain.chains import RetrievalQAWithSourcesChain, GraphCypherQAChain
from langchain.prompts.prompt import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from config import get_settings


class LangChainRAGService:
    """LangChain RAG using Neo4jVector and GraphCypherQAChain (exactly like mentor's notebooks)"""
    
    def __init__(self):
        settings = get_settings()
        
        # Initialize Neo4j Graph (like notebook)
        self.kg = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=getattr(settings, 'neo4j_database', 'neo4j') or 'neo4j'
        )
        
        # Vector store constants (like notebook)
        self.index_name = 'node_embeddings'
        self.node_label = 'Node'  # Will match any node type
        self.text_property = '_text_repr'  # Text representation we store
        self.embedding_property = 'embedding'
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            api_key=settings.openai_api_key,
            temperature=0
        )
        
        # Will be initialized when vector index is ready
        self.vector_store = None
        self.retriever = None
        self.qa_chain = None
        self.cypher_chain = None
        
        # Cypher generation template (like Lesson 7)
        self._setup_cypher_chain()
    
    def _setup_cypher_chain(self):
        """Setup GraphCypherQAChain (like Lesson 7)"""
        CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.

Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Schema:
{schema}

Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.

Examples: Here are a few examples of generated Cypher statements for particular questions:

# How many patients are in the database?
MATCH (p:Patient)
RETURN count(p) as patientCount

# Which patients have diabetes?
MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
WHERE c.description CONTAINS 'Diabetes'
RETURN p.firstName, p.lastName, c.description

# What procedures were performed for patients with hypertension?
MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition),
      (p)-[:UNDERWENT]->(proc:Procedure)
WHERE c.description CONTAINS 'Hypertension'
RETURN proc.description, count(proc) as frequency
ORDER BY frequency DESC

The question is:
{question}"""
        
        CYPHER_GENERATION_PROMPT = PromptTemplate(
            input_variables=["schema", "question"], 
            template=CYPHER_GENERATION_TEMPLATE
        )
        
        try:
            self.cypher_chain = GraphCypherQAChain.from_llm(
                self.llm,
                graph=self.kg,
                verbose=False,
                cypher_prompt=CYPHER_GENERATION_PROMPT,
            )
            print("✅ GraphCypherQAChain initialized (like mentor's Lesson 7)")
        except Exception as e:
            print(f"⚠️  Could not initialize GraphCypherQAChain: {e}")
            self.cypher_chain = None
    
    def ensure_vector_store(self):
        """Initialize Neo4jVector store (like notebook Lesson 4)"""
        if self.vector_store is None:
            try:
                # Try to use existing index (like notebook)
                self.vector_store = Neo4jVector.from_existing_graph(
                    embedding=self.embeddings,
                    url=self.kg.url,
                    username=self.kg.username,
                    password=self.kg.password,
                    database=self.kg.database,
                    index_name=self.index_name,
                    node_label=self.node_label,
                    text_node_properties=[self.text_property],
                    embedding_node_property=self.embedding_property,
                )
                self.retriever = self.vector_store.as_retriever()
                self.qa_chain = RetrievalQAWithSourcesChain.from_chain_type(
                    self.llm,
                    chain_type="stuff",
                    retriever=self.retriever
                )
                print("✅ LangChain Neo4jVector initialized")
            except Exception as e:
                print(f"⚠️  Could not initialize Neo4jVector: {e}")
                # Fallback: create from scratch if needed
                self.vector_store = None
    
    def answer_with_sources(self, question: str) -> Dict[str, Any]:
        """Answer question using LangChain RAG (like notebook)"""
        self.ensure_vector_store()
        
        if self.qa_chain is None:
            return {
                "answer": "Vector store not initialized. Please ensure nodes have embeddings.",
                "sources": []
            }
        
        try:
            response = self.qa_chain(
                {"question": question},
                return_only_outputs=True
            )
            return {
                "answer": response.get("answer", ""),
                "sources": response.get("sources", [])
            }
        except Exception as e:
            return {
                "answer": f"Error: {str(e)}",
                "sources": []
            }
    
    def answer_with_cypher(self, question: str) -> str:
        """Answer using GraphCypherQAChain (like Lesson 7 - mentor's approach)"""
        if self.cypher_chain is None:
            # Fallback to vector search if Cypher chain not available
            result = self.answer_with_sources(question)
            return result["answer"]
        
        try:
            # Use GraphCypherQAChain to generate Cypher and execute (like mentor)
            response = self.cypher_chain.run(question)
            return response
        except Exception as e:
            print(f"⚠️  GraphCypherQAChain failed: {e}")
            # Fallback to vector search
            result = self.answer_with_sources(question)
            return result["answer"]
    
    def answer(self, question: str) -> str:
        """Answer using GraphCypherQAChain (primary) or RetrievalQAWithSourcesChain (fallback)"""
        # Prefer GraphCypherQAChain (like mentor's Lesson 7)
        if self.cypher_chain:
            return self.answer_with_cypher(question)
        else:
            # Fallback to vector search
            result = self.answer_with_sources(question)
            return result["answer"]
    
    def similarity_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Similarity search using Neo4jVector"""
        self.ensure_vector_store()
        
        if self.retriever is None:
            return []
        
        try:
            docs = self.retriever.get_relevant_documents(query)
            hits = []
            for doc in docs[:top_k]:
                hits.append({
                    "id": doc.metadata.get("id"),
                    "score": getattr(doc, "score", 0.0),
                    "content": doc.page_content[:200],
                    "metadata": doc.metadata
                })
            return hits
        except Exception as e:
            print(f"⚠️  Similarity search failed: {e}")
            return []
    
    def use_window_retrieval(self, window_size: int = 1):
        """Use window retrieval query (like notebook - expands context around chunks)"""
        # Custom retrieval query with window (like notebook)
        retrieval_query_window = f"""
        MATCH window = (prev:Node)-[:NEXT*0..{window_size}]->(node)-[:NEXT*0..{window_size}]->(next:Node)
        WHERE node.{self.embedding_property} IS NOT NULL
        WITH node, score, window as longestWindow 
        ORDER BY length(window) DESC LIMIT 1
        WITH nodes(longestWindow) as nodeList, node, score
        UNWIND nodeList as nodeRow
        WITH collect(nodeRow.{self.text_property}) as textList, node, score
        RETURN apoc.text.join(textList, " \\n ") as text,
            score,
            node {{.*}} AS metadata
        """
        
        try:
            self.vector_store = Neo4jVector.from_existing_index(
                embedding=self.embeddings,
                url=self.kg.url,
                username=self.kg.username,
                password=self.kg.password,
                database=self.kg.database,
                index_name=self.index_name,
                text_node_property=self.text_property,
                retrieval_query=retrieval_query_window,
            )
            self.retriever = self.vector_store.as_retriever()
            self.qa_chain = RetrievalQAWithSourcesChain.from_chain_type(
                self.llm,
                chain_type="stuff",
                retriever=self.retriever
            )
            print(f"✅ Window retrieval enabled (window_size={window_size})")
        except Exception as e:
            print(f"⚠️  Window retrieval failed: {e}")
