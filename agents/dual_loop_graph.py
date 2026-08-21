import os
import re
import json
import sys
import operator
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from llm import get_llm
from tools import search_web, fetch_page, deep_research_rag
from prompts import ACTOR_SYS_PROMPT, CRITIC_SYS_PROMPT

# --- LLMs ---
actor_llm = get_llm(model_name=os.getenv("MODEL_EXPERT", "expert"))
critic_llm = get_llm(model_name=os.getenv("MODEL_FAST", "fast"))

# --- State Schema ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    rejection_count: int

# --- Helper: XML Parser for Nemotron ---
def parse_xml_tool_calls(text):
    tool_calls = []
    for match in re.finditer(r"<function=(\w+)>(.*?)</function>", text, re.DOTALL):
        tool_name = match.group(1)
        params_str = match.group(2)
        args = {}
        for p_match in re.finditer(r"<parameter=(\w+)>(.*?)</parameter>", params_str, re.DOTALL):
            key = p_match.group(1)
            val = p_match.group(2).strip()
            args[key] = val
        tool_calls.append({"name": tool_name, "args": args, "id": f"call_{len(tool_calls)}"})
    return tool_calls

# --- Nodes ---
def actor_node(state: AgentState):
    """The Inner Loop: 120B model decides to use a tool or write a draft."""
    print("--- 🧠 ACTOR (Nemotron 120B) THINKING ---")
    messages = state["messages"]
    
    # Inject system prompt if missing
    if not isinstance(messages[0], SystemMessage):
        sys_prompt = ACTOR_SYS_PROMPT + "\n\nTo call a tool, output exactly this XML format:\n<function=tool_name>\n<parameter=param_name>param_value</parameter>\n</function>"
        messages = [SystemMessage(content=sys_prompt)] + messages
        
    response = actor_llm.invoke(messages)
    
    # Check if model tried to call a tool using XML
    tool_calls = parse_xml_tool_calls(response.content)
    if tool_calls:
        print(f"Actor decided to call tools: {[tc['name'] for tc in tool_calls]}")
        response = AIMessage(content=response.content, tool_calls=tool_calls)
        
    return {"messages": [response]}

def tool_node(state: AgentState):
    """Executes the specific tool requested by the Actor."""
    print("--- 🔧 TOOL EXECUTOR ---")
    last_message = state["messages"][-1]
    
    tool_map = {
        "search_web": search_web, 
        "fetch_page": fetch_page, 
        "deep_research_rag": deep_research_rag
    }
    
    results = []
    for call in last_message.tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        
        print(f"Executing: {tool_name}({tool_args})")
        result = tool_map[tool_name].invoke(tool_args)
        results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        
    return {"messages": results}

def critic_node(state: AgentState):
    """The Outer Loop: 8B model strictly audits the Actor's draft."""
    print("--- 🛡️ CRITIC (Qwen 8B) AUDITING ---")
    messages = state["messages"]
    draft = messages[-1].content
    
    # Format conversation history for the critic
    history = "\n".join([f"{m.type}: {m.content}" for m in messages if not isinstance(m, SystemMessage)])
    
    prompt = f"Conversation History:\n{history}\n\nActor's Final Draft:\n{draft}\n\nEvaluate the draft against the observations."
    
    response = critic_llm.invoke([
        SystemMessage(content=CRITIC_SYS_PROMPT),
        HumanMessage(content=prompt)
    ])
    
    # Parse JSON robustly (sometimes models add markdown ticks)
    clean_response = response.content.strip().replace("```json", "").replace("```", "")
    try:
        result = json.loads(clean_response)
        status = result.get("status", "REJECT").upper()
        feedback = result.get("feedback", "")
    except Exception:
        # Fallback if JSON parsing fails
        status = "APPROVE"
        feedback = ""
        print(f"Warning: Critic JSON parse failed. Raw: {response.content}")

    print(f"Critic Status: {status}")
    if feedback:
        print(f"Critic Feedback: {feedback}")
        
    if status == "APPROVE":
        # Signal approval to end the graph
        return {"messages": [AIMessage(content="FINAL_APPROVED")]}
    else:
        # Kick back to actor with feedback
        feedback_msg = f"CRITIC REJECTION: {feedback}. Please re-evaluate, search again if needed, and rewrite your draft."
        return {"messages": [HumanMessage(content=feedback_msg)], "rejection_count": state.get("rejection_count", 0) + 1}

# --- Routing Logic ---
def actor_router(state: AgentState):
    """Router 1: Does the Actor want to search, or did it write a draft?"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "Tools"
    return "Critic"

def critic_router(state: AgentState):
    """Router 2: Did the Critic approve, reject, or hit the limit?"""
    last_message = state["messages"][-1]
    if last_message.content == "FINAL_APPROVED":
        return END
    if state.get("rejection_count", 0) >= 3:
        print("Max rejections reached. Forcing approval.")
        return END
    return "Actor"

# --- Build Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("Actor", actor_node)
workflow.add_node("Tools", tool_node)
workflow.add_node("Critic", critic_node)

workflow.set_entry_point("Actor")

workflow.add_conditional_edges("Actor", actor_router, {
    "Tools": "Tools",
    "Critic": "Critic"
})

workflow.add_edge("Tools", "Actor")

workflow.add_conditional_edges("Critic", critic_router, {
    "Actor": "Actor",
    END: END
})

app = workflow.compile()

# --- CLI Entry Point for Testing ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python dual_loop_graph.py "Your question here"')
        sys.exit(1)
        
    user_input = " ".join(sys.argv[1:])
    inputs = {"messages": [HumanMessage(content=user_input)], "rejection_count": 0}
    
    print(f"\nUser: {user_input}")
    print("=" * 50)
    
    # We need to track the final draft. The Actor writes it, then Critic approves.
    # The final approved draft is the last AIMessage before the "FINAL_APPROVED" message.
    final_draft = "Error: No draft generated."
    for output in app.stream(inputs, {"recursion_limit": 25}):
        for key, value in output.items():
            if key == "Actor" and not value["messages"][0].tool_calls:
                # This is a draft
                final_draft = value["messages"][0].content
                
    print("=" * 50)
    print(f"✨ FINAL ANSWER:\n{final_draft}")
