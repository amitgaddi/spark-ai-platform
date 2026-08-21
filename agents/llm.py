import os
from langchain_openai import ChatOpenAI

def get_llm() -> ChatOpenAI:
    """Returns the LLM configured to use our local LiteLLM gateway."""
    return ChatOpenAI(
        model=os.getenv("MODEL_EXPERT", "expert"),
        api_key=os.getenv("LITELLM_API_KEY"),
        base_url=os.getenv("LITELLM_API_BASE", "http://litellm:4000/v1"),
        temperature=0.1,
        streaming=False
    )
