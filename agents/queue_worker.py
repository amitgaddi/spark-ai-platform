import os
import json
import redis
import time
import requests
from dual_loop_graph import app as agent_app
from langchain_core.messages import HumanMessage, AIMessage

r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def process_task(task):
    print(f"--- ⚙️ Processing Task {task['task_id']} ---")
    
    from langchain_core.messages import HumanMessage, AIMessage
    
    # Run the Dual-Loop graph with the correct state schema
    inputs = {
        "messages": [HumanMessage(content=task['final_prompt'])],
        "rejection_count": 0
    }
    final_state = agent_app.invoke(inputs, {"recursion_limit": 25})
    
    # Extract the final draft (the last AIMessage before "FINAL_APPROVED")
    result = "Error: Could not process request."
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content != "FINAL_APPROVED":
            result = msg.content
            break
    
    # Save result to Redis for API polling
    r.set(f"result:{task['task_id']}", result, ex=86400)
    
    # If this came from Telegram, send the result back
    chat_id = task.get("chat_id")
    if chat_id:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            tg_response = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"✨ Result:\n\n{result}"
                # Removed parse_mode="Markdown" to prevent silent Telegram API failures
            })
            # Log the response from Telegram so we can see if it fails
            if tg_response.status_code != 200:
                print(f"❌ Telegram API Error: {tg_response.text}")
            else:
                print(f"✅ Sent result to Telegram chat {chat_id}")
                
    print(f"--- ✅ Task {task['task_id']} Complete ---")

def main():
    print("Queue Worker started. Listening for tasks...")
    while True:
        # Check Q1 first (priority)
        task_json = r.rpop("queue:q1")
        if not task_json:
            # Then check Q2
            task_json = r.rpop("queue:q2")
            if not task_json:
                time.sleep(2)
                continue
        
        task = json.loads(task_json)
        try:
            process_task(task)
        except Exception as e:
            print(f"Error processing task {task['task_id']}: {e}")

if __name__ == "__main__":
    main()
