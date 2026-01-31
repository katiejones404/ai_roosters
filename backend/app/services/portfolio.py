"""
Portfolio service - Business logic for portfolio operations
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

import sys
sys.path.insert(0, '/app')

from app.schema.schemas import (
    PortfolioItem,
    PortfolioCreateItem,
    PortfolioUpdateItem,
    PortfolioItemWithMetrics,
    PortfolioSummary,
    PortfolioSummaryResponse
)


def get_user_portfolio(db: Session, user_id: UUID) -> List[PortfolioItem]:
    """
    Get all portfolio items for a user
    """
    sql = text("""
        SELECT 
            id,
            user_id,
            ticker,
            quantity,
            avg_price,
            added_at
        FROM portfolio
        WHERE user_id = :user_id
        ORDER BY added_at DESC
    """)
    
    rows = db.execute(sql, {"user_id": str(user_id)}).fetchall()
    
    return [
        PortfolioItem(
            id=row["id"],
            user_id=row["user_id"],
            ticker=row["ticker"],
            quantity=float(row["quantity"]),
            avg_price=float(row["avg_price"]),
            added_at=row["added_at"].isoformat() if row["added_at"] else None
        )
        for row in rows
    ]


def get_portfolio_item_by_ticker(
    db: Session, 
    user_id: UUID, 
    ticker: str
) -> Optional[PortfolioItem]:
    """
    Get a specific portfolio item by ticker
    """
    sql = text("""
        SELECT 
            id,
            user_id,
            ticker,
            quantity,
            avg_price,
            added_at
        FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    row = db.execute(
        sql,
        {"user_id": str(user_id), "ticker": ticker}
    ).fetchone()
    
    if not row:
        return None
    
    return PortfolioItem(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        quantity=float(row["quantity"]),
        avg_price=float(row["avg_price"]),
        added_at=row["added_at"].isoformat() if row["added_at"] else None
    )


