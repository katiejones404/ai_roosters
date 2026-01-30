"""
Unit tests for User model
Tests User model creation, validation, and database operations
"""
import pytest
import uuid
from sqlalchemy.exc import IntegrityError
import sys
sys.path.insert(0, '/app')

from app.models.models import User
from app.core.security import hash_password


class TestUserModel:
    """Test User model functionality"""
    
    def test_create_user(self, test_db):
        """Test creating a basic user"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash is not None
        assert user.created_at is not None
    
    def test_user_email_unique_constraint(self, test_db):
        """Test that duplicate emails raise IntegrityError"""
        email = "duplicate@example.com"
        
        # Create first user
        user1 = User(
            username="user1",
            email=email,
            password_hash=hash_password("password1")
        )
        test_db.add(user1)
        test_db.commit()
        
        # Try to create second user with same email
        user2 = User(
            username="user2",
            email=email,
            password_hash=hash_password("password2")
        )
        test_db.add(user2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
    
    def test_user_username_unique_constraint(self, test_db):
        """Test that duplicate usernames raise IntegrityError"""
        username = "sameusername"
        
        # Create first user
        user1 = User(
            username=username,
            email="user1@example.com",
            password_hash=hash_password("password1")
        )
        test_db.add(user1)
        test_db.commit()
        
        # Try to create second user with same username
        user2 = User(
            username=username,
            email="user2@example.com",
            password_hash=hash_password("password2")
        )
        test_db.add(user2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
    
    def test_user_repr(self, test_db):
        """Test User __repr__ method"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password")
        )
        test_db.add(user)
        test_db.commit()
        
        assert repr(user) == "<User test@example.com>"
    
    def test_user_id_auto_generated(self, test_db):
        """Test that user ID is automatically generated"""
        user = User(
            username="autouser",
            email="auto@example.com",
            password_hash=hash_password("password")
        )
        # Don't set ID explicitly
        assert user.id is None  # Before commit
        
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
    
    def test_user_created_at_auto_generated(self, test_db):
        """Test that created_at is automatically set"""
        user = User(
            username="timeuser",
            email="time@example.com",
            password_hash=hash_password("password")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.created_at is not None
    
    def test_query_user_by_email(self, test_db):
        """Test querying user by email"""
        email = "query@example.com"
        user = User(
            username="queryuser",
            email=email,
            password_hash=hash_password("password")
        )
        test_db.add(user)
        test_db.commit()
        
        # Query by email
        found_user = test_db.query(User).filter(User.email == email).first()
        assert found_user is not None
        assert found_user.email == email
    
    def test_query_user_by_username(self, test_db):
        """Test querying user by username"""
        username = "queryusername"
        user = User(
            username=username,
            email="query2@example.com",
            password_hash=hash_password("password")
        )
        test_db.add(user)
        test_db.commit()
        
        # Query by username
        found_user = test_db.query(User).filter(User.username == username).first()
        assert found_user is not None
        assert found_user.username == username
    
    def test_user_password_not_stored_plaintext(self, test_db):
        """Test that password is hashed, not stored as plaintext"""
        password = "myPlainPassword123"
        user = User(
            username="secureuser",
            email="secure@example.com",
            password_hash=hash_password(password)
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Password hash should not equal the plaintext password
        assert user.password_hash != password
        assert len(user.password_hash) > len(password)
