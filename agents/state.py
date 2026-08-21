from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # The conversation history + tool calls + reflections
    messages: Annotated[list[AnyMessage], add_messages]
    # Counter to prevent infinite loops
    iterations: int
