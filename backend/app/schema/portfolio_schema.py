from pydantic import BaseModel
from typing import Optional
from uuid import UUID

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
