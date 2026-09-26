import sys
import json
from unittest.mock import patch, MagicMock

# 1. Mock Redis globally before importing the app
mock_redis_instance = MagicMock()
patch('redis.Redis', return_value=mock_redis_instance).start()

# 2. Mock the internal 'llm' module so it doesn't attempt real model loading
mock_llm_module = MagicMock()
sys.modules['llm'] = mock_llm_module
mock_fast_llm = MagicMock()
mock_llm_module.get_llm.return_value = mock_fast_llm

# 3. Now import FastAPI and the application safely
from fastapi.testclient import TestClient
from agents.api import app, parse_priority

client = TestClient(app)

def test_parse_priority():
    """Test the Eisenhower Matrix priority parser."""
    assert parse_priority("!q2 research Apple") == ("q2", "research Apple")
    assert parse_priority("!urgent Fix the server") == ("q1", "Fix the server")
    assert parse_priority("Just a normal message") == ("q1", "Just a normal message")

@patch("agents.api.r", mock_redis_instance)
def test_chat_bypass_enhancer():
    """Test that Q1/bypass messages skip the LLM and go straight to the queue."""
    mock_redis_instance.lpush.reset_mock()
    
    response = client.post(
        "/v1/chat",
        json={
            "message": "!q1 What is the IP?",
            "bypass_enhancer": True,
            "chat_id": "12345"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["final_prompt"] == "What is the IP?"
    
    # Verify Redis lpush was called correctly
    mock_redis_instance.lpush.assert_called_once()
    args, _ = mock_redis_instance.lpush.call_args
    assert args[0] == "queue:q1"
    assert "What is the IP?" in args[1]

@patch("agents.api.r", mock_redis_instance)
def test_chat_needs_approval():
    """Test that normal messages hit the re-prompter and wait for human approval."""
    mock_redis_instance.set.reset_mock()
    
    # Mock the fast LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = "You are an expert AI. Explain Docker."
    mock_fast_llm.invoke.return_value = mock_llm_response
    
    response = client.post(
        "/v1/chat",
        json={
            "message": "Explain Docker",
            "bypass_enhancer": False
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_approval"
    assert data["suggested_prompt"] == "You are an expert AI. Explain Docker."
    
    # Verify it was saved to Redis with an expiration
    mock_redis_instance.set.assert_called_once()
    args, kwargs = mock_redis_instance.set.call_args
    assert args[0].startswith("task:")
    assert kwargs["ex"] == 3600
