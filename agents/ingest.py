import os
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = "bge-m3"
COLLECTION_NAME = "personal_knowledge"

def get_embedding(text: str) -> list[float]:
    """Get embeddings from Ollama."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text}
    )
    response.raise_for_status()
    return response.json()["embedding"]

def ingest_data():
    """Ingests test data into Qdrant."""
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = QdrantClient(url=QDRANT_URL)
    
    # Create collection if it doesn't exist
    if not client.collection_exists(COLLECTION_NAME):
        print(f"Creating collection: {COLLECTION_NAME}")
        # bge-m3 outputs 1024 dimensional vectors
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
        )
    
    # Our test document
    documents = [
        {
            "id": 1,
            "text": "The secret launch code for Project Spark is 8441. This code is highly classified and only known to the system administrator Amit.",
            "metadata": {"source": "local_test_doc"}
        }
    ]
    
    print("Embedding and uploading documents...")
    points = []
    for doc in documents:
        vector = get_embedding(doc["text"])
        points.append(PointStruct(
            id=doc["id"], 
            vector=vector, 
            payload={"text": doc["text"], "source": doc["metadata"]["source"]}
        ))
        
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"✅ Successfully ingested {len(points)} document(s) into Qdrant!")

if __name__ == "__main__":
    ingest_data()
