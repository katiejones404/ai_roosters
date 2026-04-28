"""
Watchlist API endpoints.
Stores per-user starred tickers in the database.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.auth import get_current_user
from app.db.main import get_db
from app.models.models import User

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistOut(BaseModel):
    tickers: List[str]


@router.get("", response_model=WatchlistOut)
def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("SELECT ticker FROM watchlist WHERE user_id = :uid ORDER BY created_at ASC"),
        {"uid": current_user.id},
    ).fetchall()
    return WatchlistOut(tickers=[r[0] for r in rows])


@router.post("/{ticker}", status_code=201)
def add_to_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = ticker.strip().upper()
    db.execute(
        text("""
            INSERT INTO watchlist (user_id, ticker)
            VALUES (:uid, :ticker)
            ON CONFLICT (user_id, ticker) DO NOTHING
        """),
        {"uid": current_user.id, "ticker": normalized},
    )
    db.commit()
    return {"ticker": normalized}


@router.delete("/{ticker}", status_code=200)
def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = ticker.strip().upper()
    result = db.execute(
        text("DELETE FROM watchlist WHERE user_id = :uid AND ticker = :ticker"),
        {"uid": current_user.id, "ticker": normalized},
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ticker not in watchlist")
    return {"ticker": normalized}
