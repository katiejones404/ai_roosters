"""
Database connection and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base 

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
)

# Create database engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()