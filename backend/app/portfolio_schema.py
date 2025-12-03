from pydantic import BaseModel
from typing import Optional
from uuid import UUID


# Base schema for portfolio items
class PortfolioBaseItem(BaseModel):
    ticker: str
    quantity: float
    avg_price: float


# Schema for creating a new portfolio item
class PortfolioCreateItem(PortfolioBaseItem):
    pass


# Schema for updating an existing portfolio item
class PortfolioUpdateItem(BaseModel):
    quantity: Optional[float] = None
    avg_price: Optional[float] = None


# Schema for returning portfolio items (with DB fields)
class PortfolioItem(PortfolioBaseItem):
    id: UUID
    user_id: UUID
    added_at: Optional[str]

    class Config:
        orm_mode = True   # ✅ corrected from "orm_mode: True"