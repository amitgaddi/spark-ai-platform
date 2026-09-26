import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load the LITELLM_MASTER_KEY from the root .env file
load_dotenv(dotenv_path=".env")

# Connect to the local LiteLLM gateway
client = OpenAI(
    base_url="http://127.0.0.1:4000/v1",
    api_key=os.environ.get("LITELLM_MASTER_KEY", "dummy-key")
)

# 20 Diverse Prompts: Logic, Coding, Math, formatting, and reasoning
PROMPTS = [
    # Logic & Math
    "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?",
    "If you have a 3-gallon jug and a 5-gallon jug, how can you measure exactly 4 gallons of water?",
    "Solve for x: 3x + 5 = 20",
    "If I am facing north and turn 90 degrees clockwise, then 180 degrees counter-clockwise, what direction am I facing?",
    
    # Coding & Engineering
    "Write a SQL query to find the second highest salary from an Employee table.",
    "Explain the difference between Python's threading and multiprocessing in exactly two sentences.",
    "Write a Python function to check if a string is a valid palindrome, ignoring spaces and punctuation.",
    "Provide a bash command to find all files modified in the last 7 days ending in .log.",
    "Write a regex pattern to match a standard IPv4 address.",
    "Write a minimal Dockerfile to run a simple Node.js application.",
    "Explain what a database deadlock is and one common way to prevent it.",
    "What is the difference between TCP and UDP? Give one common use case for each.",
    
    # Formatting & Constraints
    "Summarize the plot of the movie 'The Matrix' in a single haiku.",
    "Create a JSON object representing a book with a title, author, publication year, and an array of three genres.",
    
    # Domain Knowledge & Facts
    "List the first 5 elements of the periodic table with their atomic symbols.",
    "Explain the concept of 'opportunity cost' in economics using a real-world example.",
    "Is a tomato a fruit or a vegetable? Briefly explain the botanical versus culinary distinction.",
    "What is the capital of Australia?",
    "Who wrote the play 'Hamlet'?",
    "Translate the following English sentence into French: 'The library is closed on Sundays.'"
]

def generate_response(model: str, prompt: str) -> str:
    """Calls the local model to generate an answer."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def evaluate_responses(prompt: str, ans_fast: str, ans_expert: str) -> dict:
    """Uses the 120B Expert model as an impartial judge to score the outputs."""
    eval_prompt = f"""You are an impartial AI evaluator.
Prompt: {prompt}

Model A (Fast 8B): 
{ans_fast}

Model B (Expert 120B):
{ans_expert}

Evaluate both responses for accuracy, helpfulness, and logic. 
Output your evaluation as a strict JSON object with two keys: "winner" (either "Model A", "Model B", or "Tie") and "reasoning" (a 1-sentence explanation).
"""
    try:
        response = client.chat.completions.create(
            model="expert",
            messages=[{"role": "user", "content": eval_prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"winner": "Error", "reasoning": str(e)}

if __name__ == "__main__":
    print(f"Starting Spark AI LLM Evals across {len(PROMPTS)} prompts...")
    results = []
    
    for i, prompt in enumerate(PROMPTS):
        print(f"\n--- Eval {i+1}/{len(PROMPTS)} ---")
        
        ans_fast = generate_response("fast", prompt)
        ans_expert = generate_response("expert", prompt)
        evaluation = evaluate_responses(prompt, ans_fast, ans_expert)
        
        print(f"Winner: {evaluation.get('winner')}")
        
        results.append({
            "prompt": prompt,
            "fast_answer": ans_fast,
            "expert_answer": ans_expert,
            "evaluation": evaluation
        })
        
    with open("evals/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nEvals complete! Saved to evals/results.json")