def add_or_update_position(
    db: Session, 
    user_id: UUID, 
    item: PortfolioCreateItem
) -> PortfolioItem:
    """
    Add a new position or update existing position with averaging
    """
    # Check if ticker already exists in user's portfolio
    check_sql = text("""
        SELECT id, quantity, avg_price
        FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    existing = db.execute(
        check_sql,
        {"user_id": str(user_id), "ticker": item.ticker}
    ).fetchone()
    
    if existing:
        # Update existing position (average down/up)
        old_quantity = float(existing["quantity"])
        old_avg_price = float(existing["avg_price"])
        new_quantity = old_quantity + item.quantity
        
        # Calculate new average price
        new_avg_price = (
            (old_quantity * old_avg_price + item.quantity * item.avg_price) / new_quantity
        )
        
        update_sql = text("""
            UPDATE portfolio
            SET quantity = :quantity,
                avg_price = :avg_price
            WHERE id = :id
            RETURNING id, user_id, ticker, quantity, avg_price, added_at
        """)
        
        row = db.execute(
            update_sql,
            {
                "id": str(existing["id"]),
                "quantity": new_quantity,
                "avg_price": new_avg_price
            }
        ).fetchone()
    else:
        # Insert new position
        insert_sql = text("""
            INSERT INTO portfolio (user_id, ticker, quantity, avg_price)
            VALUES (:user_id, :ticker, :quantity, :avg_price)
            RETURNING id, user_id, ticker, quantity, avg_price, added_at
        """)
        
        row = db.execute(
            insert_sql,
            {
                "user_id": str(user_id),
                "ticker": item.ticker,
                "quantity": item.quantity,
                "avg_price": item.avg_price
            }
        ).fetchone()
    
    db.commit()
    
    return PortfolioItem(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        quantity=float(row["quantity"]),
        avg_price=float(row["avg_price"]),
        added_at=row["added_at"].isoformat() if row["added_at"] else None
    )


def update_portfolio_item(
    db: Session,
    user_id: UUID,
    ticker: str,
    item: PortfolioUpdateItem
) -> Optional[PortfolioItem]:
    """
    Update quantity or average price for a portfolio item
    """
    # Build dynamic update query
    update_fields = []
    params = {"user_id": str(user_id), "ticker": ticker}
    
    if item.quantity is not None:
        update_fields.append("quantity = :quantity")
        params["quantity"] = item.quantity
    
    if item.avg_price is not None:
        update_fields.append("avg_price = :avg_price")
        params["avg_price"] = item.avg_price
    
    if not update_fields:
        return None
    
    sql = text(f"""
        UPDATE portfolio
        SET {', '.join(update_fields)}
        WHERE user_id = :user_id AND ticker = :ticker
        RETURNING id, user_id, ticker, quantity, avg_price, added_at
    """)
    
    row = db.execute(sql, params).fetchone()
    db.commit()
    
    if not row:
        return None
    
    return PortfolioItem(
        id=row["id"],
        user_id=row["user_id"],
        ticker=row["ticker"],
        quantity=float(row["quantity"]),
        avg_price=float(row["avg_price"]),
        added_at=row["added_at"].isoformat() if row["added_at"] else None
    )


def remove_from_portfolio(
    db: Session,
    user_id: UUID,
    ticker: str
) -> bool:
    """
    Remove a stock from user's portfolio
    Returns True if deleted, False if not found
    """
    sql = text("""
        DELETE FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    result = db.execute(
        sql,
        {"user_id": str(user_id), "ticker": ticker}
    )
    db.commit()
    
    return result.rowcount > 0


def get_portfolio_summary(
    db: Session,
    user_id: UUID
) -> PortfolioSummaryResponse:
    """
    Get portfolio summary with current prices and P&L calculations
    """
    # Get portfolio items with latest prices and returns
    sql = text("""
        WITH latest_prices AS (
            SELECT DISTINCT ON (ticker)
                ticker,
                close as current_price,
                return_1d,
                return_30d,
                return_120d,
                return_360d,
                date as price_date
            FROM stocks
            ORDER BY ticker, date DESC
        )
        SELECT 
            p.id,
            p.ticker,
            p.quantity,
            p.avg_price,
            p.added_at,
            lp.current_price,
            lp.return_1d,
            lp.return_30d,
            lp.return_120d,
            lp.return_360d,
            lp.price_date,
            (p.quantity * p.avg_price) as cost_basis,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) as current_value,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) - (p.quantity * p.avg_price) as total_gain_loss,
            ((COALESCE(lp.current_price, p.avg_price) - p.avg_price) / p.avg_price * 100) as gain_loss_pct
        FROM portfolio p
        LEFT JOIN latest_prices lp ON p.ticker = lp.ticker
        WHERE p.user_id = :user_id
        ORDER BY p.added_at DESC
    """)
    
    rows = db.execute(sql, {"user_id": str(user_id)}).fetchall()
    
    portfolio_items = []
    total_cost_basis = 0.0
    total_current_value = 0.0
    
    for row in rows:
        cost_basis = float(row["cost_basis"]) if row["cost_basis"] else 0.0
        current_value = float(row["current_value"]) if row["current_value"] else 0.0
        total_gain_loss = float(row["total_gain_loss"]) if row["total_gain_loss"] else 0.0
        gain_loss_pct = float(row["gain_loss_pct"]) if row["gain_loss_pct"] else 0.0
        
        total_cost_basis += cost_basis
        total_current_value += current_value
        
        portfolio_items.append(
            PortfolioItemWithMetrics(
                id=str(row["id"]),
                ticker=row["ticker"],
                quantity=float(row["quantity"]),
                avg_price=float(row["avg_price"]),
                current_price=float(row["current_price"]) if row["current_price"] else None,
                cost_basis=cost_basis,
                current_value=current_value,
                total_gain_loss=total_gain_loss,
                gain_loss_pct=gain_loss_pct,
                return_1d=float(row["return_1d"]) if row["return_1d"] else None,
                return_30d=float(row["return_30d"]) if row["return_30d"] else None,
                return_120d=float(row["return_120d"]) if row["return_120d"] else None,
                return_360d=float(row["return_360d"]) if row["return_360d"] else None,
                added_at=row["added_at"].isoformat() if row["added_at"] else None
            )
        )
    
    total_gain_loss = total_current_value - total_cost_basis
    total_gain_loss_pct = (
        (total_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
    )
    
    summary = PortfolioSummary(
        total_cost_basis=total_cost_basis,
        total_current_value=total_current_value,
        total_gain_loss=total_gain_loss,
        total_gain_loss_pct=total_gain_loss_pct,
        num_positions=len(portfolio_items)
    )
    
    return PortfolioSummaryResponse(
        portfolio_items=portfolio_items,
        summary=summary
    )