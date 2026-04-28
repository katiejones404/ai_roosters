"""
Portfolio API endpoints for managing user stock positions and calculating performance.

Notes
-----
All endpoints require authentication. Portfolio operations delegate business logic
to the services.portfolio module, which handles price averaging and P&L calculations.
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
    PortfolioSummaryResponse,
    TransactionItem
)
from app.api.auth import get_current_user
from app.services import portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=List[PortfolioItem])
async def get_user_portfolio(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Return all portfolio positions for the authenticated user.

    Returns
    -------
    list of PortfolioItem
        All stock positions held by the current user, ordered by date added.
    """
    return portfolio.get_user_portfolio(db, current_user.id)


@router.post("", response_model=PortfolioItem, status_code=status.HTTP_201_CREATED)
async def add_to_portfolio(item: PortfolioCreateItem, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Add a new position or increase an existing position using price averaging.

    Notes
    -----
    If the ticker already exists in the portfolio, the quantity is increased and
    the average price is recalculated using a weighted average of old and new shares.
    Rejects quantities that would exceed the total shares outstanding for the ticker.

    Returns
    -------
    PortfolioItem
        The created or updated portfolio position.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(item.ticker).info
        shares_outstanding = info.get("sharesOutstanding")
        if shares_outstanding:
            existing = portfolio.get_portfolio_item_by_ticker(db, current_user.id, item.ticker)
            total_after = (existing.quantity if existing else 0.0) + item.quantity
            if total_after > shares_outstanding:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Quantity exceeds total shares outstanding for {item.ticker} "
                        f"({shares_outstanding:,.0f} shares). "
                        f"You requested {total_after:,.4f} shares."
                    ),
                )
    except HTTPException:
        raise
    except Exception:
        pass  # Fail open if yfinance is unavailable

    return portfolio.add_or_update_position(db, current_user.id, item)


@router.get("/stats/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Return portfolio positions with current market prices and P&L calculations.

    Returns
    -------
    PortfolioSummaryResponse
        All positions with current price, cost basis, unrealized gain/loss,
        and 1D/30D/120D/360D return percentages, plus a portfolio-level summary.
    """
    return portfolio.get_portfolio_summary(db, current_user.id)


@router.get("/transactions", response_model=List[TransactionItem])
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all buy and sell transaction history for the authenticated user, newest first."""
    return portfolio.get_transactions(db, current_user.id)


@router.get("/transactions/summary")
async def get_realized_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return per-ticker realized gain totals and sell counts for the authenticated user."""
    return portfolio.get_realized_summary(db, current_user.id)


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a single transaction log entry and recompute the affected portfolio
    position from remaining transactions.

    Returns 404 if the transaction does not exist or belongs to a different user.
    """
    success = portfolio.delete_transaction(db, current_user.id, transaction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return {"status": "ok"}


@router.get("/{ticker}", response_model=PortfolioItem)
async def get_portfolio_item(ticker: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Return a single portfolio position by ticker symbol.

    Path Parameters
    ---------------
    ticker : str
        The stock ticker symbol to look up.

    Returns
    -------
    PortfolioItem
        The matching portfolio position.

    Notes
    -----
    Returns 404 if the ticker is not in the user's portfolio.
    """
    item = portfolio.get_portfolio_item_by_ticker(db, current_user.id, ticker)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in portfolio"
        )
    return item


@router.put("/{ticker}", response_model=PortfolioItem)
async def update_portfolio_item(ticker: str, item: PortfolioUpdateItem, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Update the quantity or average price for an existing portfolio position.

    Path Parameters
    ---------------
    ticker : str
        The stock ticker symbol of the position to update.

    Returns
    -------
    PortfolioItem
        The updated portfolio position.

    Notes
    -----
    Returns 404 if the ticker is not in the user's portfolio.
    Only fields provided in the request body are updated.
    """
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
    """
    Permanently remove a stock position from the user's portfolio.

    Path Parameters
    ---------------
    ticker : str
        The stock ticker symbol of the position to remove.

    Notes
    -----
    Returns 404 if the ticker is not in the user's portfolio.
    """
    success = portfolio.remove_from_portfolio(db, current_user.id, ticker)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in portfolio"
        )

    return {"status": "ok", "message": f"Removed {ticker} from portfolio"}
