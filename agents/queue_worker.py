import os
import json
import redis
import time
import requests
from crag_graph import app as crag_app

r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def process_task(task):
    print(f"--- ⚙️ Processing Task {task['task_id']} ---")
    
    # Run the CRAG pipeline
    inputs = {"question": task['final_prompt'], "documents": [], "web_results": [], "retries": 0, "rewritten_query": ""}
    final_state = crag_app.invoke(inputs, {"recursion_limit": 25})
    
    result = final_state.get('generation', 'Error: Could not process request.')
    
    # Save result to Redis for API polling
    r.set(f"result:{task['task_id']}", result, ex=86400)
    
    # If this came from Telegram, send the result back
    chat_id = task.get("chat_id")
    if chat_id:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"✨ *Result:*\n\n{result}",
                "parse_mode": "Markdown"
            })
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
