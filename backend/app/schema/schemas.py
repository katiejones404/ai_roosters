from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
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

<<<<<<< HEAD
# ============ PORTFOLIO SCHEMAS ============
class PortfolioBaseItem(BaseModel):
    ticker: str 
    quantity: float 
    avg_price: float

class PortfolioCreateItem(PortfolioBaseItem):
    pass

class PortfolioUpdateItem(BaseModel):
    quantity: Optional[float] = None
    avg_price: Optional[float] = None

class PortfolioItem(PortfolioBaseItem):
    id: UUID
    user_id: UUID
    added_at: Optional[str]

    class Config:
        orm_mode: True
=======


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
>>>>>>> 74c3d87b2cd59345b3d1117a71dbd934e1854245
