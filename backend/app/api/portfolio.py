"""
Portfolio API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

import sys
sys.path.insert(0, '/app')

from app.db.main import get_db
from app.models.models import User
from app.schema.schemas import (
    PortfolioItem,
    PortfolioCreateItem,
    PortfolioUpdateItem,
    PortfolioSummaryResponse
)
from app.api.auth import get_current_user
from app.services import portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=List[PortfolioItem])
async def get_user_portfolio(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return portfolio.get_user_portfolio(db, current_user.id)


@router.post("", response_model=PortfolioItem, status_code=status.HTTP_201_CREATED)
async def add_to_portfolio(item: PortfolioCreateItem, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return portfolio.add_or_update_position(db, current_user.id, item)


@router.get("/stats/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return portfolio.get_portfolio_summary(db, current_user.id)


@router.get("/{ticker}", response_model=PortfolioItem)
async def get_portfolio_item(ticker: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = portfolio.get_portfolio_item_by_ticker(db, current_user.id, ticker)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in portfolio"
        )
    return item


@router.put("/{ticker}", response_model=PortfolioItem)
async def update_portfolio_item(ticker: str, item: PortfolioUpdateItem, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated_item = portfolio.update_portfolio_item(
        db, current_user.id, ticker, item
    )
    if not updated_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in portfolio"
        )
    return updated_item


@router.delete("/{ticker}")
async def remove_from_portfolio(ticker: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    success = portfolio.remove_from_portfolio(db, current_user.id, ticker)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in portfolio"
        )
    
    return {"status": "ok", "message": f"Removed {ticker} from portfolio"}