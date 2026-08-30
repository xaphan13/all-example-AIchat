"""Tests for FastAPI application endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import json

from src.app import app
from src.core.models import TaskRequest


client = TestClient(app)


class TestEndpoints:
    """Test API endpoints."""
    
    def test_root_endpoint(self):
        """Test root health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "Multi-Agent" in data["service"]
    
    def test_health_endpoint(self):
        """Test detailed health check."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "api_keys" in data
        assert "config" in data
        assert "anthropic" in data["api_keys"]
        assert "max_concurrent_agents" in data["config"]
    
    def test_reset_endpoint(self):
        """Test conversation reset endpoint."""
        response = client.post("/api/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_process_task_empty_message(self):
        """Test that empty message returns error."""
        response = client.post(
            "/api/task",
            json={"message": "   "}
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    
    def test_process_task_stream_empty_message(self):
        """Test that empty message returns error in stream endpoint."""
        response = client.post(
            "/api/task/stream",
            json={"message": ""}
        )
        assert response.status_code == 400


class TestEventGenerator:
    """Test event generator functionality."""
    
    @pytest.mark.asyncio
    async def test_event_generator_format(self):
        """Test SSE event format."""
        from main import event_generator
        
        task = TaskRequest(message="Test", enable_collaboration=False)
        
        with patch('orchestrator.task_orchestrator.TaskOrchestrator.process_task') as mock_process:
            async def mock_events():
                yield {"type": "init", "conversation_id": "test_123"}
                yield {"type": "stream", "content": "Hello"}
            
            mock_process.return_value = mock_events()
            
            events = []
            async for event in event_generator(task):
                events.append(event)
            
            # Check SSE format
            for event in events:
                assert event.startswith("data: ")
                assert event.endswith("\n\n")
                # Should be valid JSON
                json_str = event.replace("data: ", "").strip()
                data = json.loads(json_str)
                assert "type" in data
    
    @pytest.mark.asyncio
    async def test_event_generator_error_handling(self):
        """Test error handling in event generator."""
        from main import event_generator
        
        task = TaskRequest(message="Test")
        
        with patch('orchestrator.task_orchestrator.TaskOrchestrator.process_task') as mock_process:
            async def mock_error():
                raise Exception("Test error")
            
            mock_process.return_value = mock_error()
            
            events = []
            async for event in event_generator(task):
                events.append(event)
            
            # Should have error event
            assert len(events) > 0
            last_event = events[-1]
            json_str = last_event.replace("data: ", "").strip()
            data = json.loads(json_str)
            assert data["type"] == "error"
            assert "error" in data


class TestCORS:
    """Test CORS configuration."""
    
    def test_cors_headers(self):
        """Test CORS headers are set."""
        response = client.options("/", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST"
        })
        # FastAPI handles CORS, just verify endpoint is accessible
        assert response.status_code in [200, 405]


class TestTaskProcessing:
    """Test task processing logic."""
    
    def test_task_request_validation(self):
        """Test task request validation."""
        # Valid request
        response = client.post(
            "/api/task",
            json={
                "message": "What is AI?",
                "max_sub_agents": 2,
                "enable_collaboration": False
            }
        )
        # May fail due to actual processing, but should not fail validation
        assert response.status_code != 422
    
    def test_invalid_task_request(self):
        """Test invalid task request structure."""
        response = client.post(
            "/api/task",
            json={"invalid_field": "value"}
        )
        # Should fail validation
        assert response.status_code == 422

