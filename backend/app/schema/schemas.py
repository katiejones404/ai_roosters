from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from typing import Literal, Optional, Dict, List
from datetime import date


# ============ AUTH SCHEMAS ============

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    
    class Config:
        orm_mode = True 


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema for token payload data"""
    email: str | None = None



# ============ Sentiment Schemas ============

SentimentLabel = Literal["bullish", "neutral", "bearish"]

class TimeRangeIndicators(BaseModel):
    d30: SentimentLabel
    d120: SentimentLabel
    d360: SentimentLabel


class StockIndicatorsOut(BaseModel):
    ticker: str
    snapshot_date: date
    indicators: TimeRangeIndicators