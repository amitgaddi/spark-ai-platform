
```markdown
# Spark AI Platform - Application Integration Guide

This document provides the specification for connecting custom Python applications (built locally on your Mac) to the Spark AI Local LLM Server. 

**Architecture:**
Your Mac App -> (HTTP over Tailscale VPN) -> Spark AI LiteLLM Gateway -> vLLM (120B Model)

## 1. Configuration & Authentication

Applications must never hardcode the API key. They should read it from the environment.

- **API Base URL:** `http://spark-8441/v1` (or `http://100.121.31.59/v1`)
- **API Key Environment Variable:** `SPARK_API_KEY`
- **Expected Header:** `Authorization: Bearer <SPARK_API_KEY>`

Ensure your Mac's `~/.zshrc` exports this variable:
```bash
export SPARK_API_KEY="your_generated_key_here"
```

## 2. Available Models

- `expert`: Nemotron-3-Super-120B (Use for complex reasoning, drafting, architecture, and chat).
- `fast`: Qwen3-8B (Use for quick classifications, routing, or simple tasks).
- `coder`: Qwen3-Coder-30B (Use for code generation. *Requires manual swap on Spark first*).

## 3. Integration Example (Python)

Use the standard `openai` Python SDK to connect to the Spark. 

**Install dependency:** `pip install openai`

**Code Template:**
```python
import os
from openai import OpenAI

# Initialize the client pointing to the local Spark AI server
client = OpenAI(
    base_url="http://spark-8441/v1",
    api_key=os.environ.get("SPARK_API_KEY") # Fetch key from environment
)

def call_spark_llm(prompt: str, model: str = "expert", max_tokens: int = 4000) -> str:
    """
    Sends a prompt to the Spark AI local server and returns the response.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error communicating with Spark AI: {e}"

# Example usage:
if __name__ == "__main__":
    result = call_spark_llm("Write a python function to reverse a string.")
    print(result)
```

## 4. Important Constraints for AI Agents

When building applications that use this API, AI coding assistants must adhere to the following constraints:

1. **Context Window Limit:** The `expert` model has a maximum context window of **65,536 tokens**. If passing large documents (like resumes or web pages) into the prompt, chunk the data or summarize it first to avoid `400 Context Window Exceeded` errors.
2. **Timeouts:** The 120B model is highly capable but slower than hosted APIs. The client must have a timeout of at least **120-300 seconds** to prevent request cancellations during long generations.
3. **Tool Calling Format:** The server natively supports OpenAI-style tool calls (JSON), but it is recommended to use standard `chat.completions` for simple application integrations.
```
