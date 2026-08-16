#!/bin/bash
set -e

echo "=== DGX Spark Day 1 Startup ==="

# 1. Setup Tailscale (Run manually if not done)
# sudo tailscale up

# 2. Create Docker Network
docker network create ai-net || true

# 3. Create Model Directory
sudo mkdir -p /data/models
sudo chown -R $USER:$USER /data

# 4. Download Primary Model (Uncomment to run)
# huggingface-cli download nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \
#     --local-dir /data/models/nvidia-nemotron-3-super-120b-a12b-nvfp4 \
#     --local-dir-use-symlinks False

# 5. Start Core Services (Excluding Ollama for Day 1)
docker compose -f compose/llm.yml up -d caddy litellm vllm postgres

echo "Waiting for vLLM to load 120B model into memory (3-5 minutes)..."
docker logs -f vllm

