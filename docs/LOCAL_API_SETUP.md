# Spark AI Platform - Developer & Coding Assistant Setup

This guide explains how to connect custom applications and coding assistants (like Claude Code, Cursor, or Aider) to your personal 24/7 Spark AI server.

## Architecture Overview

The system has two distinct API paths:
1. **Agent API (`/agent-api/v1/chat`)**: For chat interfaces (like Telegram). Includes the Smart Prompt Enhancer (Re-Prompter) and the Actor-Critic verification loop.
2. **LiteLLM Direct API (`/v1/chat/completions`)**: Standard OpenAI-compatible endpoint for coding assistants. Bypasses the Re-Prompter and verification loop entirely (the coding assistant handles its own reasoning/verification).

---

## 1. Connecting Coding Assistants (Cursor, Aider, Claude Code)

Coding assistants must use the **Direct LiteLLM API** to avoid interfering with the Spark's internal agent loops. 

**Base URL:** `http://spark-8441/v1` (or your Tailscale IP `http://100.121.31.59/v1`)
**API Key:** Your `LITELLM_MASTER_KEY` from the `.env` file.

### Example: Cursor / Continue.dev Configuration
In your extension settings, configure the OpenAI provider:
```json
{
  "provider": "openai",
  "apiKey": "<LITELLM_MASTER_KEY>",
  "baseURL": "http://spark-8441/v1",
  "model": "expert"
}
```

### Available Models for Coding
- `expert`: Nemotron-3-Super-120B (Great for architecture, reasoning, and general code generation).
- `coder`: Qwen3-Coder-30B (Specialized for coding).
- `fast`: Qwen3-8B (Autocomplete and quick chat).

### Switching to the 30B Coder Model
Because the DGX Spark has 128GB of shared memory, the 120B and 30B models cannot run simultaneously. 

To use the `coder` model, SSH into the Spark and run the swap script:
```bash
cd ~/spark-ai-platform
./scripts/swap-to-coder.sh
```
*(This stops vLLM (120B) and frees 92GB of RAM so Ollama can load the 30B Coder).*

When you are done coding, swap back to the expert model:
```bash
./scripts/swap-to-expert.sh
```

### Important: Timeouts
The 120B model is highly capable but slower than hosted models. Ensure your coding assistant has a timeout of at least **120-300 seconds** to prevent request cancellations during long code generation.

---

## 2. Connecting Custom Apps (Agent API)

If you are building a custom app that needs grounded research and verification, use the **Agent API**.

**Base URL:** `http://spark-8441/agent-api/v1`

### Workflow:
1. `POST /chat` with `{"message": "Your query !q2"}`.
2. If `status` is `needs_approval`, present the `suggested_prompt` to the user.
3. `POST /approve` with `{"task_id": "...", "approved_prompt": "..."}`.
4. The background worker will process the task (Search -> Fetch -> Critic -> Verify) and save the result to Redis.
