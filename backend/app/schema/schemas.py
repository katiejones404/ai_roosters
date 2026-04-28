"""
Pydantic schemas for authentication, portfolio management, sentiment data,
and net worth tracking used throughout the StockSense backend.
"""

from pydantic import BaseModel, EmailStr, Field, validator
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


class StreakResponse(BaseModel):
    currentStreak: int
    bestStreak: int
    lastVisit: str
    visitDays: list[str]
    totalVisits: int


class NotificationPreferencesResponse(BaseModel):
    marketAlerts: bool
    pushNotifications: bool


class NotificationPreferencesUpdate(BaseModel):
    marketAlerts: Optional[bool] = None
    pushNotifications: Optional[bool] = None


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


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
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
    quantity: float = Field(..., ge=0.0001)
    avg_price: float = Field(..., gt=0)


class PortfolioCreateItem(PortfolioBaseItem):
    purchase_date: Optional[str] = None


class PortfolioUpdateItem(BaseModel):
    quantity: Optional[float] = Field(None, ge=0.0001)
    avg_price: Optional[float] = Field(None, gt=0)


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
    total_realized_gain: float
    num_positions: int

class PortfolioSummaryResponse(BaseModel):
    portfolio_items: list[PortfolioItemWithMetrics]
    summary: PortfolioSummary

class TransactionItem(BaseModel):
    id: str
    ticker: str
    action: str
    quantity: float
    price: float
    realized_gain: Optional[float] = None
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

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


# ============ NET WORTH SCHEMAS ============

class NetworthAssetCreate(BaseModel):
    name: str
    category: str  # cash | checking | savings | real_estate | vehicle | other
    balance: float


class NetworthAssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    balance: Optional[float] = None


class NetworthAssetOut(BaseModel):
    id: str
    name: str
    category: str
    balance: float
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True


class NetworthLiabilityCreate(BaseModel):
    name: str
    category: str  # credit_card | student_loan | auto_loan | mortgage | other
    balance: float


class NetworthLiabilityUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    balance: Optional[float] = None


class NetworthLiabilityOut(BaseModel):
    id: str
    name: str
    category: str
    balance: float
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True


class NetworthSummary(BaseModel):
    portfolio_value: float
    total_assets: float        # portfolio_value + manual assets
    total_liabilities: float
    net_worth: float           # total_assets - total_liabilities
    assets: list[NetworthAssetOut]
    liabilities: list[NetworthLiabilityOut]


class NetworthSnapshotOut(BaseModel):
    snapshot_date: str
    net_worth: float
    portfolio_value: float
    total_assets: float
    total_liabilities: float
