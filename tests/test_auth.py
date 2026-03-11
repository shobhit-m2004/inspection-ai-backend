"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User


class TestRegister:
    """Test user registration."""
    
    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "securepassword123",
        }
        
        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == payload["email"]
        assert data["user"]["name"] == payload["name"]
    
    def test_register_duplicate_email(self, client: TestClient, db_session: Session):
        """Test registration with existing email."""
        # Create existing user
        user = User(
            name="Existing User",
            email="existing@example.com",
            password_hash="hashed_password",
        )
        db_session.add(user)
        db_session.commit()
        
        # Try to register with same email
        payload = {
            "name": "New User",
            "email": "existing@example.com",
            "password": "securepassword123",
        }
        
        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 409
        assert "Email already registered" in response.json()["error"]["message"]
    
    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email format."""
        payload = {
            "name": "John Doe",
            "email": "invalid-email",
            "password": "securepassword123",
        }
        
        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422
    
    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password."""
        payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "weak",
        }
        
        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 422


class TestLogin:
    """Test user login."""
    
    def test_login_success(self, client: TestClient, db_session: Session):
        """Test successful login."""
        # Create user
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu",  # "password123"
        )
        db_session.add(user)
        db_session.commit()
        
        payload = {
            "email": "test@example.com",
            "password": "password123",
        }
        
        response = client.post("/auth/login", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "test@example.com"
    
    def test_login_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials."""
        payload = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        }
        
        response = client.post("/auth/login", json=payload)
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["error"]["message"]
    
    def test_login_wrong_password(self, client: TestClient, db_session: Session):
        """Test login with wrong password."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu",
        )
        db_session.add(user)
        db_session.commit()
        
        payload = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }
        
        response = client.post("/auth/login", json=payload)
        
        assert response.status_code == 401
