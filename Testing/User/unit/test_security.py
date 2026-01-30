"""
Unit tests for security functions
Tests password hashing and JWT token operations
"""
import pytest
from datetime import timedelta
from jose import jwt, JWTError
from fastapi import HTTPException
import sys
sys.path.insert(0, '/app')

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    SECRET_KEY,
    ALGORITHM
)


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string"""
        password = "mySecurePassword123"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """Test that hashing the same password twice produces different hashes"""
        password = "samePassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # Different salts should produce different hashes
    
    def test_verify_password_correct(self):
        """Test that correct password verification returns True"""
        password = "correctPassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test that incorrect password verification returns False"""
        password = "correctPassword"
        wrong_password = "wrongPassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty_string(self):
        """Test password verification with empty string"""
        password = "password123"
        hashed = hash_password(password)
        assert verify_password("", hashed) is False
    
    def test_hash_password_special_characters(self):
        """Test hashing passwords with special characters"""
        password = "p@ssw0rd!#$%^&*()"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestJWTTokens:
    """Test JWT token creation and verification"""
    
    def test_create_access_token_returns_string(self):
        """Test that create_access_token returns a string"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_contains_data(self):
        """Test that created token contains the correct data"""
        email = "user@example.com"
        data = {"sub": email}
        token = create_access_token(data)
        
        # Decode token manually to check contents
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == email
        assert "exp" in payload
    
    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiration time"""
        data = {"sub": "test@example.com"}
        expires_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=expires_delta)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
    
    def test_verify_token_valid(self):
        """Test that valid token verification returns payload"""
        email = "test@example.com"
        data = {"sub": email}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload["sub"] == email
    
    def test_verify_token_invalid_signature(self):
        """Test that token with invalid signature raises exception"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        # Tamper with the token
        tampered_token = token[:-10] + "tampered12"
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(tampered_token)
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail
    
    def test_verify_token_expired(self):
        """Test that expired token raises exception"""
        data = {"sub": "test@example.com"}
        # Create token that expires immediately
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        
        assert exc_info.value.status_code == 401
    
    def test_verify_token_missing_subject(self):
        """Test that token without 'sub' field raises exception"""
        # Create token without 'sub' field
        data = {"user_id": "123"}
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        
        assert exc_info.value.status_code == 401
    
    def test_verify_token_malformed(self):
        """Test that malformed token raises exception"""
        malformed_token = "this.is.not.a.valid.token"
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(malformed_token)
        
        assert exc_info.value.status_code == 401
