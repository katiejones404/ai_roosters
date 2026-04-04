"""
Portfolio service layer providing database operations for user stock positions.

Notes
-----
This module handles CRUD operations, price averaging logic, and P&L calculations.
All SQL queries use parameterized statements to prevent injection.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID, uuid4
from decimal import Decimal
import math
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def safe_float(value, default=0.0):
    """
    Safely convert a value to float, returning a default for None, NaN, or infinity.

    Notes
    -----
    Returns None when value is None and default is 0.0, preserving optional fields.
    """
    if value is None:
        return None if default == 0.0 else default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError) as e:
        return default
    
def row_to_dict(row):
    """Convert SQLAlchemy Row or dict to dict"""
    if row is None:
        return None
    if hasattr(row, '_mapping'):
        return dict(row._mapping)
    return row

def safe_datetime_to_str(value):
    """Convert datetime to ISO string, or keep string as is"""
    if value is None:
        return None
    if isinstance(value, str):
        return value  
    if hasattr(value, 'isoformat'):
        return value.isoformat()  # Convert datetime to string
    return str(value)  # Fallback


def get_user_portfolio(db: Session, user_id: UUID) -> List[PortfolioItem]:
    """Get all portfolio items for a user"""
    sql = text("""
        SELECT 
            id, user_id, ticker, quantity, avg_price, added_at
        FROM portfolio
        WHERE user_id = :user_id
        ORDER BY added_at DESC
    """)
    
    rows = db.execute(sql, {"user_id": str(user_id)}).fetchall()
    
    result = []
    for row in rows:
        row_dict = row_to_dict(row)
        result.append(PortfolioItem(
            id=row_dict["id"],
            user_id=row_dict["user_id"],
            ticker=row_dict["ticker"],
            quantity=float(row_dict["quantity"]),
            avg_price=float(row_dict["avg_price"]),
            added_at=safe_datetime_to_str(row_dict["added_at"])
        ))
    return result


def get_portfolio_item_by_ticker(
    db: Session, user_id: UUID, ticker: str
) -> Optional[PortfolioItem]:
    """Get a specific portfolio item by ticker"""
    sql = text("""
        SELECT id, user_id, ticker, quantity, avg_price, added_at
        FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    row = db.execute(sql, {"user_id": str(user_id), "ticker": ticker}).fetchone()
    if not row:
        return None
    
    row_dict = row_to_dict(row)
    return PortfolioItem(
        id=row_dict["id"],
        user_id=row_dict["user_id"],
        ticker=row_dict["ticker"],
        quantity=float(row_dict["quantity"]),
        avg_price=float(row_dict["avg_price"]),
        added_at=safe_datetime_to_str(row_dict["added_at"])
    )


def add_or_update_position(
    db: Session, user_id: UUID, item: PortfolioCreateItem
) -> PortfolioItem:
    """Add a new position or update existing position with averaging"""
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
        existing_dict = row_to_dict(existing)
        old_quantity = float(existing_dict["quantity"])
        old_avg_price = float(existing_dict["avg_price"])
        new_quantity = old_quantity + item.quantity
        new_avg_price = (
            (old_quantity * old_avg_price + item.quantity * item.avg_price) / new_quantity
        )
        
        update_sql = text("""
            UPDATE portfolio
            SET quantity = :quantity, avg_price = :avg_price
            WHERE id = :id
        """)
        
        db.execute(
            update_sql,
            {
                "id": existing_dict["id"],
                "quantity": new_quantity,
                "avg_price": new_avg_price
            }
        )
        db.commit()
        
        return get_portfolio_item_by_ticker(db, user_id, item.ticker)
    else:
        new_id = str(uuid4())
        insert_sql = text("""
            INSERT INTO portfolio (id, user_id, ticker, quantity, avg_price)
            VALUES (:id, :user_id, :ticker, :quantity, :avg_price)
        """)
        
        db.execute(
            insert_sql,
            {
                "id": new_id,
                "user_id": str(user_id),
                "ticker": item.ticker,
                "quantity": item.quantity,
                "avg_price": item.avg_price
            }
        )
    
        db.commit()

        return get_portfolio_item_by_ticker(db, user_id, item.ticker)


