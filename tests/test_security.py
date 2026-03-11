"""Tests for security utilities."""
import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)
from app.core.config import get_settings


class TestPasswordHashing:
    """Test password hashing functions."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "securepassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "securepassword123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with wrong password."""
        password = "securepassword123"
        hashed = hash_password(password)
        
        assert verify_password("wrongpassword", hashed) is False


class TestTokenCreation:
    """Test JWT token operations."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        user_id = "123"
        token = create_access_token(user_id)
        
        assert token is not None
        assert len(token) > 0
    
    def test_create_access_token_with_expiry(self):
        """Test access token with custom expiry."""
        user_id = "123"
        expires_delta = timedelta(minutes=30)
        token = create_access_token(user_id, expires_delta=expires_delta)
        
        # Decode and verify expiry
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        
        assert payload["sub"] == user_id
        assert "exp" in payload
    
    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        user_id = "123"
        token = create_access_token(user_id)
        
        payload = decode_token(token)
        
        assert payload is not None
        assert payload.sub == user_id
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid token."""
        invalid_token = "invalid.token.here"
        
        payload = decode_token(invalid_token)
        
        assert payload is None
    
    def test_decode_expired_token(self):
        """Test decoding an expired token."""
        # Create token that expired 1 minute ago
        user_id = "123"
        expires_delta = timedelta(minutes=-1)
        token = create_access_token(user_id, expires_delta=expires_delta)
        
        payload = decode_token(token)
        
        assert payload is None
