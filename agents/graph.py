from langgraph.graph import StateGraph, END
from state import AgentState
from nodes import call_agent, call_tools, reflect, should_continue

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Define nodes
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", call_tools)
    workflow.add_node("reflect", reflect)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edge from agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END
        }
    )
    
    # Normal edge from tools -> reflect -> agent (The Interleaved Thinking Loop)
    workflow.add_edge("tools", "reflect")
    workflow.add_edge("reflect", "agent")
    
    return workflow.compile()