def update_portfolio_item(
    db: Session, user_id: UUID, ticker: str, item: PortfolioUpdateItem
) -> Optional[PortfolioItem]:
    """
    Update quantity and/or average price for an existing portfolio position.

    Notes
    -----
    Only fields provided in the update schema are modified. Returns None if
    no fields are provided or if the ticker does not exist for the user.
    """
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
    """)
    
    result = db.execute(sql, params)
    db.commit()
    if result.rowcount == 0:
        return None
    return get_portfolio_item_by_ticker(db, user_id, ticker)


def remove_from_portfolio(db: Session, user_id: UUID, ticker: str) -> bool:
    """
    Delete a portfolio position for the given user and ticker.

    Returns
    -------
    bool
        True if a row was deleted, False if the ticker was not found.
    """
    sql = text("""
        DELETE FROM portfolio
        WHERE user_id = :user_id AND ticker = :ticker
    """)
    
    result = db.execute(sql, {"user_id": str(user_id), "ticker": ticker})
    db.commit()
    return result.rowcount > 0


def get_portfolio_summary(
    db: Session, user_id: UUID
) -> PortfolioSummaryResponse:
    """Get portfolio summary with current prices and P&L calculations"""
    
    sql = text("""
        WITH latest AS (
            SELECT ticker, MAX(date) AS max_date FROM stocks GROUP BY ticker
        ),
        latest_prices AS (
            SELECT
                s.ticker,
                s.close AS current_price,
                s.date  AS price_date,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '1 day'
                 ORDER BY s2.date DESC LIMIT 1) AS close_1d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '30 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_30d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '120 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_120d_ago,
                (SELECT s2.close FROM stocks s2
                 WHERE s2.ticker = s.ticker
                   AND s2.date <= s.date - INTERVAL '360 days'
                 ORDER BY s2.date DESC LIMIT 1) AS close_360d_ago
            FROM stocks s
            INNER JOIN latest ON s.ticker = latest.ticker AND s.date = latest.max_date
        )
        SELECT
            p.id,
            p.ticker,
            p.quantity,
            p.avg_price,
            p.added_at,
            lp.current_price,
            lp.price_date,
            CASE WHEN lp.close_1d_ago   IS NOT NULL AND lp.close_1d_ago   <> 0
                 THEN (lp.current_price - lp.close_1d_ago)   / lp.close_1d_ago   * 100
                 END AS return_1d,
            CASE WHEN lp.close_30d_ago  IS NOT NULL AND lp.close_30d_ago  <> 0
                 THEN (lp.current_price - lp.close_30d_ago)  / lp.close_30d_ago  * 100
                 END AS return_30d,
            CASE WHEN lp.close_120d_ago IS NOT NULL AND lp.close_120d_ago <> 0
                 THEN (lp.current_price - lp.close_120d_ago) / lp.close_120d_ago * 100
                 END AS return_120d,
            CASE WHEN lp.close_360d_ago IS NOT NULL AND lp.close_360d_ago <> 0
                 THEN (lp.current_price - lp.close_360d_ago) / lp.close_360d_ago * 100
                 END AS return_360d,
            (p.quantity * p.avg_price) AS cost_basis,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) AS current_value,
            (p.quantity * COALESCE(lp.current_price, p.avg_price)) - (p.quantity * p.avg_price) AS total_gain_loss,
            ((COALESCE(lp.current_price, p.avg_price) - p.avg_price) / p.avg_price * 100) AS gain_loss_pct
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
        row_dict = row_to_dict(row)
        # Log raw values from database
        logger.info(f"Processing {row_dict['ticker']}: "
                   f"qty={row_dict['quantity']}, "
                   f"avg_price={row_dict['avg_price']}, "
                   f"current_price={row_dict['current_price']}, "
                   f"cost_basis={row_dict['cost_basis']}, "
                   f"current_value={row_dict['current_value']}, "
                   f"gain_loss={row_dict['total_gain_loss']}, "
                   f"gain_loss_pct={row_dict['gain_loss_pct']}")
        
        # Use safe_float for all conversions
        cost_basis = safe_float(row_dict["cost_basis"], 0.0)
        current_value = safe_float(row_dict["current_value"], 0.0)
        total_gain_loss = safe_float(row_dict["total_gain_loss"], 0.0)
        gain_loss_pct = safe_float(row_dict["gain_loss_pct"], 0.0)
        
        total_cost_basis += cost_basis if cost_basis is not None else 0.0
        total_current_value += current_value if current_value is not None else 0.0
        
        portfolio_items.append(
            PortfolioItemWithMetrics(
                id=str(row_dict["id"]),
                ticker=row_dict["ticker"],
                quantity=safe_float(row_dict["quantity"], 0.0),
                avg_price=safe_float(row_dict["avg_price"], 0.0),
                current_price=safe_float(row_dict["current_price"]),
                cost_basis=cost_basis,
                current_value=current_value,
                total_gain_loss=total_gain_loss,
                gain_loss_pct=gain_loss_pct,
                return_1d=safe_float(row_dict["return_1d"]),
                return_30d=safe_float(row_dict["return_30d"]),
                return_120d=safe_float(row_dict["return_120d"]),
                return_360d=safe_float(row_dict["return_360d"]),
                added_at=safe_datetime_to_str(row_dict["added_at"])
            )
        )
    
    # Safe final calculations
    total_gain_loss = safe_float(total_current_value - total_cost_basis, 0.0)
    total_gain_loss_pct = safe_float(
        (total_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0.0,
        0.0
    )
    
    logger.info(f"Summary totals: cost_basis={total_cost_basis}, "
               f"current_value={total_current_value}, "
               f"gain_loss={total_gain_loss}, "
               f"gain_loss_pct={total_gain_loss_pct}")
    
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