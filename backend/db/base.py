"""
Database base configuration
If you already have this file with content, keep your existing content
and just make sure it has these imports
"""
from sqlalchemy.ext.declarative import declarative_base

# Base class for all database models
Base = declarative_base()