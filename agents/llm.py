import os
from langchain_openai import ChatOpenAI

def get_llm(model_name: str = None) -> ChatOpenAI:
    """Returns the LLM configured to use our local LiteLLM gateway."""
    # If no model is specified, default to the expert model
    model = model_name or os.getenv("MODEL_EXPERT", "expert")
    
    return ChatOpenAI(
        model=model,
        api_key=os.getenv("LITELLM_API_KEY"),
        base_url=os.getenv("LITELLM_API_BASE", "http://litellm:4000/v1"),
        temperature=0.1,
        streaming=False
    )
