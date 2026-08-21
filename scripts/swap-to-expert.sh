#!/bin/bash
echo "Unloading 30B Coder Model from Ollama..."
docker exec ollama ollama stop qwen3-coder:30b

echo "Loading 120B Expert Model..."
docker start vllm

echo "Waiting for Expert Model to load (5-10 minutes)..."
docker logs -f vllm
