import os
import sys
import requests
from typing import TypedDict, List
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from llm import get_llm

# --- Configuration ---
QDRANT_URL = "http://qdrant:6333"
OLLAMA_URL = "http://ollama:11434"
SEARXNG_URL = "http://searxng:8080"
EMBED_MODEL = "bge-m3"
COLLECTION_NAME = "personal_knowledge"

# --- State Schema ---
class CragState(TypedDict):
    question: str
    documents: List[str]
    web_results: List[str]
    generation: str
    verified: bool
    retries: int
    rewritten_query: str

# --- Nodes ---
def retrieve_local(state: CragState):
    """Searches Qdrant for local documents."""
    print("--- 🔍 RETRIEVING LOCAL DOCUMENTS ---")
    question = state["question"]
    
    # Get embedding from Ollama
    res = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": EMBED_MODEL, "prompt": question})
    vector = res.json()["embedding"]
    
    # Search Qdrant
    from qdrant_client import QdrantClient
    client = QdrantClient(url=QDRANT_URL)
    results = client.search(collection_name=COLLECTION_NAME, query_vector=vector, limit=3)
    
    docs = [r.payload['text'] for r in results]
    print(f"Found {len(docs)} local documents.")
    return {"documents": docs}

def grade_documents(state: CragState):
    """CRAG Step: Grades if local docs are relevant to answer the question."""
    print("--- 📝 GRADING DOCUMENTS (CRAG) ---")
    question = state["question"]
    docs = state["documents"]
    llm = get_llm()
    
    relevant_docs = []
    for doc in docs:
        prompt = f"""You are a grader assessing relevance of a retrieved document to a user question.
        Document: {doc}
        Question: {question}
        If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant.
        Output ONLY 'YES' or 'NO'."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        grade = response.content.strip().upper()
        print(f"Grader Output: {grade}")
        
        if "YES" in grade:
            relevant_docs.append(doc)
            
    if not relevant_docs:
        print("❌ No relevant local documents found. Will search web.")
    else:
        print("✅ Relevant local documents found!")
        
    return {"documents": relevant_docs}

def decide_to_search(state: CragState):
    """Routing logic: If no relevant local docs, search the web."""
    if not state["documents"]:
        return "web_search"
    return "generate"

def web_search(state: CragState):
    """Fallback: Searches SearXNG for live web results."""
    print("--- 🌐 SEARCHING THE WEB ---")
    query = state.get("rewritten_query") or state["question"]
    if state.get("rewritten_query"):
        print(f"Using rewritten query: {query}")
    else:
        print(f"Using original query: {query}")
        
    res = requests.get(f"{SEARXNG_URL}/search", params={"q": query, "format": "json"})
    data = res.json()
    
    # Extract top 3 snippets
    snippets = [r['content'] for r in data.get('results', [])[:3]]
    print(f"Found {len(snippets)} web results.")
    return {"web_results": snippets, "documents": state["documents"]}

def generate(state: CragState):
    """Generates a draft answer using ONLY retrieved context (local or web)."""
    print("--- ✍️ GENERATING DRAFT ANSWER ---")
    question = state["question"]
    docs = state["documents"]
    web = state.get("web_results", [])
    
    context = "\n\n".join(docs + web)
    
    if not context:
        return {"generation": "I could not find any information in local documents or on the web to answer this."}
        
    prompt = f"""You are an AI assistant. Answer the user's question based ONLY on the context provided below.
    Context:
    {context}
    
    Question: {question}
    
    Answer:"""
    
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"Draft Answer: {response.content}")
    return {"generation": response.content}

def verify(state: CragState):
    """Verification Subagent: Checks if the draft answer is fully grounded in the context."""
    print("--- 🛡️ VERIFYING ANSWER ---")
    question = state["question"]
    docs = state["documents"]
    web = state.get("web_results", [])
    generation = state["generation"]
    retries = state.get("retries", 0)
    
    context = "\n\n".join(docs + web)
    
    prompt = f"""You are a verifier. Does the following answer directly answer the user's question, and is it fully supported by the provided context?
    Answer: {generation}
    Context: {context}
    Question: {question}
    
    Output ONLY 'YES' or 'NO'."""
    
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    
    grade = response.content.strip().upper()
    print(f"Verifier Output: {grade}")
    
    if "YES" in grade:
        print("✅ Verification Passed!")
        return {"verified": True}
    else:
        print("❌ Verification Failed! Will retry web search if attempts remain.")
        return {"verified": False, "retries": retries + 1}

def rewrite_query(state: CragState):
    """If verification fails, rewrite the search query to find better results."""
    print("--- 🔄 REWRITING SEARCH QUERY ---")
    question = state["question"]
    previous_answer = state["generation"]
    
    prompt = f"""You are an expert search query rewriter.
    The original question was: "{question}"
    The previous search results were insufficient to answer this question.
    Write a new, highly specific search query to find the exact missing information.
    Output ONLY the new search query, nothing else."""
    
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    new_query = response.content.strip()
    
    print(f"New Query: {new_query}")
    return {"rewritten_query": new_query}


# --- Build Graph ---
workflow = StateGraph(CragState)

workflow.add_node("retrieve", retrieve_local)
workflow.add_node("grade", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate", generate)
workflow.add_node("verify", verify)
workflow.add_node("rewrite", rewrite_query)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade")

def decide_to_search(state: CragState):
    if not state["documents"]:
        return "web_search"
    return "generate"

workflow.add_conditional_edges(
    "grade",
    decide_to_search,
    {
        "web_search": "web_search",
        "generate": "generate"
    }
)

def decide_to_retry(state: CragState):
    """If verification fails, rewrite query then retry web search up to 3 times."""
    if not state.get("verified", False) and state.get("retries", 0) < 3:
        print(f"Verification failed. Rewriting query for attempt {state['retries'] + 1}...")
        return "rewrite"
    return END

workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", "verify")
# Retry loop: verify -> rewrite -> web_search -> generate
workflow.add_conditional_edges(
    "verify",
    decide_to_retry,
    {
        "rewrite": "rewrite",
        END: END
    }
)
workflow.add_edge("rewrite", "web_search")

app = workflow.compile()

# --- CLI Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python crag_graph.py "Your question here"')
        sys.exit(1)
        
    user_input = " ".join(sys.argv[1:])
    inputs = {"question": user_input, "documents": [], "web_results": [], "retries": 0, "rewritten_query": ""}    
    
    print(f"\nUser: {user_input}")
    print("=" * 50)
    
    # Using invoke() gets us the final state directly
    final_state = app.invoke(inputs, {"recursion_limit": 25})
        
    print("=" * 50)
    if final_state.get("verified"):
        print(f"✨ FINAL ANSWER: {final_state.get('generation', 'Error')}")
    else:
        print(f"❌ FINAL ANSWER: I could not find or verify the answer after {final_state.get('retries', 0)} attempts.")
