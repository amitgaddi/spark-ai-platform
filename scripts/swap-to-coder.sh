#!/bin/bash
echo "Unloading 120B Expert Model (Freeing 92GB)..."
docker stop vllm

echo "Ollama is now ready for the 30B Coder Model."
echo "You can now send requests using 'model: coder'"
