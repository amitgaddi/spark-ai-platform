import sys
from langchain_core.messages import HumanMessage
from graph import build_graph

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m agents.main \"Your question here\"")
        sys.exit(1)
        
    user_input = " ".join(sys.argv[1:])
    
    app = build_graph()
    
    inputs = {
        "messages": [HumanMessage(content=user_input)],
        "iterations": 0
    }
    
    print(f"\nUser: {user_input}")
    print("-" * 50)
    
    # Stream the graph to see the execution flow
    for output in app.stream(inputs, {"recursion_limit": 15}):
        for key, value in output.items():
            if key == "agent":
                msg = value["messages"][-1]
                if msg.tool_calls:
                    print(f"Agent Decision: Call Tool {msg.tool_calls[0]['name']}")
                else:
                    print(f"\nAgent Final Answer: {msg.content}")
            # Tools and Reflect nodes print internally via print() statements
            pass
        print("-" * 50)

if __name__ == "__main__":
    main()
