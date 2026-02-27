from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, date
from typing import Optional, Literal, Union
from uuid import UUID


# ============ AUTH SCHEMAS ============

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: str
    username: str
    password: str
    confirm_password: str

    # --- Feature #5: Backend password confirmation validation ---
    @validator('confirm_password')
    def passwords_must_match(cls, confirm_password, values):
        if 'password' in values and confirm_password != values['password']:
            raise ValueError('Passwords do not match.')
        return confirm_password


class UserLogin(BaseModel):
    """Schema for user login"""
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
    profile_picture: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True


class ProfilePictureUpdate(BaseModel):
    profile_picture: str


class DeleteAccountRequest(BaseModel):
    password: str


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema for token payload data"""
    email: Optional[str] = None


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
        orm_mode = True

class PortfolioItemWithMetrics(PortfolioBaseItem):
    id: str
    ticker: str
    quantity: float
    avg_price: float
    current_price: Optional[float]
    cost_basis: float
    current_value: float
    total_gain_loss: float
    gain_loss_pct: float
    return_1d: Optional[float]
    return_30d: Optional[float]
    return_120d: Optional[float]
    return_360d: Optional[float]
    added_at: Optional[str]

class PortfolioSummary(BaseModel):
    total_cost_basis: float
    total_current_value: float
    total_gain_loss: float
    total_gain_loss_pct: float
    num_positions: int

class PortfolioSummaryResponse(BaseModel):
    portfolio_items: list[PortfolioItemWithMetrics]
    summary: PortfolioSummary


# ============ SENTIMENT SCHEMAS ============

SentimentLabel = Literal["bullish", "neutral", "bearish"]


class TimeRangeIndicators(BaseModel):
    d30: SentimentLabel
    d120: SentimentLabel
    d360: SentimentLabel


class StockIndicatorsOut(BaseModel):
    ticker: str
    snapshot_date: Union[date, datetime]
    close_price: Optional[float]  # may be null if not present
    indicators: TimeRangeIndicators