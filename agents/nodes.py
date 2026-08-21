import re
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from state import AgentState
from llm import get_llm
from tools import calculator, get_current_time
from prompts import AGENT_SYS_PROMPT, REFLECTOR_SYS_PROMPT

llm = get_llm()

def parse_xml_tool_calls(text):
    """Parses custom XML tool calls from LLM text output."""
    tool_calls = []
    # Find all <function=NAME> ... </function> blocks
    for match in re.finditer(r"<function=(\w+)>(.*?)</function>", text, re.DOTALL):
        tool_name = match.group(1)
        params_str = match.group(2)
        args = {}
        
        # Find all <parameter=KEY> VALUE </parameter>
        for p_match in re.finditer(r"<parameter=(\w+)>(.*?)</parameter>", params_str, re.DOTALL):
            key = p_match.group(1)
            val = p_match.group(2).strip()
            args[key] = val
            
        tool_calls.append({
            "name": tool_name,
            "args": args,
            "id": f"call_{len(tool_calls)}"
        })
    return tool_calls

def call_agent(state: AgentState):
    """Main reasoning node. Decides whether to answer or use a tool."""
    messages = state["messages"]
    
    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=AGENT_SYS_PROMPT)] + messages
        
    response = llm.invoke(messages)
    
    # Check if the model tried to call a tool using our XML format
    tool_calls = parse_xml_tool_calls(response.content)
    
    if tool_calls:
        # Convert text output to a proper AIMessage with tool_calls
        response = AIMessage(
            content=response.content,
            tool_calls=tool_calls
        )
        
    return {"messages": [response], "iterations": state["iterations"] + 1}

def call_tools(state: AgentState):
    """Executes the tools requested by the agent."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_map = {"calculator": calculator, "get_current_time": get_current_time}
    
    results = []
    for call in last_message.tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        
        print(f"--- 🔧 Executing Tool: {tool_name}({tool_args}) ---")
        result = tool_map[tool_name].invoke(tool_args)
        
        results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        
    return {"messages": results}

def reflect(state: AgentState):
    """Interleaved thinking node. Generates reasoning AFTER seeing tool output."""
    messages = state["messages"]
    last_tool_output = messages[-1].content
    
    reflection_prompt = [
        SystemMessage(content=REFLECTOR_SYS_PROMPT),
        HumanMessage(content=f"User's original question: {messages[0].content if isinstance(messages[0], HumanMessage) else messages[1].content}\n\nTool Output observed: {last_tool_output}\n\nProvide your brief reflection:")
    ]
    
    reflection = llm.invoke(reflection_prompt)
    print(f"--- 💭 Reflection: {reflection.content} ---")
    
    return {"messages": [reflection]}

def should_continue(state: AgentState):
    """Routing logic. Determines if we answer or continue the loop."""
    if state["iterations"] >= 10:
        return "end"
        
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    
    return "end"
