import os
import requests
import uuid
from bs4 import BeautifulSoup
from qdrant_client import QdrantClient
from langchain_core.tools import tool
import asyncio
from crawl4ai import AsyncWebCrawler

# Configuration from environment
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = "bge-m3"

def get_embedding(text: str) -> list[float]:
    """Helper to get embeddings from Ollama."""
    res = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
    res.raise_for_status()
    return res.json()["embedding"]

@tool
def search_web(query: str) -> str:
    """Discovery: Searches the web using SearXNG for the given query. Returns top 5 results with URLs and snippets. Use this to find general information or find URLs to fetch."""
    try:
        res = requests.get(f"{SEARXNG_URL}/search", params={"q": query, "format": "json"})
        data = res.json()
        results = []
        for r in data.get('results', [])[:5]:
            results.append(f"Title: {r.get('title')}\nURL: {r.get('url')}\nSnippet: {r.get('content')}\n")
        return "\n".join(results) if results else "No web results found."
    except Exception as e:
        return f"Error searching web: {e}"

@tool
def fetch_page(url: str) -> str:
    """Fetch: Extracts clean readable text from a single URL using a headless browser. Use this to read articles or JavaScript-heavy pages."""
    async def _fetch():
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown[:8000] # Cap at 8000 chars
    try:
        return asyncio.run(_fetch())
    except Exception as e:
        return f"Error fetching page: {e}"

@tool
def deep_research_rag(url: str, question: str) -> str:
    """Deep Read: Downloads a massive page, chunks it, embeds it locally, and returns ONLY the exact facts answering the question. Use this for deep research on a specific URL."""
    try:
        print(f"--- 🧠 Running Deep Research RAG on {url} ---")
        # 1. Scrape page
        res = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.content, 'lxml')
        for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header']):
            script_or_style.extract()
        text = soup.get_text(separator=' ')
        
        # 2. Chunk text (simple 500 char chunks)
        chunk_size = 500
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        if len(chunks) > 100: 
            chunks = chunks[:100] # Limit to 100 chunks to prevent OOM
            
        # 3. Embed using Ollama bge-m3 and prepare points
        points = []
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            points.append({"id": i, "vector": vector, "payload": {"text": chunk}})
            
        # 4. Ephemeral Qdrant Collection
        client = QdrantClient(url=QDRANT_URL)
        collection_name = f"temp_{uuid.uuid4().hex}"
        client.create_collection(collection_name=collection_name, vectors_config={"size": 1024, "distance": "Cosine"})
        
        # Wait for collection to be ready (simple sleep, Qdrant is fast)
        import time
        time.sleep(1)
        
        client.upsert(collection_name=collection_name, points=points)
        
        # 5. Search the ephemeral collection
        query_vector = get_embedding(question)
        hits = client.search(collection_name=collection_name, query_vector=query_vector, limit=3)
        
        # 6. Cleanup and return facts
        client.delete_collection(collection_name=collection_name)
        return "\n".join([hit.payload['text'] for hit in hits])
    except Exception as e:
        return f"Error in deep research RAG: {e}"

# The list of tools the LLM will be bound to
tools = [search_web, fetch_page, deep_research_rag]
