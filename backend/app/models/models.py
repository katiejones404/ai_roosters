"""
SQLAlchemy ORM models for StockSense.

Defines the database tables and relationships used by the application:
User, Portfolio, StockNewsArticle, and PriceAlert.
"""
import uuid
from sqlalchemy import Column, String, DateTime, Date, Text, Numeric, ForeignKey, TIMESTAMP, Boolean, Integer
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
    profile_picture = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    streak_current = Column(Integer, nullable=True)
    streak_best = Column(Integer, nullable=True)
    streak_last_visit = Column(Date, nullable=True)
    streak_visit_days = Column(Text, nullable=True)  # JSON string list of YYYY-MM-DD dates
    streak_total_visits = Column(Integer, nullable=True)
    notify_market_alerts_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_push_enabled = Column(Boolean, nullable=False, default=False, server_default="false")

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


class StockNewsArticle(Base):
    """Stores news articles fetched from external sources, linked to a ticker symbol."""
    __tablename__ = "stock_news_articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    language = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())
    relevance_score = Column(Numeric, nullable=True)


class PriceAlert(Base):
    """Represents a user-defined price threshold alert for a stock ticker."""
    __tablename__ = "price_alerts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String, nullable=False)
    target_price = Column(Numeric, nullable=False)
    direction = Column(String, nullable=False)  # "above" or "below"
    is_active = Column(Boolean, default=True, nullable=False)
    email_notify = Column(Boolean, default=True, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    triggered_price = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
