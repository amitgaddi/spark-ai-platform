import os
import re
import json
import uuid
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from llm import get_llm

# --- Initialization ---
app = FastAPI(title="Spark Agent API")
r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# Use the fast model for re-prompting
fast_llm = get_llm(model_name=os.getenv("MODEL_FAST", "fast"))

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str
    user_id: str = "api_user"
    bypass_enhancer: bool = False
    chat_id: str = None #used by Telegram to route the final response

class ApprovalRequest(BaseModel):
    task_id: str
    approved_prompt: str

# --- Helper Functions ---
def parse_priority(message: str):
    """Extracts priority tag from message. Defaults to Q1."""
    if "!q2" in message.lower() or "!background" in message.lower():
        clean_msg = re.sub(r'!q2|!background', '', message, flags=re.IGNORECASE).strip()
        return "q2", clean_msg
    clean_msg = re.sub(r'!q1|!urgent', '', message, flags=re.IGNORECASE).strip()
    return "q1", clean_msg

def enhance_prompt(raw_prompt: str) -> str:
    """Uses the 8B model to rewrite the prompt for better results."""
    sys_prompt = """You are a prompt engineering expert. Rewrite the user's prompt to be highly specific, role-based, and structured for an expert AI. Output ONLY the rewritten prompt, nothing else."""
    
    response = fast_llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=raw_prompt)
    ])
    return response.content.strip()

# --- API Endpoints ---
@app.post("/v1/chat")
def chat_endpoint(req: ChatRequest):
    """Receives a prompt, enhances it, and queues it for approval/execution."""
    priority, clean_msg = parse_priority(req.message)
    task_id = str(uuid.uuid4())
    
    if req.bypass_enhancer:
        # Skip re-prompter, go straight to queue
        task_data = {
            "task_id": task_id,
            "original_prompt": clean_msg,
            "final_prompt": clean_msg,
            "priority": priority,
            "status": "queued",
            "chat_id": req.chat_id
        }
        r.lpush(f"queue:{priority}", json.dumps(task_data))
        return {"status": "queued", "task_id": task_id, "final_prompt": clean_msg}
        
    else:
        # Run Re-Prompter
        enhanced = enhance_prompt(clean_msg)
        
        # Store in Redis waiting for approval
        task_data = {
            "task_id": task_id,
            "original_prompt": clean_msg,
            "final_prompt": enhanced,
            "priority": priority,
            "status": "pending_approval",
            "chat_id": req.chat_id
        }
        r.set(f"task:{task_id}", json.dumps(task_data), ex=3600) # Expire in 1hr
        
        # Return to user/app for approval
        return {
            "status": "needs_approval",
            "task_id": task_id,
            "original_prompt": clean_msg,
            "suggested_prompt": enhanced,
            "priority": priority
        }

@app.post("/v1/approve")
def approve_endpoint(req: ApprovalRequest):
    """User approves or edits the enhanced prompt. Pushes to execution queue."""
    task_json = r.get(f"task:{req.task_id}")
    if not task_json:
        raise HTTPException(status_code=404, detail="Task not found or expired.")
        
    task = json.loads(task_json)
    
    # If the user clicked "Accept", the bot sends "ACCEPTED_DEFAULT"
    # In this case, we just use the original suggested prompt.
    if req.approved_prompt == "ACCEPTED_DEFAULT":
        task["final_prompt"] = task.get("final_prompt", task["original_prompt"])
    else:
        task["final_prompt"] = req.approved_prompt
        
    task["status"] = "queued"
    
    # Push to appropriate priority queue
    r.lpush(f"queue:{task['priority']}", json.dumps(task))
    r.delete(f"task:{req.task_id}")
    
    return {"status": "queued", "task_id": req.task_id}

@app.get("/v1/queue")
def view_queue():
    """Returns the current state of Q1 and Q2 queues."""
    q1_tasks = [json.loads(t) for t in r.lrange("queue:q1", 0, 4)]
    q2_tasks = [json.loads(t) for t in r.lrange("queue:q2", 0, 4)]
    return {"q1_urgent": q1_tasks, "q2_background": q2_tasks}
