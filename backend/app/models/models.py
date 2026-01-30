"""
Database models
"""
import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base
from app.db.types import GUID


class User(Base):
    """
    User model for authentication
    """
    __tablename__ = "users"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    email = Column(Text, unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    #username = Column(String(50), unique=True, index=True, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"