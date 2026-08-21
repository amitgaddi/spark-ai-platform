
```markdown
# Spark Agent API Documentation

The Agent API allows custom applications to interact with the Spark AI platform. It handles prompt enhancement, priority routing (Eisenhower Matrix), and task queueing.

**Base URL:** `http://spark-8441/v1` (or your Tailscale IP)

---

## 1. Submit a Chat Request

Send a prompt to the AI. The system will automatically use the 8B model to enhance your prompt for better results, then return it for your approval.

**Endpoint:** `POST /v1/chat`

**Payload:**
```json
{
  "message": "Write a python script to scrape a website. !q2",
  "user_id": "resumx_app",
  "bypass_enhancer": false
}
```

**Parameters:**
- `message` (string, required): Your prompt. 
  - *Priority Tags (optional):* Append `!q1` or `!urgent` for immediate execution (default). Append `!q2` or `!background` for background processing.
- `bypass_enhancer` (boolean, optional): If `true`, skips the 8B prompt enhancer and executes immediately. Defaults to `false`.

**Response (200 OK):**
```json
{
  "status": "needs_approval",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "original_prompt": "Write a python script to scrape a website.",
  "suggested_prompt": "You are an expert Python developer. Write a robust web scraping script using BeautifulSoup. Include error handling, rate limiting, and output to a JSON file.",
  "priority": "q2"
}
```

---

## 2. Approve / Edit Prompt

Once you receive the `suggested_prompt`, you can either accept it as-is, or edit it. Submit the final approved prompt to queue it for execution.

**Endpoint:** `POST /v1/approve`

**Payload:**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "approved_prompt": "You are an expert Python developer. Write a robust web scraping script using BeautifulSoup. Include error handling, rate limiting, and output to a JSON file."
}
```

**Response (200 OK):**
```json
{
  "status": "queued",
  "task_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

---

## 3. View Queues

Check the current backlog of tasks in the Eisenhower Matrix.

**Endpoint:** `GET /v1/queue`

**Response (200 OK):**
```json
{
  "q1_urgent": [],
  "q2_background": [
    {
      "task_id": "123e4567-...",
      "final_prompt": "You are an expert...",
      "priority": "q2"
    }
  ]
}
```
```
