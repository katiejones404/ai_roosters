"""
Database models
"""
import uuid
from sqlalchemy import Column, String, DateTime, Text, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

    portfolio_items = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class Portfolio(Base):
    """
    User portfolio model - tracks stock positions
    """
    __tablename__ = "portfolio"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    ticker = Column(String, nullable=False)
    quantity = Column(Numeric, nullable=False)
    avg_price = Column(Numeric, nullable=False)
    added_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="portfolio_items")

    def __repr__(self):
        return f"<Portfolio(user_id={self.user_id}, ticker={self.ticker}, quantity={self.quantity})>"
