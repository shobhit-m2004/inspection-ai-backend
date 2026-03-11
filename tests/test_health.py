"""Tests for health check endpoints."""
import pytest
from fastapi.testclient import TestClient


class TestHealthChecks:
    """Test health check endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test basic health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
    
    def test_liveness_check(self, client: TestClient):
        """Test liveness check."""
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_readiness_check(self, client: TestClient):
        """Test readiness check."""
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
    
    def test_database_health(self, client: TestClient):
        """Test database health check."""
        response = client.get("/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data


class TestRootEndpoints:
    """Test root endpoints."""
    
    def test_root(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "name" in data
        assert "version" in data
    
    def test_api_info(self, client: TestClient):
        """Test API info endpoint."""
        response = client.get("/info")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "environment" in data
