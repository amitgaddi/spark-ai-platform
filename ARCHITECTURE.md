# DGX Spark AI Platform Architecture

## 1. System Overview
- **Hardware:** NVIDIA DGX Spark (Grace Blackwell GB10, 128GB Unified Memory, 4TB NVMe).
- **Role:** Dedicated, headless, 24/7 AI inference and agent server.
- **Client:** Personal laptop/phone connects via Tailscale VPN.

## 2. Critical Constraints (AI MUST READ BEFORE EDITING)
- **Unified Memory:** The 128GB pool is shared by CPU, OS, Docker, and GPU. 
- **vLLM Allocation:** vLLM is capped at 72% (~92GB) of memory for the 120B model. DO NOT increase this, or Linux will OOM-kill the OS.
- **Model Hosting:** vLLM serves ONLY the massive primary model (Nemotron-120B). All smaller models (8B, 30B) MUST be routed to Ollama, which manages its own memory dynamically.

## 3. The "Lego Block" POC Strategy
This system is built incrementally. Do not break earlier blocks.
- **Block 1 (Day 1):** Core API (vLLM, LiteLLM, Caddy, Postgres).
- **Block 2 (Day 2):** Fast Models (Ollama for Qwen-8B/30B).
- **Block 3 (Day 3):** Observability (Prometheus, Grafana, DCGM).
- **Block 4 (Day 4+):** Agents & Eisenhower Matrix (Redis, Python Dispatchers).
- **Block 5:** RAG & Search (SearXNG, Qdrant, Embeddings).

## 4. Request Flow (The Eisenhower Matrix)
Requests hit Caddy -> LiteLLM. Priority is passed via HTTP headers (`X-Priority: q1`).
- **Q1 (Urgent/Important):** Bypasses queue, hits vLLM directly. Preempts Q2 if needed.
- **Q2 (Important/Not Urgent):** Pushed to Redis queue. Background worker runs ReAct + Adversarial Review.

## 5. Verification Pipeline (For Q2 Tasks)
1. **ReAct Loop:** Think -> Act (Web Search via SearXNG) -> Observe.
2. **Mandatory Grounding:** Facts must have citations. Unverified facts are flagged.
3. **Adversarial Review:** Implementer (120B) -> Critic (30B via Ollama) -> Fixer (120B) -> Arbiter (8B via Ollama).
